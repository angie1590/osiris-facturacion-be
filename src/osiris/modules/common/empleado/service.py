from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, cast
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, select

from osiris.core.company_scope import (
    ensure_entity_belongs_to_selected_company,
    resolve_company_scope,
)
from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.domain.service import BaseService
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.persona.composition import resolve_persona
from osiris.modules.common.persona.entity import Persona
from osiris.modules.common.usuario.entity import Usuario
from osiris.modules.common.usuario.service import (
    UsuarioService,
    check_directory_references,
)
from osiris.utils.pagination import PaginationMeta
from .entity import Empleado
from .models import EmpleadoRead, _calc_age, _min_employee_age
from .repository import EmpleadoRepository
from .strategy import EmpleadoCrearUsuarioStrategy


class EmpleadoService(BaseService[Empleado, EmpleadoRead]):
    repo = EmpleadoRepository()
    fk_models = {"persona_id": Persona, "empresa_id": Empresa}

    def __init__(self, strategy: EmpleadoCrearUsuarioStrategy | None = None) -> None:
        self.strategy = strategy or EmpleadoCrearUsuarioStrategy()

    @staticmethod
    def _ensure_dict(data: Any) -> dict[str, Any]:
        return UsuarioService._ensure_dict(data)

    def _check_fk_active_and_exists(
        self, session: Session, data: dict[str, Any]
    ) -> None:
        check_directory_references(session, data, self.fk_models)

    @staticmethod
    def _validate_labor(payload: dict[str, Any]) -> None:
        try:
            salary = Decimal(str(payload["salario"]))
            if (
                not salary.is_finite()
                or salary < 0
                or salary >= Decimal("100000000")
                or salary != salary.quantize(Decimal("0.01"))
            ):
                raise ValueError(
                    "El salario debe ser decimal no negativo, con hasta dos decimales y diez digitos"
                )
            payload["salario"] = salary
            for field in ("fecha_ingreso", "fecha_salida", "fecha_nacimiento"):
                value = payload.get(field)
                if isinstance(value, str):
                    payload[field] = date.fromisoformat(value)
            entry = payload.get("fecha_ingreso")
            if not isinstance(entry, date) or entry > date.today():
                raise ValueError(
                    "La fecha de ingreso no puede ser mayor que la fecha actual"
                )
            departure = payload.get("fecha_salida")
            if departure is not None and departure <= entry:
                raise ValueError(
                    "La fecha de salida debe ser posterior a la fecha de ingreso"
                )
            birth = payload.get("fecha_nacimiento")
            minimum_age = _min_employee_age()
            if birth is not None and _calc_age(birth, date.today()) < minimum_age:
                raise ValueError(f"El empleado debe tener al menos {minimum_age} anos")
        except (KeyError, ValueError, TypeError, InvalidOperation) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def create(self, session: Session, data: Any, *, commit: bool = True) -> Empleado:
        try:
            payload = self._ensure_dict(data).copy()
            if not payload.get("empresa_id"):
                raise HTTPException(status_code=422, detail="empresa_id es requerido")
            payload["empresa_id"] = UUID(str(payload["empresa_id"]))
            resolve_company_scope(requested_company_id=payload["empresa_id"])
            payload = resolve_persona(session, payload)
            self._validate_labor(payload)
            self._check_fk_active_and_exists(session, payload)
            existing = session.exec(
                select(Empleado)
                .where(Empleado.persona_id == payload["persona_id"])
                .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
            ).first()
            if existing is not None:
                raise HTTPException(
                    status_code=409,
                    detail="Empleado ya registrado; use reactivacion explicita",
                )
            user = session.exec(
                select(Usuario)
                .where(Usuario.persona_id == payload["persona_id"])
                .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
            ).first()
            if user is not None:
                raise HTTPException(
                    status_code=409,
                    detail="Persona con Usuario previo; requiere una decision administrativa sin sobrescribir credenciales",
                )
            usuario_payload = payload.pop("usuario", None)
            self.strategy.create_user_for_persona(
                session,
                persona_id=payload["persona_id"],
                usuario_payload=usuario_payload,
                commit=False,
            )
            employee = cast(Empleado, self.repo.create(session, payload))
            if commit:
                session.commit()
                session.refresh(employee)
            return employee
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    def get(self, session: Session, item_id: UUID) -> Empleado | None:
        employee = cast(Empleado | None, self.repo.get(session, item_id))
        if employee is not None:
            ensure_entity_belongs_to_selected_company(employee.empresa_id)
        return employee

    def list_paginated(
        self,
        session: Session,
        *,
        only_active: bool = True,
        limit: int = 50,
        offset: int = 0,
        **filters: Any,
    ) -> tuple[list[EmpleadoRead], PaginationMeta]:
        filters["empresa_id"] = resolve_company_scope(
            requested_company_id=filters.get("empresa_id")
        )
        return super().list_paginated(
            session, only_active=only_active, limit=limit, offset=offset, **filters
        )

    def update(
        self, session: Session, item_id: UUID, data: Any, *, commit: bool = True
    ) -> Empleado | None:
        try:
            incoming = self._ensure_dict(data).copy()
            current = self.get(session, item_id)
            if current is None:
                return None
            if "persona_id" in incoming and str(incoming["persona_id"]) != str(
                current.persona_id
            ):
                raise HTTPException(status_code=409, detail="persona_id es inmutable")
            incoming.pop("persona_id", None)
            allowed = {
                "empresa_id",
                "salario",
                "fecha_ingreso",
                "fecha_salida",
                "fecha_nacimiento",
                "foto",
                "usuario_auditoria",
            }
            if incoming.keys() - allowed:
                raise HTTPException(
                    status_code=422,
                    detail="Campos no editables; use reactivacion explicita",
                )
            if "empresa_id" in incoming:
                if incoming["empresa_id"] is None:
                    raise HTTPException(
                        status_code=422, detail="empresa_id no puede ser null"
                    )
                incoming["empresa_id"] = UUID(str(incoming["empresa_id"]))
                resolve_company_scope(requested_company_id=incoming["empresa_id"])
            combined = {**current.model_dump(), **incoming}
            self._validate_labor(combined)
            for field in (
                "salario",
                "fecha_ingreso",
                "fecha_salida",
                "fecha_nacimiento",
            ):
                if field in incoming:
                    incoming[field] = combined[field]
            self._check_fk_active_and_exists(session, incoming)
            updated = cast(Empleado, self.repo.update(session, current, incoming))
            if commit:
                session.commit()
                session.refresh(updated)
            return updated
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    def _get_history(self, session: Session, item_id: UUID) -> Empleado | None:
        employee = session.exec(
            select(Empleado)
            .where(Empleado.id == item_id)
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
            .with_for_update()
        ).first()
        if employee is not None:
            ensure_entity_belongs_to_selected_company(employee.empresa_id)
        return employee

    def delete(
        self, session: Session, item_id: UUID, *, commit: bool = True
    ) -> bool | None:
        try:
            employee = self._get_history(session, item_id)
            if employee is None:
                return None
            user = session.exec(
                select(Usuario)
                .where(Usuario.persona_id == employee.persona_id)
                .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
                .with_for_update()
            ).first()
            if user is not None:
                UsuarioService().repo.update(
                    session,
                    user,
                    {"activo": False, "sesion_invalidada_en": datetime.utcnow()},
                )
            self.repo.delete(session, employee)
            if commit:
                session.commit()
            return True
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    def reactivate(
        self, session: Session, item_id: UUID, *, commit: bool = True
    ) -> Empleado:
        try:
            employee = self._get_history(session, item_id)
            if employee is None:
                raise HTTPException(status_code=404, detail="Empleado no encontrado")
            resolve_persona(session, {"persona_id": employee.persona_id})
            self._check_fk_active_and_exists(
                session, {"empresa_id": employee.empresa_id}
            )
            self._validate_labor(employee.model_dump())
            updated = cast(
                Empleado, self.repo.update(session, employee, {"activo": True})
            )
            if commit:
                session.commit()
                session.refresh(updated)
            return updated
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    @staticmethod
    def to_read(session: Session, employee: Empleado) -> EmpleadoRead:
        return EmpleadoRead.model_validate(
            {
                **employee.model_dump(),
                "persona": session.get(Persona, employee.persona_id),
            }
        )

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, col, select

from osiris.core.audit_context import get_current_user_id
from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.domain.service import BaseService
from osiris.modules.common.persona.composition import resolve_persona
from osiris.modules.common.persona.entity import Persona
from osiris.utils.pagination import PaginationMeta, build_pagination_meta


class DirectoryService(BaseService[Any]):
    read_model: Any = None
    create_model: Any = None
    update_model: Any = None
    persona_field: str | None = None
    persona_new_field: str = "persona_nueva"
    unique_field: str | None = None
    catalog_model: Any = None
    catalog_field: str | None = None
    catalog_key: str = "id"
    catalog_name_field: str | None = None

    def _payload(self, data: Any, *, updating: bool = False) -> dict[str, Any]:
        payload = self._ensure_dict(data).copy()
        model = self.update_model if updating else self.create_model
        if model is not None and payload.keys() - model.model_fields.keys():
            raise HTTPException(
                status_code=422,
                detail="Campos no editables; use reactivacion explicita",
            )
        payload["usuario_auditoria"] = (
            get_current_user_id() or payload.get("usuario_auditoria") or "system"
        )
        return payload

    def _resolve(
        self, session: Session, payload: dict[str, Any], *, required: bool = True
    ) -> dict[str, Any]:
        if self.persona_field:
            if payload.get(self.persona_field) is not None:
                try:
                    payload[self.persona_field] = UUID(str(payload[self.persona_field]))
                except ValueError as error:
                    raise HTTPException(
                        status_code=422, detail="Referencia Persona no valida"
                    ) from error
            return resolve_persona(
                session,
                payload,
                id_field=self.persona_field,
                new_field=self.persona_new_field,
                required=required,
            )
        return payload

    def _check_duplicate(
        self, session: Session, payload: dict[str, Any], *, item_id: UUID | None = None
    ) -> None:
        if not self.unique_field or self.unique_field not in payload:
            return
        model = self.repo.model
        statement = select(model).where(
            getattr(model, self.unique_field) == payload[self.unique_field]
        )
        if item_id is not None:
            statement = statement.where(model.id != item_id)
        existing = session.exec(
            statement.execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        ).first()
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail={
                    "mensaje": f"{model.__name__} ya registrado"
                    + (
                        "; requiere reactivacion explicita"
                        if not existing.activo
                        else ""
                    ),
                    "id": str(existing.id),
                    "activo": existing.activo,
                    "accion": "reactivar" if not existing.activo else "consultar",
                },
            )

    def create(self, session: Session, data: Any, *, commit: bool = True) -> Any:
        try:
            payload = self._resolve(
                session, self.prepare_create(session, self._payload(data))
            )
            self._check_duplicate(session, payload)
            obj = super().create(session, payload, commit=False)
            if commit:
                session.commit()
                session.refresh(obj)
            return obj
        except Exception as error:
            self._handle_transaction_error(session, error)

    def prepare_create(
        self, session: Session, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return payload

    def prepare_update(
        self, session: Session, current: Any, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return payload

    def get(self, session: Session, item_id: UUID) -> Any:
        return self.repo.get(session, item_id)

    def update(
        self, session: Session, item_id: UUID, data: Any, *, commit: bool = True
    ) -> Any:
        try:
            payload = self._payload(data, updating=True)
            current = self.repo.get(session, item_id)
            if current is None:
                return None
            if current.activo is False:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "mensaje": "Registro inactivo",
                        "id": str(item_id),
                        "accion": "reactivar",
                    },
                )
            payload = self.prepare_update(session, current, payload)
            self._check_fk_active_and_exists(session, payload)
            updated = self.repo.update(session, current, payload)
            if commit:
                session.commit()
                session.refresh(updated)
            return updated
        except Exception as error:
            self._handle_transaction_error(session, error)

    @staticmethod
    def immutable_persona(current: Any, payload: dict[str, Any]) -> dict[str, Any]:
        if "persona_id" in payload and str(payload["persona_id"]) != str(
            current.persona_id
        ):
            raise HTTPException(status_code=409, detail="persona_id es inmutable")
        payload.pop("persona_id", None)
        return payload

    def reactivate(
        self, session: Session, item_id: UUID, *, commit: bool = True
    ) -> Any:
        try:
            current = self.repo.get(session, item_id, lock=True)
            if current is None:
                raise HTTPException(status_code=404, detail="Registro no encontrado")
            if current.activo:
                return current
            payload = current.model_dump()
            self._resolve(
                session,
                (
                    {self.persona_field: payload[self.persona_field]}
                    if self.persona_field
                    else {}
                ),
            )
            self.validate_create(payload, session)
            self._check_fk_active_and_exists(session, payload)
            updated = self.repo.update(
                session,
                current,
                {
                    "activo": True,
                    "usuario_auditoria": get_current_user_id() or "system",
                },
            )
            if commit:
                session.commit()
                session.refresh(updated)
            return updated
        except Exception as error:
            self._handle_transaction_error(session, error)

    def _related(
        self, session: Session, items: list[Any]
    ) -> tuple[dict[Any, Any], dict[Any, Any]]:
        persons: dict[Any, Any] = {}
        catalogs: dict[Any, Any] = {}
        if items and self.persona_field:
            ids = {getattr(item, self.persona_field) for item in items}
            persons = {
                person.id: person
                for person in session.exec(
                    select(Persona)
                    .where(col(Persona.id).in_(ids))
                    .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
                ).all()
            }
        if items and self.catalog_model is not None and self.catalog_field:
            ids = {getattr(item, self.catalog_field) for item in items}
            model = self.catalog_model
            catalogs = {
                getattr(catalog, self.catalog_key): catalog
                for catalog in session.exec(
                    select(model)
                    .where(getattr(model, self.catalog_key).in_(ids))
                    .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
                ).all()
            }
        return persons, catalogs

    def _read(
        self, item: Any, persons: dict[Any, Any], catalogs: dict[Any, Any]
    ) -> Any:
        payload = item.model_dump()
        payload["created_at"] = item.creado_en
        payload["updated_at"] = item.actualizado_en
        if self.persona_field:
            payload["persona"] = persons.get(getattr(item, self.persona_field))
        if self.catalog_field:
            catalog = catalogs.get(getattr(item, self.catalog_field))
            if catalog is not None:
                if self.catalog_name_field:
                    payload[self.catalog_name_field] = catalog.nombre
                if hasattr(catalog, "descuento"):
                    payload["descuento"] = catalog.descuento
        return self.read_model.model_validate(payload)

    def to_read(self, session: Session, item: Any) -> Any:
        return self._read(item, *self._related(session, [item]))

    def list_paginated(
        self,
        session: Session,
        *,
        only_active: bool = True,
        limit: int = 50,
        offset: int = 0,
        **filters: Any,
    ) -> tuple[list[Any], PaginationMeta]:
        items, total = self.repo.list(
            session, only_active=only_active, limit=limit, offset=offset, **filters
        )
        meta = build_pagination_meta(total=total, limit=limit, offset=offset)
        if self.persona_field:
            persons, catalogs = self._related(session, items)
            items = [self._read(item, persons, catalogs) for item in items]
        return items, meta

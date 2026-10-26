from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, col, select

from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.domain.directory_service import DirectoryService
from osiris.modules.common.cliente.entity import Cliente
from .entity import TipoCliente
from .models import TipoClienteCreate, TipoClienteRead, TipoClienteUpdate
from .repository import TipoClienteRepository


class TipoClienteService(DirectoryService):
    repo = TipoClienteRepository()
    create_model = TipoClienteCreate
    update_model = TipoClienteUpdate
    read_model = TipoClienteRead

    def _normalize(
        self, session: Session, payload: dict[str, Any], *, item_id: UUID | None = None
    ) -> None:
        name = payload.get("nombre")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 255:
            raise HTTPException(
                status_code=400,
                detail="nombre debe ser no vacio y tener hasta 255 caracteres",
            )
        payload["nombre"] = name.strip()
        try:
            discount = Decimal(str(payload.get("descuento")))
            if not discount.is_finite() or not 0 <= discount <= 100:
                raise ValueError("Descuento fuera de rango")
        except (InvalidOperation, ValueError) as error:
            raise HTTPException(
                status_code=400, detail="descuento debe estar entre 0 y 100"
            ) from error
        payload["descuento"] = discount
        statement = select(TipoCliente).where(
            func.lower(func.trim(TipoCliente.nombre)) == payload["nombre"].lower()
        )
        if item_id is not None:
            statement = statement.where(TipoCliente.id != item_id)
        existing = session.exec(
            statement.execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        ).first()
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail={
                    "mensaje": "Nombre de TipoCliente ya registrado",
                    "id": str(existing.id),
                    "activo": existing.activo,
                    "accion": "consultar" if existing.activo else "reactivar",
                },
            )

    def validate_create(self, data: dict[str, Any], session: Session) -> None:
        self._normalize(session, data, item_id=data.get("id"))

    def prepare_update(
        self, session: Session, current: Any, payload: dict[str, Any]
    ) -> dict[str, Any]:
        combined = {**current.model_dump(), **payload}
        self._normalize(session, combined, item_id=current.id)
        for field in ("nombre", "descuento"):
            if field in payload:
                payload[field] = combined[field]
        return payload

    def delete(
        self, session: Session, item_id: UUID, *, commit: bool = True
    ) -> bool | None:
        try:
            current = self.repo.get(session, item_id, lock=True)
            if current is None:
                return None
            dependencies = session.exec(
                select(Cliente)
                .where(
                    Cliente.tipo_cliente_id == item_id, col(Cliente.activo).is_(True)
                )
                .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
            ).all()
            if dependencies:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "mensaje": "TipoCliente tiene Clientes activos; reasignar antes de desactivar",
                        "dependencias": [
                            {"tipo": "cliente", "id": str(customer.id)}
                            for customer in dependencies
                        ],
                    },
                )
            self.repo.delete(session, current)
            if commit:
                session.commit()
            return True
        except Exception as error:
            self._handle_transaction_error(session, error)

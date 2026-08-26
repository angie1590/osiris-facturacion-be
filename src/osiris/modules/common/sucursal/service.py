from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional
from uuid import UUID
from fastapi import HTTPException
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError

from osiris.domain.service import BaseService
from .repository import SucursalRepository
from .entity import Sucursal
from osiris.modules.common.empresa.entity import Empresa


class SucursalService(BaseService):
    fk_models = {"empresa_id": Empresa}
    repo = SucursalRepository()

    @staticmethod
    def _as_decimal(value: object, *, field_name: str) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail=f"El campo '{field_name}' debe ser un decimal valido",
            ) from exc

    def _validate_geo_coordinates(self, data: dict) -> None:
        if "latitud" in data:
            latitud = self._as_decimal(data.get("latitud"), field_name="latitud")
            if latitud is not None and not (Decimal("-90") <= latitud <= Decimal("90")):
                raise HTTPException(status_code=400, detail="La latitud debe estar entre -90 y 90")
            data["latitud"] = latitud

        if "longitud" in data:
            longitud = self._as_decimal(data.get("longitud"), field_name="longitud")
            if longitud is not None and not (Decimal("-180") <= longitud <= Decimal("180")):
                raise HTTPException(status_code=400, detail="La longitud debe estar entre -180 y 180")
            data["longitud"] = longitud

    @staticmethod
    def _raise_integrity_error(exc: IntegrityError) -> None:
        diag = getattr(getattr(exc, "orig", None), "diag", None)
        constraint_name = getattr(diag, "constraint_name", "") or ""
        lower_error = str(exc).lower()

        if (
            constraint_name == "uq_sucursal_empresa_codigo"
            or "uq_sucursal_empresa_codigo" in lower_error
            or "unique constraint failed: tbl_sucursal.empresa_id, tbl_sucursal.codigo" in lower_error
        ):
            raise HTTPException(
                status_code=400,
                detail="La empresa ya posee una sucursal con ese código",
            ) from exc

        if (
            constraint_name == "ck_sucursal_matriz_codigo"
            or "ck_sucursal_matriz_codigo" in lower_error
            or "check constraint failed: ck_sucursal_matriz_codigo" in lower_error
        ):
            raise HTTPException(
                status_code=400,
                detail="La sucursal matriz debe tener código '001' y las demás no pueden marcarse como matriz",
            ) from exc

        if constraint_name == "ck_sucursal_latitud_rango" or "ck_sucursal_latitud_rango" in lower_error:
            raise HTTPException(status_code=400, detail="La latitud debe estar entre -90 y 90") from exc

        if constraint_name == "ck_sucursal_longitud_rango" or "ck_sucursal_longitud_rango" in lower_error:
            raise HTTPException(status_code=400, detail="La longitud debe estar entre -180 y 180") from exc

        raise HTTPException(status_code=400, detail="Error de integridad al guardar sucursal") from exc

    def create(self, session: Session, data: dict) -> Sucursal:
        self.validate_create(data, session)
        self._check_fk_active_and_exists(session, data)
        self._validate_geo_coordinates(data)

        obj = Sucursal(**data)
        session.add(obj)
        try:
            session.commit()
            session.refresh(obj)
            self.on_created(obj, session)
            return obj
        except IntegrityError as exc:
            session.rollback()
            self._raise_integrity_error(exc)

    def update(self, session: Session, item_id: UUID, data: dict) -> Optional[Sucursal]:
        db_obj = self.repo.get(session, item_id)
        if not db_obj:
            return None

        self.validate_update(data, session)
        self._check_fk_active_and_exists(session, data)
        self._validate_geo_coordinates(data)

        for field, value in data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        session.add(db_obj)
        try:
            session.commit()
            session.refresh(db_obj)
            self.on_updated(db_obj, session)
            return db_obj
        except IntegrityError as exc:
            session.rollback()
            self._raise_integrity_error(exc)

    # ---------- atajos que ya tenías ----------
    def list_by_empresa(
        self,
        session: Session,
        *,
        empresa_id: UUID,
        limit: int,
        offset: int,
        only_active: bool = True,
    ):
        return self.list_paginated(
            session,
            limit=limit,
            offset=offset,
            only_active=only_active,
            empresa_id=empresa_id,
        )

    def get_by_empresa_y_codigo(
        self,
        session: Session,
        *,
        empresa_id: UUID,
        codigo: str,
        only_active: Optional[bool] = None,
    ) -> Optional[Sucursal]:
        stmt = select(Sucursal).where(
            Sucursal.empresa_id == empresa_id,
            Sucursal.codigo == codigo,
        )
        if only_active is True:
            stmt = stmt.where(Sucursal.activo.is_(True))
        return session.exec(stmt).first()

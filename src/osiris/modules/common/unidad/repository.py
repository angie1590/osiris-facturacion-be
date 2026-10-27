from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.domain.repository import BaseRepository
from osiris.modules.common.unidad.entity import Unidad
from osiris.modules.inventario.atributo.entity import Atributo, AtributoCambio


class UnidadRepository(BaseRepository):
    model = Unidad

    @staticmethod
    def usage_for_units(session: Session, unit_ids: set[UUID]) -> dict[UUID, dict[str, int]]:
        usage = {
            unit_id: {
                "atributos_activos": 0,
                "atributos_inactivos": 0,
                "snapshots_historicos": 0,
            }
            for unit_id in unit_ids
        }
        if not unit_ids:
            return usage

        attribute_rows = session.exec(
            select(col(Atributo.unidad_id), col(Atributo.activo), func.count())
            .where(col(Atributo.unidad_id).in_(unit_ids))
            .group_by(col(Atributo.unidad_id), col(Atributo.activo))
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        ).all()
        for unit_id, active, count in attribute_rows:
            if unit_id in usage:
                key = "atributos_activos" if active else "atributos_inactivos"
                usage[unit_id][key] = int(count)

        unit_ids_as_text = {str(unit_id) for unit_id in unit_ids}
        snapshot_statement = select(AtributoCambio).where(
            or_(
                AtributoCambio.definicion_anterior["unidad_id"].as_string().in_(unit_ids_as_text),
                AtributoCambio.definicion_posterior["unidad_id"].as_string().in_(unit_ids_as_text),
            )
        )
        snapshots = session.exec(
            snapshot_statement.execution_options(
                **{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True}
            )
        ).all()
        for snapshot in snapshots:
            referenced_units = {
                UUID(str(definition["unidad_id"]))
                for definition in (
                    snapshot.definicion_anterior,
                    snapshot.definicion_posterior,
                )
                if definition.get("unidad_id") is not None
            } & unit_ids
            for unit_id in referenced_units:
                usage[unit_id]["snapshots_historicos"] += 1
        return usage

    def get(self, session: Session, item_id: UUID, *, lock: bool = False) -> Unidad | None:
        statement = (
            select(Unidad)
            .where(Unidad.id == item_id)
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        )
        if lock:
            statement = statement.with_for_update()
        return session.exec(statement).first()

    def list_units(
        self,
        session: Session,
        *,
        only_active: bool = True,
        limit: int = 50,
        offset: int = 0,
        q: str | None = None,
        magnitud_codigo: str | None = None,
    ) -> tuple[list[Unidad], int]:
        statement = select(Unidad).execution_options(
            **{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True}
        )
        if only_active:
            statement = statement.where(col(Unidad.activo).is_(True))
        if magnitud_codigo:
            statement = statement.where(Unidad.magnitud_codigo == magnitud_codigo)
        if q and q.strip():
            term = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{term}%"
            statement = statement.where(
                or_(
                    col(Unidad.codigo).ilike(pattern, escape="\\"),
                    col(Unidad.nombre).ilike(pattern, escape="\\"),
                    col(Unidad.simbolo).ilike(pattern, escape="\\"),
                )
            )
        count_statement = select(func.count()).select_from(statement.subquery())
        count_statement = count_statement.execution_options(
            **{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True}
        )
        total = int(session.execute(count_statement).scalar_one())
        statement = statement.order_by(
            func.lower(func.trim(col(Unidad.nombre))), col(Unidad.id)
        )
        items = list(session.exec(statement.offset(offset).limit(limit)).all())
        return items, total

    def _raise_integrity(self, error: IntegrityError) -> None:
        original = str(getattr(error, "orig", error)).lower()
        diagnostic = getattr(getattr(error, "orig", None), "diag", None)
        constraint = getattr(diagnostic, "constraint_name", None)
        if (
            constraint == "uq_tbl_unidad_codigo_normalizado"
            or "tbl_unidad.codigo" in original
            or "uq_tbl_unidad_codigo_normalizado" in original
        ):
            raise HTTPException(
                status_code=409,
                detail={"code": "UNIT_DUPLICATE_CODE", "message": "El código de unidad ya existe"},
            ) from error
        if (
            constraint == "uq_tbl_unidad_simbolo_exacto"
            or "tbl_unidad.simbolo" in original
            or "uq_tbl_unidad_simbolo_exacto" in original
        ):
            raise HTTPException(
                status_code=409,
                detail={"code": "UNIT_DUPLICATE_SYMBOL", "message": "El símbolo de unidad ya existe"},
            ) from error
        super()._raise_integrity(error)
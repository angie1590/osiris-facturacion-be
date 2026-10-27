from __future__ import annotations

from typing import Any, NoReturn
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from osiris.core.audit import record_domain_change
from osiris.modules.common.unidad.entity import Unidad
from osiris.modules.common.unidad.models import (
    UnidadCreate,
    UnidadRead,
    UnidadUpdate,
    UnidadUsoRead,
)
from osiris.modules.common.unidad.repository import UnidadRepository
from osiris.utils.pagination import PaginationMeta, build_pagination_meta


class UnidadService:
    def __init__(self) -> None:
        self.repo = UnidadRepository()

    @staticmethod
    def _snapshot(unidad: Unidad) -> dict[str, Any]:
        return unidad.model_dump(mode="json")

    @staticmethod
    def _protected() -> HTTPException:
        return HTTPException(
            status_code=409,
            detail={"code": "UNIT_PROTECTED", "message": "Las unidades del sistema están protegidas"},
        )

    @staticmethod
    def _in_use(usage: UnidadUsoRead) -> HTTPException:
        return HTTPException(
            status_code=409,
            detail={
                "code": "UNIT_IN_USE",
                "message": "La unidad está referenciada por atributos o snapshots históricos.",
                "conteos": usage.model_dump(),
                "acciones_permitidas": [],
            },
        )

    @staticmethod
    def _finish(session: Session, error: Exception) -> NoReturn:
        session.rollback()
        if isinstance(error, IntegrityError):
            UnidadRepository()._raise_integrity(error)
        raise error

    def list_paginated(
        self,
        session: Session,
        *,
        only_active: bool = True,
        limit: int = 50,
        offset: int = 0,
        q: str | None = None,
        magnitud_codigo: str | None = None,
    ) -> tuple[list[UnidadRead], PaginationMeta]:
        items, total = self.repo.list_units(
            session,
            only_active=only_active,
            limit=limit,
            offset=offset,
            q=q,
            magnitud_codigo=magnitud_codigo,
        )
        usage = self.repo.usage_for_units(session, {item.id for item in items})
        return (
            [
                self.to_read(item, usage[item.id])
                for item in items
            ],
            build_pagination_meta(total=total, limit=limit, offset=offset),
        )

    @staticmethod
    def to_read(
        unidad: Unidad, usage: dict[str, int] | None = None
    ) -> UnidadRead:
        return UnidadRead.model_validate(
            {**unidad.model_dump(), "uso": usage or {}},
        )

    def usage(self, session: Session, unidad: Unidad) -> UnidadUsoRead:
        return UnidadUsoRead.model_validate(
            self.repo.usage_for_units(session, {unidad.id})[unidad.id]
        )

    def get(self, session: Session, item_id: UUID) -> Unidad | None:
        return self.repo.get(session, item_id)

    def create(self, session: Session, payload: UnidadCreate) -> Unidad:
        try:
            unidad = Unidad(**payload.model_dump(exclude_unset=True))
            session.add(unidad)
            session.flush()
            record_domain_change(
                session,
                entity=Unidad.__tablename__,
                entity_id=unidad.id,
                action="CREATE_UNIT",
                before={},
                after=self._snapshot(unidad),
            )
            session.commit()
            session.refresh(unidad)
            return unidad
        except Exception as error:
            self._finish(session, error)

    def update(
        self, session: Session, item_id: UUID, payload: UnidadUpdate
    ) -> Unidad | None:
        try:
            unidad = self.repo.get(session, item_id, lock=True)
            if unidad is None:
                return None
            if unidad.es_sistema:
                raise self._protected()
            if not unidad.activo:
                raise HTTPException(
                    status_code=409,
                    detail={"code": "UNIT_INACTIVE", "message": "La unidad está inactiva"},
                )
            changes = payload.model_dump(exclude_unset=True)
            usage = self.usage(session, unidad)
            semantic_fields = {"codigo", "simbolo", "magnitud_codigo"}
            semantic_change = any(
                getattr(unidad, field) != changes[field]
                for field in semantic_fields
                if field in changes
            )
            if semantic_change and any(usage.model_dump().values()):
                raise self._in_use(usage)
            before = self._snapshot(unidad)
            for field, value in changes.items():
                setattr(unidad, field, value)
            session.add(unidad)
            session.flush()
            record_domain_change(
                session,
                entity=Unidad.__tablename__,
                entity_id=unidad.id,
                action="UPDATE_UNIT",
                before=before,
                after=self._snapshot(unidad),
            )
            session.commit()
            session.refresh(unidad)
            return unidad
        except Exception as error:
            self._finish(session, error)

    def deactivate(self, session: Session, item_id: UUID) -> Unidad | None:
        try:
            unidad = self.repo.get(session, item_id, lock=True)
            if unidad is None:
                return None
            if unidad.es_sistema:
                raise self._protected()
            if not unidad.activo:
                return unidad
            usage = self.usage(session, unidad)
            if any(usage.model_dump().values()):
                raise self._in_use(usage)
            before = self._snapshot(unidad)
            unidad.activo = False
            session.add(unidad)
            session.flush()
            record_domain_change(
                session,
                entity=Unidad.__tablename__,
                entity_id=unidad.id,
                action="DEACTIVATE_UNIT",
                before=before,
                after=self._snapshot(unidad),
            )
            session.commit()
            session.refresh(unidad)
            return unidad
        except Exception as error:
            self._finish(session, error)

    def reactivate(self, session: Session, item_id: UUID) -> Unidad | None:
        try:
            unidad = self.repo.get(session, item_id, lock=True)
            if unidad is None:
                return None
            if unidad.es_sistema:
                raise self._protected()
            if unidad.activo:
                return unidad
            before = self._snapshot(unidad)
            unidad.activo = True
            session.add(unidad)
            session.flush()
            record_domain_change(
                session,
                entity=Unidad.__tablename__,
                entity_id=unidad.id,
                action="REACTIVATE_UNIT",
                before=before,
                after=self._snapshot(unidad),
            )
            session.commit()
            session.refresh(unidad)
            return unidad
        except Exception as error:
            self._finish(session, error)
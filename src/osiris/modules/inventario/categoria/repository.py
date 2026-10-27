from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from osiris.domain.repository import BaseRepository
from .entity import Categoria


class CategoriaRepository(BaseRepository):
    model = Categoria

    @staticmethod
    def default_protected() -> HTTPException:
        return HTTPException(
            status_code=409,
            detail={
                "code": "CATEGORY_DEFAULT_PROTECTED",
                "message": "Sin clasificar es una categoria temporal administrada por el sistema.",
                "conteos": {},
                "acciones_permitidas": [],
            },
        )

    @staticmethod
    def inactive_parent() -> HTTPException:
        return HTTPException(
            status_code=409,
            detail={
                "code": "CATEGORY_PARENT_INACTIVE",
                "message": "La categoria padre debe estar activa.",
                "conteos": {},
                "acciones_permitidas": [],
            },
        )

    @staticmethod
    def hierarchy_cycle(message: str) -> HTTPException:
        return HTTPException(
            status_code=409,
            detail={
                "code": "CATEGORY_CYCLE",
                "message": message,
                "conteos": {},
                "acciones_permitidas": [],
            },
        )

    @staticmethod
    def duplicate_name() -> HTTPException:
        return HTTPException(
            status_code=409,
            detail={
                "code": "CATEGORY_DUPLICATE_NAME",
                "message": "Ya existe una categoria activa o inactiva con ese nombre "
                "dentro de la misma categoria padre. Reactiva o renombra la existente.",
                "acciones_permitidas": ["reactivar", "renombrar"],
                "conteos": {},
            },
        )

    def _raise_integrity(self, error: IntegrityError) -> None:
        constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
        indices = (
            "uq_tbl_categoria_root_nombre_historical",
            "uq_tbl_categoria_child_nombre_historical",
        )
        if constraint in indices or any(name in str(error.orig) for name in indices):
            raise self.duplicate_name() from error
        super()._raise_integrity(error)

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from osiris.domain.repository import BaseRepository
from .entity import Atributo

class AtributoRepository(BaseRepository):
    model = Atributo

    @staticmethod
    def duplicate_code() -> HTTPException:
        return HTTPException(
            status_code=409,
            detail={
                "code": "ATTRIBUTE_DUPLICATE_CODE",
                "message": "Ya existe un atributo activo o inactivo con ese codigo.",
                "conteos": {},
                "acciones_permitidas": [],
            },
        )

    def _raise_integrity(self, error: IntegrityError) -> None:
        constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
        if constraint == "uq_tbl_atributo_codigo_normalizado" or (
            "uq_tbl_atributo_codigo_normalizado" in str(error.orig)
        ):
            raise self.duplicate_code() from error
        if constraint == "uq_tbl_atributo_nombre_activo_normalized" or (
            "uq_tbl_atributo_nombre_activo_normalized" in str(error.orig)
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "ATTRIBUTE_DUPLICATE_NAME",
                    "message": "Ya existe un atributo activo con ese nombre.",
                    "conteos": {},
                    "acciones_permitidas": [],
                },
            ) from error
        super()._raise_integrity(error)

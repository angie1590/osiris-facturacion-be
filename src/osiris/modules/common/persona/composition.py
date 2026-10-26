from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException
from pydantic import model_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from osiris.core.audit_context import get_current_user_id
from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.core.directory_permissions import (
    require_directory_permission as requiere_permiso,
)
from osiris.domain.base_models import BaseOSModel
from osiris.modules.common.persona.entity import Persona
from osiris.modules.common.persona.models import PersonaCreate
from osiris.modules.common.persona.repository import PersonaRepository
from osiris.utils.validacion_identificacion import ValidacionCedulaRucService


class PersonaReference(BaseOSModel):
    persona_id: UUID | None = None
    persona_nueva: PersonaCreate | None = None

    @model_validator(mode="after")
    def validate_reference(self) -> PersonaReference:
        if (self.persona_id is None) == (self.persona_nueva is None):
            raise ValueError("Enviar exactamente persona_id o persona_nueva")
        return self


def _identity_conflict(error: Exception) -> bool:
    cause = error if isinstance(error, IntegrityError) else error.__cause__
    if not isinstance(cause, IntegrityError):
        return False
    original = cause.orig
    constraint = getattr(getattr(original, "diag", None), "constraint_name", None)
    sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
    if sqlstate is not None:
        return sqlstate == "23505" and constraint in {
            "ix_tbl_persona_identificacion",
            "uq_tbl_persona_identificacion",
            "uq_tbl_persona_identificacion_normalizada",
        }
    return "UNIQUE constraint failed" in str(original) and (
        "tbl_persona.identificacion" in str(original)
        or "uq_tbl_persona_identificacion_normalizada" in str(original)
    )


def resolve_persona(
    session: Session,
    data: dict[str, Any],
    *,
    id_field: str = "persona_id",
    new_field: str = "persona_nueva",
    required: bool = True,
) -> dict[str, Any]:
    payload = data.copy()
    person_id = payload.get(id_field)
    draft = payload.pop(new_field, None)
    if person_id is not None and draft is not None:
        raise HTTPException(
            status_code=422, detail=f"Enviar solo {id_field} o {new_field}"
        )
    if person_id is None and draft is None:
        if not required:
            payload.pop(id_field, None)
            return payload
        raise HTTPException(status_code=422, detail=f"Enviar {id_field} o {new_field}")
    actor = get_current_user_id()
    if actor:
        requiere_permiso(session, UUID(actor), "PERSONAS", "leer")
    if person_id is not None:
        statement = select(Persona).where(Persona.id == person_id)
    else:
        draft = PersonaCreate.model_validate(draft).model_dump(exclude_unset=True)
        identification = ValidacionCedulaRucService.normalizar_identificacion(
            draft["identificacion"]
        )
        draft["identificacion"] = identification
        statement = select(Persona).where(
            func.upper(func.trim(Persona.identificacion)) == identification
        )
    statement = statement.execution_options(
        **{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True}
    ).with_for_update()
    person = session.exec(statement).first()
    if person is None:
        if draft is None:
            raise HTTPException(status_code=404, detail="Persona no encontrada")
        if actor:
            requiere_permiso(session, UUID(actor), "PERSONAS", "crear")
        draft["usuario_auditoria"] = actor or draft.get("usuario_auditoria") or "system"
        try:
            with session.begin_nested():
                person = PersonaRepository().create(session, draft)
        except Exception as error:
            if not _identity_conflict(error):
                raise
            person = session.exec(statement).first()
            if person is None:
                raise
    if person.activo is False:
        raise HTTPException(
            status_code=409,
            detail={
                "mensaje": "Persona inactiva; requiere reactivacion explicita",
                "persona_id": str(person.id),
                "accion": "reactivar",
            },
        )
    payload[id_field] = person.id
    return payload

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException

from osiris.core.audit_context import get_current_company_id


def get_selected_company_id() -> UUID | None:
    raw_company_id = get_current_company_id()
    if not raw_company_id:
        return None
    try:
        return UUID(str(raw_company_id))
    except (TypeError, ValueError):
        raise HTTPException(status_code=403, detail="Empresa seleccionada inválida en el contexto de sesión.") from None


def resolve_company_scope(*, requested_company_id: UUID | None = None) -> UUID | None:
    selected_company_id = get_selected_company_id()
    if selected_company_id is None:
        return requested_company_id
    if requested_company_id is not None and requested_company_id != selected_company_id:
        raise HTTPException(
            status_code=403,
            detail="La empresa solicitada no coincide con la empresa seleccionada en la sesión.",
        )
    return selected_company_id


def ensure_entity_belongs_to_selected_company(entity_company_id: UUID | None) -> None:
    selected_company_id = get_selected_company_id()
    if selected_company_id is None:
        return
    if entity_company_id is None:
        raise HTTPException(status_code=403, detail="El recurso no está asociado a la empresa seleccionada.")
    if entity_company_id != selected_company_id:
        raise HTTPException(status_code=403, detail="No autorizado para operar recursos de otra empresa.")

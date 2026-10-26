# src/osiris/modules/common/persona/service.py
from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, select
from osiris.core.audit_context import get_current_user_id
from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.core.permisos import verificar_permiso
from osiris.domain.service import BaseService
from osiris.utils.validacion_identificacion import ValidacionCedulaRucService
from .entity import Persona
from .repository import PersonaRepository


class PersonaService(BaseService[Persona]):
    def __init__(self, repo: PersonaRepository | None = None) -> None:
        self.repo = repo or PersonaRepository()

    def create(self, session: Session, data: Any, *, commit: bool = True) -> Persona:
        payload = self._ensure_dict(data).copy()
        actor = get_current_user_id()
        payload["usuario_auditoria"] = actor or payload.get("usuario_auditoria") or "system"
        payload["identificacion"] = ValidacionCedulaRucService.normalizar_identificacion(payload["identificacion"])
        return super().create(session, payload, commit=commit)

    def update(self, session: Session, item_id: UUID, data: Any, *, commit: bool = True) -> Persona | None:
        payload = self._ensure_dict(data).copy()
        allowed = {"identificacion", "tipo_identificacion", "nombre", "apellido", "direccion", "telefono", "ciudad", "email", "usuario_auditoria"}
        if payload.keys() - allowed:
            raise HTTPException(status_code=422, detail="Campos no editables; use acciones explicitas de ciclo de vida")
        if "identificacion" in payload or "tipo_identificacion" in payload:
            if not payload.get("identificacion") or not payload.get("tipo_identificacion"):
                raise HTTPException(status_code=422, detail="Debes enviar identificacion y tipo_identificacion juntos")
            payload["identificacion"] = ValidacionCedulaRucService.normalizar_identificacion(payload["identificacion"])
        return super().update(session, item_id, payload, commit=commit)

    def _history(self, session: Session, item_id: UUID, *, lock: bool = False) -> Persona:
        statement = select(Persona).where(Persona.id == item_id).execution_options(
            **{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True}
        )
        if lock:
            statement = statement.with_for_update()
        person = session.exec(statement).first()
        if person is None:
            raise HTTPException(status_code=404, detail="Persona no encontrada")
        return person

    def get(self, session: Session, item_id: UUID) -> Persona:
        return self._history(session, item_id)

    def links(self, session: Session, item_id: UUID, *, filter_permissions: bool = True) -> dict[str, Any]:
        from osiris.modules.common.cliente.entity import Cliente
        from osiris.modules.common.proveedor_persona.entity import ProveedorPersona
        from osiris.modules.common.empleado.entity import Empleado
        from osiris.modules.common.usuario.entity import Usuario
        from osiris.modules.common.proveedor_sociedad.entity import ProveedorSociedad

        self._history(session, item_id)
        actor = get_current_user_id()
        result: dict[str, Any] = {"persona_id": str(item_id), "dependencias_activas": []}
        roles: tuple[tuple[str, str, Any, str, str], ...] = (
            ("cliente", "CLIENTES", Cliente, "persona_id", "Cliente"),
            ("proveedor_persona", "PROVEEDORES_PERSONA", ProveedorPersona, "persona_id", "Proveedor Persona"),
            ("empleado", "EMPLEADOS", Empleado, "persona_id", "Empleado"),
            ("usuario", "USUARIOS", Usuario, "persona_id", "Usuario"),
            ("proveedores_sociedad", "PROVEEDORES_SOCIEDAD", ProveedorSociedad, "persona_contacto_id", "Contacto de Sociedad"),
        )
        for key, module, model, field, name in roles:
            visible = not filter_permissions or not actor or verificar_permiso(session, UUID(actor), module, "leer")
            entries = session.exec(select(model).where(getattr(model, field) == item_id).execution_options(
                **{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True}
            )).all()
            summaries: list[dict[str, Any]] = []
            for entry in entries:
                if visible:
                    summary = {"id": str(entry.id), "activo": entry.activo}
                    if key == "proveedores_sociedad":
                        summary["razon_social"] = entry.razon_social
                    summaries.append(summary)
                if entry.activo:
                    result["dependencias_activas"].append({
                        "recurso": key, "id": str(entry.id) if visible else None,
                        "nombre": entry.razon_social if visible and key == "proveedores_sociedad" else name,
                    })
            result[key] = summaries if key == "proveedores_sociedad" else (summaries[0] if summaries else None)
        return result

    def delete(self, session: Session, item_id: UUID, *, commit: bool = True) -> bool:
        try:
            person = self._history(session, item_id, lock=True)
            links = self.links(session, item_id)
            if links["dependencias_activas"]:
                raise HTTPException(status_code=409, detail={
                    "mensaje": "No se puede desactivar Persona porque tiene dependencias activas",
                    "dependencias_activas": links["dependencias_activas"],
                })
            result = self.repo.delete(session, person)
            if commit:
                session.commit()
            return cast(bool, result)
        except Exception as error:
            self._handle_transaction_error(session, error)

    def reactivate(self, session: Session, item_id: UUID, *, commit: bool = True) -> Persona:
        try:
            person = self._history(session, item_id, lock=True)
            from .models import PersonaCreate

            fields = PersonaCreate.model_fields
            validated = PersonaCreate.model_validate({key: value for key, value in person.model_dump().items() if key in fields})
            person.identificacion = validated.identificacion
            result = self.repo.update(session, person, {"activo": True, "usuario_auditoria": get_current_user_id() or "system"})
            if commit:
                session.commit()
                session.refresh(result)
            return cast(Persona, result)
        except Exception as error:
            self._handle_transaction_error(session, error)

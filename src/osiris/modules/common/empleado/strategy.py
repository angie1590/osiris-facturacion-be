# src/osiris/modules/common/empleado/strategy.py
from __future__ import annotations

from typing import Any, Dict
from uuid import UUID
from sqlmodel import Session, select
from fastapi import HTTPException

from osiris.modules.common.usuario.service import UsuarioService
from osiris.modules.common.rol.entity import Rol  # <-- importar Rol para validar FK


class EmpleadoCrearUsuarioStrategy:
    """
    Al crear un Empleado, crear también el Usuario asociado.
    Valida que el rol exista y esté activo ANTES de crear el usuario.
    """

    def __init__(self, usuario_service: UsuarioService | None = None) -> None:
        self.usuario_service = usuario_service or UsuarioService()

    def create_user_for_persona(
        self,
        session: Session,
        *,
        persona_id: UUID,
        usuario_payload: Dict[str, Any],
        commit: bool = True,
    ):
        if not usuario_payload:
            raise HTTPException(status_code=400, detail="Debe enviar el bloque 'usuario' con username, password y rol_id")

        # Normalizar payload
        if hasattr(usuario_payload, "model_dump"):
            usuario_payload = usuario_payload.model_dump(exclude_unset=True)

        required = ("username", "password", "rol_id")
        missing = [k for k in required if not usuario_payload.get(k)]
        if missing:
            raise HTTPException(status_code=400, detail=f"Faltan campos requeridos en usuario: {', '.join(missing)}")

        # ✅ Validar FK rol_id (existente y activo) ANTES de crear el usuario
        rol_id = usuario_payload.get("rol_id")
        ok_rol = session.exec(
            select(Rol.id).where(Rol.id == rol_id, getattr(Rol, "activo", True) == True)  # noqa: E712
        ).first()
        if not ok_rol:
            raise HTTPException(status_code=404, detail=f"Rol {rol_id} no encontrado o inactivo")

        # Forzar persona_id del empleado
        usuario_payload["persona_id"] = persona_id

        # Crear el usuario (UsuarioService también valida FKs vía fk_models)
        user = self.usuario_service.create(session, usuario_payload, commit=commit)
        return user

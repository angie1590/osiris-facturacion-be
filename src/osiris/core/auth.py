from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import func
from sqlmodel import Session, select

from osiris.core.db import get_session
from osiris.core.errors import NotFoundError
from osiris.core.security import verify_password
from osiris.core.settings import get_settings
from osiris.modules.common.persona.entity import Persona
from osiris.modules.common.rol.entity import Rol
from osiris.modules.common.usuario.entity import Usuario

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def create_token(subject: UUID, token_type: str, expires: timedelta) -> str:
    settings = get_settings()
    payload = {
        "sub": str(subject),
        "type": token_type,
        "iat": datetime.now(timezone.utc).timestamp(),
        "exp": datetime.now(timezone.utc) + expires,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def is_token_invalidated(payload: dict[str, Any], usuario: Usuario) -> bool:
    issued_at = payload.get("iat")
    if not usuario.sesion_invalidada_en or not isinstance(issued_at, (int, float)):
        return False
    invalidated_at = usuario.sesion_invalidada_en.replace(tzinfo=timezone.utc)
    return datetime.fromtimestamp(issued_at, timezone.utc) <= invalidated_at


def get_current_usuario(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> Usuario:
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise JWTError
        user_id = UUID(str(payload["sub"]))
    except (JWTError, KeyError, ValueError):
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    usuario = session.get(Usuario, user_id)
    if not usuario or not usuario.activo:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Usuario inactivo")
    if is_token_invalidated(payload, usuario):
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Sesión invalidada")
    return usuario


def authenticate(session: Session, username: str, password: str) -> Usuario | None:
    usuario = session.exec(
        select(Usuario).where(func.lower(Usuario.username) == username.strip().lower())
    ).first()
    if not usuario or not usuario.activo or not verify_password(password, usuario.password_hash):
        return None
    return usuario


def verify_approval_code(usuario: Usuario, approval_code: str) -> bool:
    if not usuario.codigo_aprobacion_hash:
        return False
    from osiris.core.security import verify_password

    return verify_password(approval_code, usuario.codigo_aprobacion_hash)


def user_response(session: Session, usuario: Usuario) -> dict[str, Any]:
    persona = session.get(Persona, usuario.persona_id)
    rol = session.get(Rol, usuario.rol_id)
    full_name = " ".join(filter(None, [persona.nombre if persona else "", persona.apellido if persona else ""]))
    role_name = (rol.nombre.lower() if rol else "operator").strip()
    role = {
        "administrador": "admin",
        "admin": "admin",
        "supervisor": "supervisor",
        "jefe de almacén": "supervisor",
        "jefe de almacen": "supervisor",
        "operador": "operator",
        "vendedor": "operator",
        "operator": "operator",
    }.get(role_name, "operator")
    return {
        "id": str(usuario.id),
        "username": usuario.username,
        "full_name": full_name or usuario.username,
        "role": role,
        "is_active": usuario.activo,
        "require_password_change": usuario.requiere_cambio_password,
        "has_approval_code": usuario.codigo_aprobacion_hash is not None,
    }
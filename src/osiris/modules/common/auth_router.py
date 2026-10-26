from __future__ import annotations

from datetime import timedelta
from uuid import UUID
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlmodel import Session

from osiris.core.auth import (
    authenticate,
    create_token,
    decode_token,
    get_current_usuario,
    is_token_invalidated,
    user_response,
    verify_approval_code,
)
from osiris.core.db import get_session
from osiris.core.settings import get_settings
from osiris.modules.common.usuario.entity import Usuario
from osiris.modules.common.usuario.service import UsuarioService
from osiris.core.security import PASSWORD_MIN_LENGTH

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticación"])
service = UsuarioService()


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str | None = None
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH)


class ApprovalCodeRequest(BaseModel):
    approval_code: str = Field(pattern=r"^\d{4}$")


@router.post("/login")
def login(
    form: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)
) -> dict[str, Any]:
    usuario = authenticate(session, form.username, form.password)
    if not usuario:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    settings = get_settings()
    return {
        "access_token": create_token(
            usuario.id,
            "access",
            timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        ),
        "refresh_token": create_token(
            usuario.id, "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        ),
        "token_type": "bearer",
        "require_password_change": usuario.requiere_cambio_password,
        "session_timeout_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    }


@router.post("/refresh")
def refresh(
    body: RefreshRequest, session: Session = Depends(get_session)
) -> dict[str, Any]:
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError
        usuario = session.get(Usuario, UUID(str(payload["sub"])))
    except Exception as exc:
        raise HTTPException(
            status_code=401, detail="Refresh token inválido o expirado"
        ) from exc
    if not usuario or not usuario.activo:
        raise HTTPException(status_code=401, detail="Usuario inactivo")
    if is_token_invalidated(payload, usuario):
        raise HTTPException(status_code=401, detail="Sesión invalidada")
    settings = get_settings()
    return {
        "access_token": create_token(
            usuario.id,
            "access",
            timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        ),
        "refresh_token": create_token(
            usuario.id, "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        ),
        "token_type": "bearer",
        "session_timeout_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    }


@router.get("/me")
def me(
    usuario: Usuario = Depends(get_current_usuario),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return user_response(session, usuario)


@router.post("/logout")
def logout(
    usuario: Usuario = Depends(get_current_usuario),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    service.invalidate_session(session, usuario)
    return {"message": "Logged out successfully"}


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    usuario: Usuario = Depends(get_current_usuario),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    service.change_password(
        session,
        usuario,
        new_password=body.new_password,
        current_password=body.current_password,
    )
    return {"message": "Password changed successfully"}


@router.post("/approval-code")
def set_approval_code(
    body: ApprovalCodeRequest,
    usuario: Usuario = Depends(get_current_usuario),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    service.set_approval_code(session, usuario, body.approval_code)
    return {"message": "Approval code saved successfully"}


@router.post("/approval-code/verify")
def verify_approval_code_endpoint(
    body: ApprovalCodeRequest,
    usuario: Usuario = Depends(get_current_usuario),
) -> dict[str, bool]:
    if not verify_approval_code(usuario, body.approval_code):
        raise HTTPException(status_code=401, detail="Approval code inválido")
    return {"valid": True}

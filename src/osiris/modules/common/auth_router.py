from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlmodel import Session

from osiris.core.auth import authenticate, create_token, decode_token, get_current_usuario, user_response
from osiris.core.db import get_session
from osiris.core.settings import get_settings
from osiris.modules.common.usuario.entity import Usuario

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticación"])


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str | None = None
    new_password: str = Field(min_length=8)


@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    usuario = authenticate(session, form.username, form.password)
    if not usuario:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    settings = get_settings()
    return {
        "access_token": create_token(usuario.id, "access", timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)),
        "refresh_token": create_token(usuario.id, "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)),
        "token_type": "bearer",
        "require_password_change": usuario.requiere_cambio_password,
        "session_timeout_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    }


@router.post("/refresh")
def refresh(body: RefreshRequest, session: Session = Depends(get_session)):
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError
        usuario = session.get(Usuario, UUID(str(payload["sub"])))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Refresh token inválido o expirado") from exc
    if not usuario or not usuario.activo:
        raise HTTPException(status_code=401, detail="Usuario inactivo")
    settings = get_settings()
    return {
        "access_token": create_token(usuario.id, "access", timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)),
        "refresh_token": create_token(usuario.id, "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)),
        "token_type": "bearer",
        "session_timeout_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    }


@router.get("/me")
def me(usuario=Depends(get_current_usuario), session: Session = Depends(get_session)):
    return user_response(session, usuario)


@router.post("/logout")
def logout(usuario=Depends(get_current_usuario)):
    return {"message": "Logged out successfully"}


@router.post("/change-password")
def change_password(body: ChangePasswordRequest, usuario=Depends(get_current_usuario), session: Session = Depends(get_session)):
    if body.current_password and not authenticate(session, usuario.username, body.current_password):
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")
    from osiris.core.security import hash_password

    usuario.password_hash = hash_password(body.new_password)
    usuario.requiere_cambio_password = False
    session.add(usuario)
    session.commit()
    return {"message": "Password changed successfully"}
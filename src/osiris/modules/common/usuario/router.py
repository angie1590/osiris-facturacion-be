from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.domain.schemas import PaginatedResponse
from osiris.modules.common.rol_modulo_permiso.models import ModuloPermisoRead
from osiris.modules.common.rol_modulo_permiso.service import RolModuloPermisoService
from osiris.modules.common.usuario.models import (
    UsuarioCreate,
    UsuarioRead,
    UsuarioResetPasswordRequest,
    UsuarioResetPasswordResponse,
    UsuarioUpdate,
    UsuarioVerifyPasswordRequest,
)
from osiris.modules.common.usuario.service import UsuarioService


router = APIRouter(prefix="/api/v1/usuarios", tags=["Usuarios"])
service = UsuarioService()
permiso_service = RolModuloPermisoService()


@router.get("", response_model=PaginatedResponse[UsuarioRead])
def list_usuarios(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    only_active: bool = Query(True),
    session: Session = Depends(get_session),
):
    items, meta = service.list_paginated(session, only_active=only_active, limit=limit, offset=offset)
    return {"items": items, "meta": meta}


@router.get("/{item_id}", response_model=UsuarioRead)
def get_usuario(item_id: UUID = Path(...), session: Session = Depends(get_session)):
    obj = service.get(session, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"Usuario {item_id} not found")
    return obj


@router.post("", response_model=UsuarioRead, status_code=status.HTTP_201_CREATED)
def create_usuario(payload: UsuarioCreate = Body(...), session: Session = Depends(get_session)):
    return service.create(session, payload.model_dump(exclude_unset=True))


@router.put("/{item_id}", response_model=UsuarioRead)
def update_usuario(
    item_id: UUID = Path(...),
    payload: UsuarioUpdate = Body(...),
    session: Session = Depends(get_session),
):
    updated = service.update(session, item_id, payload.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Usuario {item_id} not found")
    return updated


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_usuario(item_id: UUID = Path(...), session: Session = Depends(get_session)):
    ok = service.delete(session, item_id)
    if ok is None:
        raise HTTPException(status_code=404, detail=f"Usuario {item_id} not found")


@router.get("/{usuario_id}/permisos", response_model=List[ModuloPermisoRead], tags=["Usuarios", "Permisos"])
def obtener_permisos_usuario(
    usuario_id: UUID = Path(..., description="ID del usuario"),
    session: Session = Depends(get_session),
):
    usuario = service.get(session, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    permisos = permiso_service.obtener_permisos_por_rol(session, usuario.rol_id)
    return permisos


@router.get("/{usuario_id}/menu", response_model=List[ModuloPermisoRead], tags=["Usuarios", "Permisos"])
def obtener_menu_usuario(
    usuario_id: UUID = Path(..., description="ID del usuario"),
    session: Session = Depends(get_session),
):
    usuario = service.get(session, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    menu = permiso_service.obtener_menu_por_rol(session, usuario.rol_id)
    return menu


@router.post("/{usuario_id}/reset-password", response_model=UsuarioResetPasswordResponse)
def reset_password_usuario(
    usuario_id: UUID = Path(..., description="ID del usuario"),
    payload: UsuarioResetPasswordRequest | None = Body(None),
    session: Session = Depends(get_session),
):
    updated, temp_password = service.reset_password(
        session,
        usuario_id,
        usuario_auditoria=payload.usuario_auditoria if payload else None,
    )
    return UsuarioResetPasswordResponse(
        usuario_id=updated.id,
        username=updated.username,
        password_temporal=temp_password,
        requiere_cambio_password=updated.requiere_cambio_password,
    )


@router.post("/{usuario_id}/verify-password", response_model=bool)
def verify_password_usuario(
    usuario_id: UUID = Path(..., description="ID del usuario"),
    payload: UsuarioVerifyPasswordRequest = Body(...),
    session: Session = Depends(get_session),
):
    return service.verify_password(session, usuario_id, payload.password)

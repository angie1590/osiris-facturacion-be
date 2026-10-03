from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.core.auth import require_roles
from osiris.modules.common.catalogo.models import (
    CatalogoCreate,
    CatalogoRead,
    CatalogoUpdate,
    CatalogoValorCreate,
    CatalogoValorRead,
    CatalogoValorUpdate,
)
from osiris.modules.common.catalogo.service import CatalogoService


router = APIRouter(prefix="/api/v1/catalogos", tags=["Catálogos"])
service = CatalogoService()


@router.get("", response_model=list[CatalogoRead])
def listar_catalogos(session: Session = Depends(get_session)):
    return service.list(session)


@router.post("", response_model=CatalogoRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_roles("admin", "supervisor"))])
def crear_catalogo(payload: CatalogoCreate, session: Session = Depends(get_session)):
    return service.create(session, name=payload.name, description=payload.description)


@router.patch("/{catalog_id}", response_model=CatalogoRead, dependencies=[Depends(require_roles("admin", "supervisor"))])
def actualizar_catalogo(
    catalog_id: UUID,
    payload: CatalogoUpdate,
    session: Session = Depends(get_session),
):
    catalog = service.update(session, catalog_id, payload.model_dump(exclude_unset=True))
    if catalog is None:
        raise HTTPException(status_code=404, detail="Catálogo no encontrado.")
    return catalog


@router.delete("/{catalog_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_roles("admin", "supervisor"))])
def eliminar_catalogo(catalog_id: UUID, session: Session = Depends(get_session)):
    if service.delete(session, catalog_id) is None:
        raise HTTPException(status_code=404, detail="Catálogo no encontrado.")


@router.get("/{catalog_id}/valores", response_model=list[CatalogoValorRead])
def listar_valores_catalogo(
    catalog_id: UUID,
    include_inactive: bool = Query(True),
    session: Session = Depends(get_session),
):
    return service.list_values(session, catalog_id, include_inactive=include_inactive)


@router.post("/{catalog_id}/valores", response_model=CatalogoValorRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_roles("admin", "supervisor"))])
def agregar_valor_catalogo(
    catalog_id: UUID,
    payload: CatalogoValorCreate,
    session: Session = Depends(get_session),
):
    return service.add_value(session, catalog_id, payload.value)


@router.patch("/{catalog_id}/valores/{value_id}", response_model=CatalogoValorRead, dependencies=[Depends(require_roles("admin", "supervisor"))])
def actualizar_valor_catalogo(
    catalog_id: UUID,
    value_id: UUID,
    payload: CatalogoValorUpdate,
    session: Session = Depends(get_session),
):
    value = service.update_value(session, catalog_id, value_id, payload.value)
    if value is None:
        raise HTTPException(status_code=404, detail="Valor de catálogo no encontrado.")
    return value


@router.post("/{catalog_id}/valores/{value_id}/deactivate", response_model=CatalogoValorRead, dependencies=[Depends(require_roles("admin", "supervisor"))])
def desactivar_valor_catalogo(catalog_id: UUID, value_id: UUID, session: Session = Depends(get_session)):
    value = service.toggle_value(session, catalog_id, value_id, active=False)
    if value is None:
        raise HTTPException(status_code=404, detail="Valor de catálogo no encontrado.")
    return value


@router.post("/{catalog_id}/valores/{value_id}/reactivate", response_model=CatalogoValorRead, dependencies=[Depends(require_roles("admin", "supervisor"))])
def reactivar_valor_catalogo(catalog_id: UUID, value_id: UUID, session: Session = Depends(get_session)):
    value = service.toggle_value(session, catalog_id, value_id, active=True)
    if value is None:
        raise HTTPException(status_code=404, detail="Valor de catálogo no encontrado.")
    return value
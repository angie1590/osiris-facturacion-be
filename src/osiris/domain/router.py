# src/osiris/domain/router.py
from typing import Any, Type
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Path, Body, HTTPException, status
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.domain.schemas import PaginatedResponse  # items + meta


def register_crud_routes(
    *,
    router: APIRouter,
    prefix: str,
    tags: list[str],
    model_read: Type[Any],     # usado en response_model (ignorar para linter)
    model_create: Type[Any],   # se usa para POST y PUT (full replace)
    model_update: Type[Any],   # si luego habilitas PATCH parcial
    service: Any,
) -> None:
    base_path = f"/{prefix}"

    # -------- LIST (paginado: items + meta)
    @router.get(base_path, response_model=PaginatedResponse[model_read], tags=tags)  # type: ignore[valid-type]
    def list_items(
        limit: int = Query(50, ge=1, le=1000, description="Máximo de registros a devolver"),
        offset: int = Query(0, ge=0, description="Número de registros a saltar"),
        only_active: bool = Query(True, description="Filtrar por activo=True/False"),
        session: Session = Depends(get_session),
    ):
        items, meta = service.list_paginated(
            session,
            only_active=only_active,
            limit=limit,
            offset=offset,
        )
        return {"items": items, "meta": meta}

    # -------- GET BY ID
    @router.get(f"{base_path}/{{item_id}}", response_model=model_read, tags=tags)  # type: ignore[valid-type]
    def get_item(
        item_id: UUID = Path(...),
        session: Session = Depends(get_session),
    ):
        obj = service.get(session, item_id)
        if not obj:
            singular = prefix[:-1].capitalize() if prefix.endswith("s") else prefix.capitalize()
            raise HTTPException(status_code=404, detail=f"{singular} {item_id} not found")
        return obj

    # -------- CREATE (201)  ← anotado con model_create para que OpenAPI muestre el esquema correcto
    @router.post(base_path, response_model=model_read, status_code=status.HTTP_201_CREATED, tags=tags)  # type: ignore[valid-type]
    def create_item(
        payload: model_create = Body(...),  # type: ignore[name-defined,valid-type]
        session: Session = Depends(get_session),
    ):
        return service.create(session, payload.model_dump(exclude_unset=True))

    # -------- UPDATE (PUT = full replace, mismo schema que create)
    @router.put(f"{base_path}/{{item_id}}", response_model=model_read, tags=tags)  # type: ignore[valid-type]
    def update_item(
        item_id: UUID = Path(...),
        payload: model_update = Body(...),  # type: ignore[name-defined,valid-type]
        session: Session = Depends(get_session),
    ):
        data = payload.model_dump(exclude_unset=True)
        updated = service.update(session, item_id, data)
        if updated is None:
            singular = prefix[:-1].capitalize() if prefix.endswith("s") else prefix.capitalize()
            raise HTTPException(status_code=404, detail=f"{singular} {item_id} not found")
        return updated

    # -------- DELETE (204 / 404)
    @router.delete(f"{base_path}/{{item_id}}", status_code=status.HTTP_204_NO_CONTENT, tags=tags)
    def delete_item(
        item_id: UUID = Path(...),
        session: Session = Depends(get_session),
    ):
        ok = service.delete(session, item_id)
        if ok is None:
            singular = prefix[:-1].capitalize() if prefix.endswith("s") else prefix.capitalize()
            raise HTTPException(status_code=404, detail=f"{singular} {item_id} not found")
        # 204 sin body

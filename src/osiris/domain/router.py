# src/osiris/domain/router.py
from typing import Any, Type
from enum import Enum
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Path, Body, HTTPException, status
from sqlmodel import Session
from pydantic import BaseModel

from osiris.core.db import get_session
from osiris.domain.schemas import PaginatedResponse  # items + meta


def register_crud_routes(
    *,
    router: APIRouter,
    prefix: str,
    tags: list[str],
    model_read: Type[BaseModel],
    model_create: Type[BaseModel],
    model_update: Type[BaseModel],
    service: Any,
) -> None:
    base_path = f"/{prefix}"
    route_tags: list[str | Enum] = list(tags)
    paginated_model = PaginatedResponse.__class_getitem__(model_read)

    # -------- LIST (paginado: items + meta)
    @router.get(base_path, response_model=paginated_model, tags=route_tags)
    def list_items(
        limit: int = Query(
            50, ge=1, le=1000, description="Máximo de registros a devolver"
        ),
        offset: int = Query(0, ge=0, description="Número de registros a saltar"),
        only_active: bool = Query(True, description="Filtrar por activo=True/False"),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        items, meta = service.list_paginated(
            session,
            only_active=only_active,
            limit=limit,
            offset=offset,
        )
        return {"items": items, "meta": meta}

    # -------- GET BY ID
    @router.get(f"{base_path}/{{item_id}}", response_model=model_read, tags=route_tags)
    def get_item(
        item_id: UUID = Path(...),
        session: Session = Depends(get_session),
    ) -> Any:
        obj = service.get(session, item_id)
        if not obj:
            singular = (
                prefix[:-1].capitalize()
                if prefix.endswith("s")
                else prefix.capitalize()
            )
            raise HTTPException(
                status_code=404, detail=f"{singular} {item_id} not found"
            )
        return obj

    # -------- CREATE (201)  ← anotado con model_create para que OpenAPI muestre el esquema correcto
    def create_item(
        payload: BaseModel = Body(...),
        session: Session = Depends(get_session),
    ) -> Any:
        return service.create(session, payload.model_dump(exclude_unset=True))

    create_item.__annotations__["payload"] = model_create
    router.add_api_route(
        base_path,
        create_item,
        response_model=model_read,
        status_code=status.HTTP_201_CREATED,
        tags=route_tags,
        methods=["POST"],
    )

    # -------- UPDATE (PUT = full replace, mismo schema que create)
    def update_item(
        item_id: UUID = Path(...),
        payload: BaseModel = Body(...),
        session: Session = Depends(get_session),
    ) -> Any:
        data = payload.model_dump(exclude_unset=True)
        updated = service.update(session, item_id, data)
        if updated is None:
            singular = (
                prefix[:-1].capitalize()
                if prefix.endswith("s")
                else prefix.capitalize()
            )
            raise HTTPException(
                status_code=404, detail=f"{singular} {item_id} not found"
            )
        return updated

    update_item.__annotations__["payload"] = model_update
    router.add_api_route(
        f"{base_path}/{{item_id}}",
        update_item,
        response_model=model_read,
        tags=route_tags,
        methods=["PUT"],
    )

    # -------- DELETE (204 / 404)
    @router.delete(
        f"{base_path}/{{item_id}}",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=route_tags,
    )
    def delete_item(
        item_id: UUID = Path(...),
        session: Session = Depends(get_session),
    ) -> None:
        ok = service.delete(session, item_id)
        if ok is None:
            singular = (
                prefix[:-1].capitalize()
                if prefix.endswith("s")
                else prefix.capitalize()
            )
            raise HTTPException(
                status_code=404, detail=f"{singular} {item_id} not found"
            )
        # 204 sin body

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CatalogoCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)


class CatalogoUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)


class CatalogoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: Optional[str]
    is_active: bool
    value_count: int = 0
    created_at: datetime
    updated_at: datetime


class CatalogoValorCreate(BaseModel):
    value: str = Field(min_length=1, max_length=255)


class CatalogoValorUpdate(BaseModel):
    value: str = Field(min_length=1, max_length=255)


class CatalogoValorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    catalog_id: UUID
    value: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
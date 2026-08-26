from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ReimpresionRequest(BaseModel):
    motivo: str = Field(min_length=1, max_length=255)
    formato: Literal["A4", "TICKET_80MM", "TICKET_58MM"]


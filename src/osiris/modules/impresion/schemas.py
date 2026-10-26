from __future__ import annotations

from typing import Literal, TypedDict

from pydantic import BaseModel, Field


class PreimpresaHTMLResult(TypedDict):
    html: str
    warning: str | None


class PreimpresaPDFResult(TypedDict):
    pdf: bytes
    warning: str | None


class ReimpresionResult(TypedDict):
    content: bytes | str
    media_type: str
    filename: str


class ReimpresionRequest(BaseModel):
    motivo: str = Field(min_length=1, max_length=255)
    formato: Literal["A4", "TICKET_80MM", "TICKET_58MM"]


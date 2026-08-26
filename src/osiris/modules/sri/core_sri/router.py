from __future__ import annotations

from fastapi import APIRouter


# Router de dominio base SRI (sin endpoints directos).
router = APIRouter(prefix="/api/v1/sri/core", tags=["SRI Core"])

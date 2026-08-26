from __future__ import annotations

from fastapi import APIRouter


# Router de dominio (sin endpoints directos). Se conserva para compatibilidad de imports.
router = APIRouter(prefix="/api/v1/common", tags=["Common"])

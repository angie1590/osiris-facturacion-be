from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.schemas.empresa import (
    EmpresaCreate,
    EmpresaResponse,
    PuntoEmisionCreate,
    PuntoEmisionResponse,
    SucursalCreate,
    SucursalResponse,
)
from app.services.empresa_service import EmpresaService

router = APIRouter()


@router.post("", response_model=EmpresaResponse, dependencies=[Depends(require_admin)])
async def create_empresa(data: EmpresaCreate, db: AsyncSession = Depends(get_db)):
    service = EmpresaService(db)
    return await service.create_empresa(data)


@router.get("", response_model=list[EmpresaResponse])
async def list_empresas(db: AsyncSession = Depends(get_db)):
    service = EmpresaService(db)
    return await service.list_empresas()


@router.get("/{empresa_id}", response_model=EmpresaResponse)
async def get_empresa(empresa_id: int, db: AsyncSession = Depends(get_db)):
    service = EmpresaService(db)
    return await service.get_empresa(empresa_id)


@router.post("/{empresa_id}/sucursales", response_model=SucursalResponse, dependencies=[Depends(require_admin)])
async def add_sucursal(empresa_id: int, data: SucursalCreate, db: AsyncSession = Depends(get_db)):
    service = EmpresaService(db)
    return await service.add_sucursal(empresa_id, data)


@router.post(
    "/sucursales/{sucursal_id}/puntos-emision",
    response_model=PuntoEmisionResponse,
    dependencies=[Depends(require_admin)],
)
async def add_punto_emision(sucursal_id: int, data: PuntoEmisionCreate, db: AsyncSession = Depends(get_db)):
    service = EmpresaService(db)
    return await service.add_punto_emision(sucursal_id, data)

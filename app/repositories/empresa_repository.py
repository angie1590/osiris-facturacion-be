from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.empresa import Empresa, PuntoEmision, Sucursal


class EmpresaRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, empresa_id: int) -> Empresa | None:
        result = await self.db.execute(
            select(Empresa)
            .options(selectinload(Empresa.sucursales).selectinload(Sucursal.puntos_emision))
            .where(Empresa.id == empresa_id)
        )
        return result.scalar_one_or_none()

    async def get_by_ruc(self, ruc: str) -> Empresa | None:
        result = await self.db.execute(select(Empresa).where(Empresa.ruc == ruc))
        return result.scalar_one_or_none()

    async def list_active(self) -> list[Empresa]:
        result = await self.db.execute(select(Empresa).where(Empresa.is_active.is_(True)))
        return list(result.scalars().all())

    async def create(self, empresa: Empresa) -> Empresa:
        self.db.add(empresa)
        await self.db.flush()
        return empresa


class SucursalRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_empresa(self, empresa_id: int) -> list[Sucursal]:
        result = await self.db.execute(select(Sucursal).where(Sucursal.empresa_id == empresa_id))
        return list(result.scalars().all())

    async def create(self, sucursal: Sucursal) -> Sucursal:
        self.db.add(sucursal)
        await self.db.flush()
        return sucursal


class PuntoEmisionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_sucursal(self, sucursal_id: int) -> list[PuntoEmision]:
        result = await self.db.execute(select(PuntoEmision).where(PuntoEmision.sucursal_id == sucursal_id))
        return list(result.scalars().all())

    async def create(self, punto: PuntoEmision) -> PuntoEmision:
        self.db.add(punto)
        await self.db.flush()
        return punto

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.empresa import Empresa, PuntoEmision, Sucursal
from app.repositories.empresa_repository import EmpresaRepository, PuntoEmisionRepository, SucursalRepository
from app.schemas.empresa import EmpresaCreate, PuntoEmisionCreate, SucursalCreate


class EmpresaService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.empresa_repo = EmpresaRepository(db)
        self.sucursal_repo = SucursalRepository(db)
        self.punto_repo = PuntoEmisionRepository(db)

    async def create_empresa(self, data: EmpresaCreate) -> Empresa:
        if await self.empresa_repo.get_by_ruc(data.ruc):
            raise ConflictError("EMPRESA_RUC_EXISTS", "Ya existe una empresa con este RUC")
        empresa = Empresa(**data.model_dump())
        await self.empresa_repo.create(empresa)
        await self.db.commit()
        await self.db.refresh(empresa)
        return empresa

    async def get_empresa(self, empresa_id: int) -> Empresa:
        empresa = await self.empresa_repo.get_by_id(empresa_id)
        if not empresa:
            raise NotFoundError("EMPRESA_NOT_FOUND", "Empresa no encontrada")
        return empresa

    async def list_empresas(self) -> list[Empresa]:
        return await self.empresa_repo.list_active()

    async def add_sucursal(self, empresa_id: int, data: SucursalCreate) -> Sucursal:
        await self.get_empresa(empresa_id)
        sucursal = Sucursal(empresa_id=empresa_id, **data.model_dump())
        await self.sucursal_repo.create(sucursal)
        await self.db.commit()
        await self.db.refresh(sucursal)
        return sucursal

    async def add_punto_emision(self, sucursal_id: int, data: PuntoEmisionCreate) -> PuntoEmision:
        punto = PuntoEmision(sucursal_id=sucursal_id, **data.model_dump())
        await self.punto_repo.create(punto)
        await self.db.commit()
        await self.db.refresh(punto)
        return punto

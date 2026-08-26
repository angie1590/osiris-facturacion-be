from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.persona import Cliente, Persona, Proveedor, TipoPersona
from app.repositories.persona_repository import PersonaRepository
from app.schemas.persona import PersonaCreate, PersonaUpdate


class PersonaService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = PersonaRepository(db)

    async def create_persona(self, empresa_id: int, data: PersonaCreate) -> Persona:
        existing = await self.repo.get_by_identificacion(empresa_id, data.identificacion)
        if existing:
            raise ConflictError("PERSONA_EXISTS", f"Ya existe una persona con identificación {data.identificacion}")

        persona_class = Cliente if data.tipo == TipoPersona.cliente else Proveedor
        persona = persona_class(empresa_id=empresa_id, **data.model_dump())
        await self.repo.create(persona)
        await self.db.commit()
        await self.db.refresh(persona)
        return persona

    async def get_persona(self, persona_id: int) -> Persona:
        persona = await self.repo.get_by_id(persona_id)
        if not persona:
            raise NotFoundError("PERSONA_NOT_FOUND", "Persona no encontrada")
        return persona

    async def list_personas(self, empresa_id: int, tipo: TipoPersona) -> list[Persona]:
        return await self.repo.list_by_empresa_y_tipo(empresa_id, tipo)

    async def search_persona(self, empresa_id: int, identificacion: str) -> Persona:
        persona = await self.repo.get_by_identificacion(empresa_id, identificacion)
        if not persona:
            raise NotFoundError("PERSONA_NOT_FOUND", "Persona no encontrada")
        return persona

    async def update_persona(self, persona_id: int, data: PersonaUpdate) -> Persona:
        persona = await self.get_persona(persona_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(persona, field, value)
        await self.repo.update(persona)
        await self.db.commit()
        await self.db.refresh(persona)
        return persona

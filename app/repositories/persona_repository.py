from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.persona import Persona, TipoPersona


class PersonaRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, persona_id: int) -> Persona | None:
        result = await self.db.execute(select(Persona).where(Persona.id == persona_id))
        return result.scalar_one_or_none()

    async def list_by_empresa_y_tipo(self, empresa_id: int, tipo: TipoPersona) -> list[Persona]:
        result = await self.db.execute(
            select(Persona).where(Persona.empresa_id == empresa_id, Persona.tipo == tipo)
        )
        return list(result.scalars().all())

    async def get_by_identificacion(self, empresa_id: int, identificacion: str) -> Persona | None:
        result = await self.db.execute(
            select(Persona).where(Persona.empresa_id == empresa_id, Persona.identificacion == identificacion)
        )
        return result.scalar_one_or_none()

    async def create(self, persona: Persona) -> Persona:
        self.db.add(persona)
        await self.db.flush()
        return persona

    async def update(self, persona: Persona) -> Persona:
        await self.db.merge(persona)
        await self.db.flush()
        return persona

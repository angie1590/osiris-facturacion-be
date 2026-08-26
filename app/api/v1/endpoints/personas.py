from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_empresa_id, require_admin_or_supervisor
from app.models.persona import TipoPersona
from app.schemas.persona import PersonaCreate, PersonaResponse, PersonaUpdate
from app.services.persona_service import PersonaService

router = APIRouter()


@router.post("", response_model=PersonaResponse, dependencies=[Depends(require_admin_or_supervisor)])
async def create_persona(
    data: PersonaCreate,
    empresa_id: int = Depends(get_current_empresa_id),
    db: AsyncSession = Depends(get_db),
):
    service = PersonaService(db)
    return await service.create_persona(empresa_id, data)


@router.get("/{tipo}", response_model=list[PersonaResponse])
async def list_personas(
    tipo: TipoPersona,
    empresa_id: int = Depends(get_current_empresa_id),
    db: AsyncSession = Depends(get_db),
):
    service = PersonaService(db)
    return await service.list_personas(empresa_id, tipo)


@router.get("/{persona_id}", response_model=PersonaResponse)
async def get_persona(persona_id: int, db: AsyncSession = Depends(get_db)):
    service = PersonaService(db)
    return await service.get_persona(persona_id)


@router.patch("/{persona_id}", response_model=PersonaResponse, dependencies=[Depends(require_admin_or_supervisor)])
async def update_persona(
    persona_id: int,
    data: PersonaUpdate,
    db: AsyncSession = Depends(get_db),
):
    service = PersonaService(db)
    return await service.update_persona(persona_id, data)

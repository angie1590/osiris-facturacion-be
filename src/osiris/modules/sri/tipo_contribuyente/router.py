from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from osiris.core.db import get_session
from osiris.modules.sri.tipo_contribuyente.entity import TipoContribuyente

router = APIRouter(prefix="/api/v1/tipos-contribuyente", tags=["Tipos de contribuyente"])


@router.get("")
def list_tipos_contribuyente(
    only_active: bool = Query(True),
    session: Session = Depends(get_session),
) -> list[TipoContribuyente]:
    statement = select(TipoContribuyente)
    if only_active:
        statement = statement.where(TipoContribuyente.activo.is_(True))
    return list(session.exec(statement).all())
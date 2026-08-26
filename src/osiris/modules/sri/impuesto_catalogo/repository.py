from __future__ import annotations

from typing import Optional, List
from datetime import date
from uuid import UUID
from sqlmodel import Session, select
from fastapi import HTTPException

from osiris.domain.repository import BaseRepository
from osiris.modules.sri.impuesto_catalogo.entity import ImpuestoCatalogo, TipoImpuesto


class ImpuestoCatalogoRepository(BaseRepository):
    model = ImpuestoCatalogo

    def get_by_codigo_sri(self, session: Session, codigo_sri: str) -> Optional[ImpuestoCatalogo]:
        """Obtiene un impuesto por su código SRI."""
        stmt = select(ImpuestoCatalogo).where(ImpuestoCatalogo.codigo_sri == codigo_sri)
        return session.exec(stmt).first()

    def list_activos_vigentes(self, session: Session, fecha: Optional[date] = None) -> List[ImpuestoCatalogo]:
        """
        Lista impuestos activos y vigentes en una fecha dada.
        Si fecha es None, usa la fecha actual.
        """
        if fecha is None:
            fecha = date.today()

        stmt = select(ImpuestoCatalogo).where(
            ImpuestoCatalogo.activo.is_(True),
            ImpuestoCatalogo.vigente_desde <= fecha,
        )

        # vigente_hasta puede ser null (vigencia indefinida) o >= fecha
        stmt = stmt.where(
            (ImpuestoCatalogo.vigente_hasta.is_(None)) | (ImpuestoCatalogo.vigente_hasta >= fecha)
        )

        return list(session.exec(stmt).all())

    def list_by_tipo(
        self,
        session: Session,
        tipo: TipoImpuesto,
        solo_vigentes: bool = False,
        fecha: Optional[date] = None
    ) -> List[ImpuestoCatalogo]:
        """Lista impuestos por tipo, opcionalmente filtrando por vigencia."""
        stmt = select(ImpuestoCatalogo).where(
            ImpuestoCatalogo.tipo_impuesto == tipo,
            ImpuestoCatalogo.activo.is_(True)
        )

        if solo_vigentes:
            if fecha is None:
                fecha = date.today()
            stmt = stmt.where(
                ImpuestoCatalogo.vigente_desde <= fecha,
                (ImpuestoCatalogo.vigente_hasta.is_(None)) | (ImpuestoCatalogo.vigente_hasta >= fecha)
            )

        return list(session.exec(stmt).all())

    def es_vigente(self, impuesto: ImpuestoCatalogo, fecha: Optional[date] = None) -> bool:
        """Verifica si un impuesto está vigente en una fecha dada."""
        if fecha is None:
            fecha = date.today()

        if not impuesto.activo:
            return False

        if impuesto.vigente_desde > fecha:
            return False

        if impuesto.vigente_hasta is not None and impuesto.vigente_hasta < fecha:
            return False

        return True

    def validar_duplicado_codigo_descripcion(
        self,
        session: Session,
        codigo_sri: str,
        descripcion: str,
        exclude_id: Optional[UUID] = None
    ) -> None:
        """Valida que no exista otro impuesto con la misma combinación de código SRI y descripción."""
        stmt = select(ImpuestoCatalogo).where(
            ImpuestoCatalogo.codigo_sri == codigo_sri,
            ImpuestoCatalogo.descripcion == descripcion
        )

        if exclude_id:
            stmt = stmt.where(ImpuestoCatalogo.id != exclude_id)

        existente = session.exec(stmt).first()
        if existente:
            raise HTTPException(
                status_code=409,
                detail=f"Ya existe un impuesto con código SRI '{codigo_sri}' y descripción '{descripcion}'"
            )

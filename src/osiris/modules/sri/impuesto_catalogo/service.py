from __future__ import annotations

from typing import List, Optional
from datetime import date
from uuid import UUID
from sqlmodel import Session
from fastapi import HTTPException

from osiris.domain.service import BaseService
from osiris.modules.sri.impuesto_catalogo.repository import ImpuestoCatalogoRepository
from osiris.modules.sri.impuesto_catalogo.entity import ImpuestoCatalogo, TipoImpuesto


class ImpuestoCatalogoService(BaseService):
    repo = ImpuestoCatalogoRepository()

    def create(self, session: Session, data):
        """Crea un nuevo impuesto en el catálogo con validaciones."""
        # Validar combinación código SRI + descripción única
        codigo_sri = getattr(data, "codigo_sri", None) or data.get("codigo_sri")
        descripcion = getattr(data, "descripcion", None) or data.get("descripcion")
        self.repo.validar_duplicado_codigo_descripcion(session, codigo_sri, descripcion)

        # Crear el impuesto
        return super().create(session, data)

    def update(self, session: Session, item_id: UUID, data):
        """Actualiza un impuesto existente."""
        impuesto = self.repo.get(session, item_id)
        if not impuesto:
            raise HTTPException(status_code=404, detail="Impuesto no encontrado")

        # Si se intenta cambiar código SRI o descripción, validar que la combinación no exista
        codigo_sri = getattr(data, "codigo_sri", None) or data.get("codigo_sri")
        descripcion = getattr(data, "descripcion", None) or data.get("descripcion")

        # Usar valores actuales si no se proporcionan nuevos
        codigo_sri_final = codigo_sri if codigo_sri else impuesto.codigo_sri
        descripcion_final = descripcion if descripcion else impuesto.descripcion

        # Validar si cambió alguno de los dos campos
        if (codigo_sri and codigo_sri != impuesto.codigo_sri) or (descripcion and descripcion != impuesto.descripcion):
            self.repo.validar_duplicado_codigo_descripcion(session, codigo_sri_final, descripcion_final, exclude_id=item_id)

        return super().update(session, item_id, data)

    def list_activos_vigentes(self, session: Session, fecha: Optional[date] = None) -> List[ImpuestoCatalogo]:
        """Lista impuestos activos y vigentes."""
        return self.repo.list_activos_vigentes(session, fecha)

    def list_by_tipo(
        self,
        session: Session,
        tipo: TipoImpuesto,
        solo_vigentes: bool = False,
        fecha: Optional[date] = None
    ) -> List[ImpuestoCatalogo]:
        """Lista impuestos por tipo."""
        return self.repo.list_by_tipo(session, tipo, solo_vigentes, fecha)

    def get_by_codigo_sri(self, session: Session, codigo_sri: str) -> Optional[ImpuestoCatalogo]:
        """Obtiene un impuesto por su código SRI."""
        return self.repo.get_by_codigo_sri(session, codigo_sri)

    def validar_vigencia(self, impuesto: ImpuestoCatalogo, fecha: Optional[date] = None) -> None:
        """Valida que un impuesto esté vigente."""
        if not self.repo.es_vigente(impuesto, fecha):
            raise HTTPException(
                status_code=400,
                detail=f"El impuesto '{impuesto.codigo_sri}' no está vigente en la fecha especificada"
            )

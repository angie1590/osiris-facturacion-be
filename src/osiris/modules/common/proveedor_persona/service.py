# src/osiris/modules/common/proveedor_persona/service.py
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, select

from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.domain.directory_service import DirectoryService
from .repository import ProveedorPersonaRepository
from .models import ProveedorPersonaCreate, ProveedorPersonaRead, ProveedorPersonaUpdate

from osiris.modules.common.persona.entity import Persona, TipoIdentificacion
from osiris.modules.sri.tipo_contribuyente.entity import TipoContribuyente
from osiris.utils.validacion_identificacion import ValidacionCedulaRucService


class ProveedorPersonaService(DirectoryService):
    repo = ProveedorPersonaRepository()
    create_model = ProveedorPersonaCreate
    update_model = ProveedorPersonaUpdate
    read_model = ProveedorPersonaRead
    persona_field = "persona_id"
    unique_field = "persona_id"
    catalog_model = TipoContribuyente
    catalog_field = "tipo_contribuyente_id"
    catalog_key = "codigo"
    catalog_name_field = "tipo_contribuyente_nombre"

    # ✅ Usa el mapa de FKs (modelo, columna) para que la base valide con la columna correcta
    fk_models = {
        "persona_id": (Persona, "id"),
        "tipo_contribuyente_id": (TipoContribuyente, "codigo"),
    }

    # ───────── Validaciones de negocio ─────────
    def _assert_persona_ruc_natural(self, session: Session, persona_id: UUID) -> None:
        persona = session.exec(select(Persona).where(Persona.id == persona_id)).first()
        if not persona:
            raise HTTPException(
                status_code=404, detail=f"Persona {persona_id} not found"
            )

        # Debe ser RUC
        if getattr(persona, "tipo_identificacion", None) != TipoIdentificacion.RUC:
            raise HTTPException(
                status_code=400, detail="Solo se permite RUC para proveedores persona."
            )

        ident = (getattr(persona, "identificacion", None) or "").strip()
        if not ident:
            raise HTTPException(
                status_code=400, detail="La persona no tiene identificación registrada"
            )

        # RUC de persona natural (usa tu helper)
        if not ValidacionCedulaRucService.es_ruc_persona_natural_valido(ident):
            raise HTTPException(
                status_code=400,
                detail="El RUC debe pertenecer a una persona natural (no sociedad).",
            )

    def _assert_tipo_contribuyente_permitido(
        self, session: Session, codigo: str
    ) -> None:
        tc = session.exec(
            select(TipoContribuyente)
            .where(TipoContribuyente.codigo == codigo)
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        ).first()
        if not tc:
            # 404 si no existe
            raise HTTPException(
                status_code=404, detail=f"TipoContribuyente {codigo} not found"
            )
        if tc.activo is False:
            raise HTTPException(
                status_code=409, detail=f"TipoContribuyente {codigo} inactivo"
            )

        # 400 si existe pero no aplica para proveedor persona
        if tc.aplica_persona_natural is not True:
            raise HTTPException(
                status_code=400,
                detail="El tipo de contribuyente no es válido para proveedores persona "
                "(no se permite Sociedad ni Gran Contribuyente).",
            )

    # ───────── Overrides CRUD ─────────
    def validate_create(self, data: dict[str, Any], session: Session) -> None:
        self._assert_persona_ruc_natural(session, data["persona_id"])
        self._assert_tipo_contribuyente_permitido(
            session, data["tipo_contribuyente_id"]
        )

    def prepare_update(
        self, session: Session, current: Any, payload: dict[str, Any]
    ) -> dict[str, Any]:
        payload = self.immutable_persona(current, payload)
        if "tipo_contribuyente_id" in payload:
            if payload["tipo_contribuyente_id"] is None:
                raise HTTPException(
                    status_code=422, detail="tipo_contribuyente_id no puede ser null"
                )
            self._assert_tipo_contribuyente_permitido(
                session, payload["tipo_contribuyente_id"]
            )
        return payload

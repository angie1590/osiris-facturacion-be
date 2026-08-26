# src/osiris/modules/common/proveedor_persona/service.py
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, select

from osiris.domain.service import BaseService
from .repository import ProveedorPersonaRepository
from .entity import ProveedorPersona

from osiris.modules.common.persona.entity import Persona, TipoIdentificacion
from osiris.modules.sri.tipo_contribuyente.entity import TipoContribuyente
from osiris.utils.validacion_identificacion import ValidacionCedulaRucService


class ProveedorPersonaService(BaseService):
    repo = ProveedorPersonaRepository()

    # ✅ Usa el mapa de FKs (modelo, columna) para que la base valide con la columna correcta
    fk_map = {
        "persona_id": (Persona, "id"),
        "tipo_contribuyente_id": (TipoContribuyente, "codigo"),
    }

    @staticmethod
    def _ensure_dict(data: Any) -> dict[str, Any]:
        if hasattr(data, "model_dump"):
            return data.model_dump(exclude_unset=True)
        if isinstance(data, dict):
            return data
        return {k: v for k, v in vars(data).items() if not k.startswith("_")}

    # ───────── Validaciones de negocio ─────────
    def _assert_persona_ruc_natural(self, session: Session, persona_id: UUID) -> None:
        persona = session.exec(
            select(Persona).where(Persona.id == persona_id)
        ).first()
        if not persona:
            raise HTTPException(status_code=404, detail=f"Persona {persona_id} not found")

        # Debe ser RUC
        if getattr(persona, "tipo_identificacion", None) != TipoIdentificacion.RUC:
            raise HTTPException(
                status_code=400,
                detail="Solo se permite RUC para proveedores persona."
            )

        ident = (getattr(persona, "identificacion", None) or "").strip()
        if not ident:
            raise HTTPException(status_code=400, detail="La persona no tiene identificación registrada")

        # RUC de persona natural (usa tu helper)
        if not ValidacionCedulaRucService.es_ruc_persona_natural_valido(ident):
            raise HTTPException(
                status_code=400,
                detail="El RUC debe pertenecer a una persona natural (no sociedad)."
            )

    def _assert_tipo_contribuyente_permitido(self, session: Session, codigo: str) -> None:
        tc = session.exec(
            select(TipoContribuyente).where(TipoContribuyente.codigo == codigo)
        ).first()
        if not tc:
            # 404 si no existe
            raise HTTPException(status_code=404, detail=f"TipoContribuyente {codigo} not found")

        # 400 si existe pero no aplica para proveedor persona
        nombre = (getattr(tc, "nombre", None) or getattr(tc, "descripcion", "") or "").strip().lower()
        prohibidas = {"sociedad", "gran contribuyente", "sociedad privada", "sociedad pública"}
        if any(p in nombre for p in prohibidas):
            raise HTTPException(
                status_code=400,
                detail="El tipo de contribuyente no es válido para proveedores persona "
                       "(no se permite Sociedad ni Gran Contribuyente)."
            )

    # ───────── Overrides CRUD ─────────
    def create(self, session: Session, data: Any) -> ProveedorPersona:
        payload = self._ensure_dict(data)

        # 1) Valida FKs (con fk_map) → 404 si no existen / inactivos
        self._check_fk_active_and_exists(session, payload)

        # 2) Reglas de negocio específicas
        self._assert_persona_ruc_natural(session, payload["persona_id"])
        self._assert_tipo_contribuyente_permitido(session, payload["tipo_contribuyente_id"])

        # 3) Unicidad persona_id la maneja BaseRepository (IntegrityError 23505 → HTTP 409)
        return super().create(session, payload)

    def update(self, session: Session, item_id: UUID, data: Any) -> ProveedorPersona | None:
        incoming = self._ensure_dict(data)

        # No permitir cambiar persona_id en update
        incoming.pop("persona_id", None)

        # Si cambian el tipo_contribuyente, validar FK y regla
        if "tipo_contribuyente_id" in incoming and incoming["tipo_contribuyente_id"] is not None:
            self._check_fk_active_and_exists(session, {
                "tipo_contribuyente_id": incoming["tipo_contribuyente_id"]
            })
            self._assert_tipo_contribuyente_permitido(session, incoming["tipo_contribuyente_id"])

        return super().update(session, item_id, incoming)

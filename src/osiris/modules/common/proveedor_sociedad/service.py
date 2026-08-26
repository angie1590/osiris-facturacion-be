from __future__ import annotations

import re
from typing import Any
from uuid import UUID
from fastapi import HTTPException
from sqlmodel import Session, select

from osiris.domain.service import BaseService
from .repository import ProveedorSociedadRepository
from .entity import ProveedorSociedad

from osiris.modules.common.persona.entity import Persona
from osiris.modules.sri.tipo_contribuyente.entity import TipoContribuyente
from osiris.utils.validacion_identificacion import ValidacionCedulaRucService


# Códigos NO permitidos para proveedor sociedad:
# 01 = Persona Natural, 03 = RIMPE - Negocio Popular
FORBIDDEN_TC_CODES = {"01", "03"}

class ProveedorSociedadService(BaseService):
    repo = ProveedorSociedadRepository()

    # ✅ Igual que en proveedor_persona: mapa de FKs (modelo, columna) para que
    # el BaseService valide con la columna correcta.
    fk_map = {
        "persona_contacto_id": (Persona, "id"),
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
    def _validar_ruc_sociedad(self, ruc: str) -> None:
        # Debe ser un identificador válido…
        if not ValidacionCedulaRucService.es_identificacion_valida(ruc):
            raise HTTPException(status_code=400, detail="El RUC no es válido")
        # …y NO debe ser RUC de persona natural
        if ValidacionCedulaRucService.es_ruc_persona_natural_valido(ruc):
            raise HTTPException(
                status_code=400,
                detail="El RUC no puede pertenecer a una persona natural"
            )

    def _validar_tipo_contribuyente_por_codigo(self, session: Session, codigo: str) -> None:
        # Negocio: Proveedor sociedad NO admite 01 ni 03
        if codigo in FORBIDDEN_TC_CODES:
            raise HTTPException(
                status_code=400,
                detail="El tipo de contribuyente no puede ser 01 (Persona Natural) ni 03 (RIMPE - Negocio Popular)"
            )

        tc = session.exec(
            select(TipoContribuyente).where(TipoContribuyente.codigo == codigo)
        ).first()
        if not tc:
            raise HTTPException(status_code=404, detail=f"TipoContribuyente {codigo} not found")

        # Si manejas 'activo' en la tabla, refuerza:
        if hasattr(tc, "activo") and not getattr(tc, "activo"):
            raise HTTPException(status_code=404, detail=f"TipoContribuyente {codigo} no encontrado o inactivo")

    def _validar_telefono(self, telefono: str | None) -> None:
        if telefono is None:
            return
        t = telefono.strip()
        if t and (not t.isdigit() or len(t) != 10):
            raise HTTPException(
                status_code=400,
                detail="El teléfono debe tener exactamente 10 dígitos numéricos"
            )

    def _validar_email(self, email: str | None) -> None:
        if email is None:
            return
        e = email.strip()
        if not e:
            return
        # Validación simple de formato (para unit tests; en entrada real podrías usar EmailStr en el DTO)
        # Requisito mínimo: algo@algo.algo
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", e):
            raise HTTPException(status_code=400, detail="El email no cumple con el formato válido")

    # ───────── Overrides CRUD ─────────
    def create(self, session: Session, data: Any) -> ProveedorSociedad:
        payload = self._ensure_dict(data)

        # 1) Valida FKs con fk_map (persona_contacto_id por id, tipo_contribuyente por codigo)
        self._check_fk_active_and_exists(session, payload)

        # 2) Validaciones de negocio
        self._validar_ruc_sociedad(payload["ruc"])
        self._validar_tipo_contribuyente_por_codigo(session, payload["tipo_contribuyente_id"])
        self._validar_telefono(payload.get("telefono"))
        self._validar_email(payload.get("email"))

        # 3) Unicidad (ruc único) y demás → lo maneja el BaseRepository (IntegrityError → HTTP 409)
        return super().create(session, payload)

    def update(self, session: Session, item_id: UUID, data: Any) -> ProveedorSociedad | None:
        incoming = self._ensure_dict(data)

        # No permitir cambiar persona_contacto_id en update
        incoming.pop("persona_contacto_id", None)

        # Si cambian campos clave, volver a validar
        if "tipo_contribuyente_id" in incoming and incoming["tipo_contribuyente_id"] is not None:
            # valida existencia por codigo + reglas de negocio
            self._check_fk_active_and_exists(session, {
                "tipo_contribuyente_id": incoming["tipo_contribuyente_id"]
            })
            self._validar_tipo_contribuyente_por_codigo(session, incoming["tipo_contribuyente_id"])

        if "ruc" in incoming and incoming["ruc"] is not None:
            self._validar_ruc_sociedad(incoming["ruc"])

        if "telefono" in incoming:
            self._validar_telefono(incoming.get("telefono"))

        if "email" in incoming:
            self._validar_email(incoming.get("email"))

        return super().update(session, item_id, incoming)
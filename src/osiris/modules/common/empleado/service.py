from __future__ import annotations

from typing import Any
from uuid import UUID
from datetime import date
from sqlmodel import Session

from fastapi import HTTPException
from osiris.domain.service import BaseService
from .repository import EmpleadoRepository
from .entity import Empleado

from osiris.modules.common.persona.entity import Persona
from osiris.modules.common.empresa.entity import Empresa
from .strategy import EmpleadoCrearUsuarioStrategy


class EmpleadoService(BaseService):
    """
    - Valida FKs (existencia/activo) vía fk_models (BaseService).
    - Unicidad y FKs violadas -> BaseRepository (HTTP 409).
    - Al crear, también crea Usuario (estrategia).
    - No permite cambiar persona_id en update.
    - Valida coherencia de fechas en update (fecha_salida > fecha_ingreso).
    """
    repo = EmpleadoRepository()
    fk_models = {
        "persona_id": Persona,
        "empresa_id": Empresa,
    }

    def __init__(self, strategy: EmpleadoCrearUsuarioStrategy | None = None) -> None:
        self.strategy = strategy or EmpleadoCrearUsuarioStrategy()

    @staticmethod
    def _ensure_dict(data: Any) -> dict[str, Any]:
        if hasattr(data, "model_dump"):
            return data.model_dump(exclude_unset=True)
        if isinstance(data, dict):
            return data
        return {k: v for k, v in vars(data).items() if not k.startswith("_")}

    # --- CREATE: crea usuario + empleado ---
    def create(self, session: Session, data: Any) -> Empleado:
        data = self._ensure_dict(data)
        persona_id = data.get("persona_id")
        if not persona_id:
            raise HTTPException(status_code=400, detail="persona_id es requerido")

        # Extraer bloque usuario y quitarlo del payload del empleado
        usuario_payload = data.pop("usuario", None)

        # 1) Crear Usuario (con persona_id forzado)
        self.strategy.create_user_for_persona(
            session,
            persona_id=persona_id,
            usuario_payload=usuario_payload,
            commit=False,
        )

        # 2) Crear Empleado
        empleado = super().create(session, data, commit=False)
        try:
            session.commit()
            session.refresh(empleado)
        except Exception as exc:
            self._handle_transaction_error(session, exc)
        return empleado

    # --- UPDATE: bloquear persona_id + validar coherencia de fechas ---
    def update(self, session: Session, item_id: UUID, data: Any) -> Empleado | None:
        incoming = self._ensure_dict(data)
        incoming.pop("persona_id", None)

        def _to_date(v):
            if isinstance(v, date) or v is None:
                return v
            if isinstance(v, str):
                return date.fromisoformat(v)
            return v

        if "fecha_ingreso" in incoming:
            incoming["fecha_ingreso"] = _to_date(incoming["fecha_ingreso"])
        if "fecha_salida" in incoming:
            incoming["fecha_salida"] = _to_date(incoming["fecha_salida"])

        # Necesitamos el objeto actual para completar reglas con datos existentes
        current = self.repo.get(session, item_id)
        if not current:
            return None

        # Resolver fechas a usar en la validación:
        # - ingreso: el nuevo si llega, si no el actual
        # - salida: sólo validamos si llega (puede venir None para limpiar → en ese caso no hay restricción)
        new_ingreso: date = incoming.get("fecha_ingreso", current.fecha_ingreso)

        if "fecha_ingreso" in incoming:
            if new_ingreso > date.today():
                raise HTTPException(
                    status_code=400,
                    detail="La fecha de ingreso no puede ser mayor que la fecha actual."
                )
        if "fecha_salida" in incoming and incoming["fecha_salida"] is not None:
            new_salida: date = incoming["fecha_salida"]
            if new_salida <= new_ingreso:
                raise HTTPException(
                    status_code=400,
                    detail="La fecha de salida debe ser posterior a la fecha de ingreso."
                )

        # La edad mínima ya se valida en el DTO si llega nueva fecha_nacimiento.
        return super().update(session, item_id, incoming)

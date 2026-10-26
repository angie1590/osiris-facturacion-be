from __future__ import annotations

from typing import Any
from fastapi import HTTPException
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlmodel import Session, select

from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.domain.directory_service import DirectoryService
from .repository import ProveedorSociedadRepository
from .models import (
    ProveedorSociedadCreate,
    ProveedorSociedadRead,
    ProveedorSociedadUpdate,
)

from osiris.modules.common.persona.entity import Persona
from osiris.modules.sri.tipo_contribuyente.entity import TipoContribuyente
from osiris.utils.validacion_identificacion import ValidacionCedulaRucService


class ProveedorSociedadService(DirectoryService):
    repo = ProveedorSociedadRepository()
    create_model = ProveedorSociedadCreate
    update_model = ProveedorSociedadUpdate
    read_model = ProveedorSociedadRead
    persona_field = "persona_contacto_id"
    persona_new_field = "persona_contacto_nueva"
    unique_field = "ruc"
    catalog_model = TipoContribuyente
    catalog_field = "tipo_contribuyente_id"
    catalog_key = "codigo"
    catalog_name_field = "tipo_contribuyente_nombre"

    # ✅ Igual que en proveedor_persona: mapa de FKs (modelo, columna) para que
    # el BaseService valide con la columna correcta.
    fk_models = {
        "persona_contacto_id": (Persona, "id"),
        "tipo_contribuyente_id": (TipoContribuyente, "codigo"),
    }

    # ───────── Validaciones de negocio ─────────
    def _validar_ruc_sociedad(self, ruc: str) -> None:
        if not isinstance(ruc, str) or len(ruc) != 13 or not ruc.isdigit():
            raise HTTPException(status_code=400, detail="El RUC debe tener 13 digitos")
        # Debe ser un identificador válido…
        if not ValidacionCedulaRucService.es_identificacion_valida(ruc):
            raise HTTPException(status_code=400, detail="El RUC no es válido")
        # …y NO debe ser RUC de persona natural
        if ValidacionCedulaRucService.es_ruc_persona_natural_valido(ruc):
            raise HTTPException(
                status_code=400,
                detail="El RUC no puede pertenecer a una persona natural",
            )

    def _validar_tipo_contribuyente_por_codigo(
        self, session: Session, codigo: str
    ) -> None:
        tc = session.exec(
            select(TipoContribuyente)
            .where(TipoContribuyente.codigo == codigo)
            .execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})
        ).first()
        if not tc:
            raise HTTPException(
                status_code=404, detail=f"TipoContribuyente {codigo} not found"
            )
        if tc.activo is False:
            raise HTTPException(
                status_code=409, detail=f"TipoContribuyente {codigo} inactivo"
            )
        if tc.aplica_sociedad is not True:
            raise HTTPException(
                status_code=400,
                detail="El tipo de contribuyente no es aplicable a sociedad",
            )

        # Si manejas 'activo' en la tabla, refuerza:
        if hasattr(tc, "activo") and not getattr(tc, "activo"):
            raise HTTPException(
                status_code=409, detail=f"TipoContribuyente {codigo} inactivo"
            )

    def _validar_telefono(self, telefono: str | None) -> None:
        if telefono is None:
            return
        t = telefono.strip()
        if t and (not t.isdigit() or len(t) != 10):
            raise HTTPException(
                status_code=400,
                detail="El teléfono debe tener exactamente 10 dígitos numéricos",
            )

    def _validar_email(self, email: str | None) -> None:
        try:
            TypeAdapter(EmailStr).validate_python(email)
        except ValidationError as error:
            raise HTTPException(
                status_code=400, detail="El email no cumple con el formato valido"
            ) from error

    def _normalize_fields(
        self, payload: dict[str, Any], *, partial: bool = False
    ) -> dict[str, Any]:
        for field in (
            "ruc",
            "razon_social",
            "direccion",
            "email",
            "telefono",
            "nombre_comercial",
        ):
            if isinstance(payload.get(field), str):
                payload[field] = payload[field].strip()
        for field in ("razon_social", "direccion"):
            if (not partial or field in payload) and not payload.get(field):
                raise HTTPException(
                    status_code=400, detail=f"{field} no puede ser vacio"
                )
        if "telefono" in payload:
            self._validar_telefono(payload["telefono"])
            payload["telefono"] = payload["telefono"] or None
        if not partial or "email" in payload:
            self._validar_email(payload.get("email"))
        return payload

    def prepare_create(
        self, session: Session, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._normalize_fields(payload)

    # ───────── Overrides CRUD ─────────
    def validate_create(self, data: dict[str, Any], session: Session) -> None:
        self._normalize_fields(data)
        self._validar_ruc_sociedad(data["ruc"])
        self._validar_tipo_contribuyente_por_codigo(
            session, data["tipo_contribuyente_id"]
        )
        self._validar_telefono(data.get("telefono"))
        self._validar_email(data.get("email"))

    def prepare_update(
        self, session: Session, current: Any, payload: dict[str, Any]
    ) -> dict[str, Any]:
        contact_fields = {"persona_contacto_id", "persona_contacto_nueva"}
        if payload.keys() & contact_fields and not any(
            payload.get(field) is not None for field in contact_fields
        ):
            raise HTTPException(status_code=422, detail="El contacto no puede ser null")
        payload = self._resolve(session, payload, required=False)
        for field in (
            "ruc",
            "razon_social",
            "direccion",
            "email",
            "tipo_contribuyente_id",
        ):
            if field in payload and payload[field] is None:
                raise HTTPException(
                    status_code=422, detail=f"{field} no puede ser null"
                )
        self._normalize_fields(payload, partial=True)
        if "tipo_contribuyente_id" in payload:
            self._validar_tipo_contribuyente_por_codigo(
                session, payload["tipo_contribuyente_id"]
            )
        if "ruc" in payload:
            self._validar_ruc_sociedad(payload["ruc"])
            self._check_duplicate(session, payload, item_id=current.id)
        return payload

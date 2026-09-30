from __future__ import annotations

from fastapi import HTTPException
from pydantic import ValidationError
from sqlmodel import Session, select

from osiris.modules.sri.tipo_contribuyente.entity import TipoContribuyente
from osiris.domain.service import BaseService
from osiris.modules.common.sucursal.entity import Sucursal
from .entity import ModoEmisionEmpresa, RegimenTributario, TipoContribuyenteJuridico
from .models import EmpresaRegimenModoRules
from .repository import EmpresaRepository


class EmpresaService(BaseService):
    fk_models = {
        "tipo_contribuyente_id": (TipoContribuyente, "codigo"),
    }
    repo = EmpresaRepository()

    @staticmethod
    def _normalize_resolution(value):
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    def _normalize_tributary_fields(self, data: dict) -> None:
        for key in (
            "contribuyente_especial_resolucion",
            "gran_contribuyente_resolucion",
            "agente_retencion_resolucion",
        ):
            if key in data:
                data[key] = self._normalize_resolution(data.get(key))

        if data.get("contribuyente_especial") is False:
            data["contribuyente_especial_resolucion"] = None
        if data.get("gran_contribuyente") is False:
            data["gran_contribuyente_resolucion"] = None
        if data.get("agente_retencion") is False:
            data["agente_retencion_resolucion"] = None

    @staticmethod
    def _infer_tipo_juridico_from_legacy(tipo_contribuyente_id: str | None):
        mapping = {
            "01": TipoContribuyenteJuridico.PERSONA_NATURAL,
            "02": TipoContribuyenteJuridico.SOCIEDAD,
        }
        if tipo_contribuyente_id is None:
            return None
        return mapping.get(str(tipo_contribuyente_id).strip())

    def _validate_regimen_modo(self, data: dict) -> None:
        if not data.get("tipo_contribuyente_juridico"):
            raise HTTPException(
                status_code=400,
                detail="El tipo de contribuyente jurídico es obligatorio.",
            )

        try:
            EmpresaRegimenModoRules(
                tipo_contribuyente_juridico=data.get("tipo_contribuyente_juridico"),
                regimen=data.get("regimen"),
                modo_emision=data.get("modo_emision"),
                contribuyente_especial=data.get("contribuyente_especial", False),
                contribuyente_especial_resolucion=data.get("contribuyente_especial_resolucion"),
                gran_contribuyente=data.get("gran_contribuyente", False),
                gran_contribuyente_resolucion=data.get("gran_contribuyente_resolucion"),
                agente_retencion=data.get("agente_retencion", False),
                agente_retencion_resolucion=data.get("agente_retencion_resolucion"),
            )
        except ValidationError as exc:
            raise HTTPException(
                status_code=400,
                detail=exc.errors()[0]["msg"],
            ) from exc

    def _build_validation_payload(self, db_obj, incoming: dict) -> dict:
        payload = {
            "tipo_contribuyente_juridico": incoming.get(
                "tipo_contribuyente_juridico",
                getattr(db_obj, "tipo_contribuyente_juridico", None),
            ),
            "regimen": incoming.get("regimen", getattr(db_obj, "regimen", RegimenTributario.GENERAL)),
            "modo_emision": incoming.get(
                "modo_emision",
                getattr(db_obj, "modo_emision", ModoEmisionEmpresa.ELECTRONICO),
            ),
            "contribuyente_especial": incoming.get(
                "contribuyente_especial",
                getattr(db_obj, "contribuyente_especial", False),
            ),
            "contribuyente_especial_resolucion": incoming.get(
                "contribuyente_especial_resolucion",
                getattr(db_obj, "contribuyente_especial_resolucion", None),
            ),
            "gran_contribuyente": incoming.get(
                "gran_contribuyente",
                getattr(db_obj, "gran_contribuyente", False),
            ),
            "gran_contribuyente_resolucion": incoming.get(
                "gran_contribuyente_resolucion",
                getattr(db_obj, "gran_contribuyente_resolucion", None),
            ),
            "agente_retencion": incoming.get(
                "agente_retencion",
                getattr(db_obj, "agente_retencion", False),
            ),
            "agente_retencion_resolucion": incoming.get(
                "agente_retencion_resolucion",
                getattr(db_obj, "agente_retencion_resolucion", None),
            ),
        }
        payload["contribuyente_especial_resolucion"] = self._normalize_resolution(
            payload.get("contribuyente_especial_resolucion")
        )
        payload["gran_contribuyente_resolucion"] = self._normalize_resolution(
            payload.get("gran_contribuyente_resolucion")
        )
        payload["agente_retencion_resolucion"] = self._normalize_resolution(
            payload.get("agente_retencion_resolucion")
        )
        if payload.get("contribuyente_especial") is False:
            payload["contribuyente_especial_resolucion"] = None
        if payload.get("gran_contribuyente") is False:
            payload["gran_contribuyente_resolucion"] = None
        if payload.get("agente_retencion") is False:
            payload["agente_retencion_resolucion"] = None
        return payload

    def validate_create(self, data, session: Session) -> None:
        data.setdefault("regimen", RegimenTributario.GENERAL)
        data.setdefault("modo_emision", ModoEmisionEmpresa.ELECTRONICO)
        self._normalize_tributary_fields(data)
        if data.get("tipo_contribuyente_juridico") is None:
            inferred = self._infer_tipo_juridico_from_legacy(data.get("tipo_contribuyente_id"))
            if inferred is not None:
                data["tipo_contribuyente_juridico"] = inferred
        self._validate_regimen_modo(data)

    def update(self, session: Session, item_id, data):
        try:
            db_obj = self.repo.get(session, item_id)
            if not db_obj:
                return None

            self._normalize_tributary_fields(data)
            validation_payload = self._build_validation_payload(db_obj, data)
            if validation_payload.get("tipo_contribuyente_juridico") is None:
                inferred = self._infer_tipo_juridico_from_legacy(
                    data.get("tipo_contribuyente_id") or getattr(db_obj, "tipo_contribuyente_id", None)
                )
                if inferred is not None:
                    validation_payload["tipo_contribuyente_juridico"] = inferred
                    data.setdefault("tipo_contribuyente_juridico", inferred)

            self._validate_regimen_modo(validation_payload)

            self._check_fk_active_and_exists(session, data)
            updated = self.repo.update(session, db_obj, data)
            session.commit()
            session.refresh(updated)
            return updated
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    def on_created(self, obj, session: Session) -> None:
        # En pruebas unitarias con sesiones mock, omitimos side-effects transaccionales.
        if not isinstance(session, Session):
            return

        matriz = session.exec(
            select(Sucursal).where(
                Sucursal.empresa_id == obj.id,
                Sucursal.codigo == "001",
                Sucursal.activo.is_(True),
            )
        ).first()
        if matriz is not None:
            return

        session.add(
            Sucursal(
                codigo="001",
                nombre="Matriz",
                direccion=obj.direccion_matriz,
                telefono=obj.telefono,
                empresa_id=obj.id,
                es_matriz=True,
                usuario_auditoria=obj.usuario_auditoria,
                activo=True,
            )
        )

from __future__ import annotations

from fastapi import HTTPException
from pydantic import ValidationError
from sqlmodel import Session, select

from osiris.modules.sri.tipo_contribuyente.entity import TipoContribuyente
from osiris.domain.service import BaseService
from osiris.modules.common.sucursal.entity import Sucursal
from .entity import ModoEmisionEmpresa, RegimenTributario
from .models import EmpresaRegimenModoRules
from .repository import EmpresaRepository


class EmpresaService(BaseService):
    fk_models = {
        "tipo_contribuyente_id": (TipoContribuyente, "codigo"),
    }
    repo = EmpresaRepository()

    def _validate_regimen_modo(self, regimen, modo_emision) -> None:
        try:
            EmpresaRegimenModoRules(
                regimen=regimen,
                modo_emision=modo_emision,
            )
        except ValidationError as exc:
            raise HTTPException(
                status_code=400,
                detail=exc.errors()[0]["msg"],
            ) from exc

    def validate_create(self, data, session: Session) -> None:
        regimen = data.get("regimen", RegimenTributario.GENERAL)
        modo_emision = data.get("modo_emision", ModoEmisionEmpresa.ELECTRONICO)
        self._validate_regimen_modo(regimen, modo_emision)

    def update(self, session: Session, item_id, data):
        try:
            db_obj = self.repo.get(session, item_id)
            if not db_obj:
                return None

            regimen = data.get("regimen", db_obj.regimen)
            modo_emision = data.get("modo_emision", db_obj.modo_emision)
            self._validate_regimen_modo(regimen, modo_emision)

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

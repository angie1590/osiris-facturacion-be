from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, event
from sqlalchemy.inspection import inspect as sa_inspect
from sqlmodel import Field

from osiris.domain.base_models import BaseTable, AuditMixin, SoftDeleteMixin


class RegimenTributario(str, Enum):
    GENERAL = "GENERAL"
    RIMPE_EMPRENDEDOR = "RIMPE_EMPRENDEDOR"
    RIMPE_NEGOCIO_POPULAR = "RIMPE_NEGOCIO_POPULAR"


class ModoEmisionEmpresa(str, Enum):
    ELECTRONICO = "ELECTRONICO"
    NOTA_VENTA_FISICA = "NOTA_VENTA_FISICA"


class Empresa(BaseTable, AuditMixin, SoftDeleteMixin, table=True):
    __tablename__ = "tbl_empresa"
    __table_args__ = (
        CheckConstraint(
            (
                "NOT (modo_emision = 'NOTA_VENTA_FISICA' "
                "AND regimen <> 'RIMPE_NEGOCIO_POPULAR')"
            ),
            name="ck_tbl_empresa_regimen_modo_emision",
        ),
    )

    razon_social: str = Field(index=True, nullable=False, max_length=255)
    nombre_comercial: Optional[str] = Field(default=None, max_length=255)

    # RUC ecuatoriano (13)
    ruc: str = Field(index=True, nullable=False, max_length=13)

    direccion_matriz: str = Field(nullable=False, max_length=255)
    telefono: Optional[str] = Field(default=None, max_length=15)
    logo: Optional[str] = Field(default=None, max_length=500)

    obligado_contabilidad: bool = Field(default=False)
    regimen: RegimenTributario = Field(default=RegimenTributario.GENERAL, nullable=False)
    modo_emision: ModoEmisionEmpresa = Field(default=ModoEmisionEmpresa.ELECTRONICO, nullable=False)

    # FK al catálogo (PK = 'codigo')
    tipo_contribuyente_id: str = Field(
        foreign_key="aux_tipo_contribuyente.codigo",
        nullable=False,
        max_length=2,
    )


def _serialize_for_audit(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    return value


@event.listens_for(Empresa, "after_update")
def _registrar_auditoria_regimen_modo_after_update(_mapper, connection, target: Empresa):
    state = sa_inspect(target)

    before_json: dict[str, str] = {}
    after_json: dict[str, str] = {}
    hubo_cambio = False

    for field_name in ("regimen", "modo_emision"):
        history = state.attrs[field_name].history
        old_value = history.deleted[0] if history.deleted else getattr(target, field_name)
        new_value = history.added[0] if history.added else getattr(target, field_name)

        before_json[field_name] = _serialize_for_audit(old_value)
        after_json[field_name] = _serialize_for_audit(new_value)
        hubo_cambio = hubo_cambio or history.has_changes()

    if not hubo_cambio:
        return

    from osiris.modules.common.audit_log.entity import AuditLog

    connection.execute(
        sa.insert(AuditLog.__table__).values(
            id=uuid4(),
            tabla_afectada="tbl_empresa",
            registro_id=str(target.id),
            entidad="Empresa",
            entidad_id=target.id,
            accion="UPDATE_REGIMEN_MODO",
            estado_anterior=before_json,
            estado_nuevo=after_json,
            before_json=before_json,
            after_json=after_json,
            usuario_id=getattr(target, "usuario_auditoria", None),
            usuario_auditoria=getattr(target, "usuario_auditoria", None),
            fecha=datetime.utcnow(),
            creado_en=datetime.utcnow(),
        )
    )

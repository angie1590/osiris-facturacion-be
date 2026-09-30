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


class TipoContribuyenteJuridico(str, Enum):
    PERSONA_NATURAL = "PERSONA_NATURAL"
    SOCIEDAD = "SOCIEDAD"


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
        CheckConstraint(
            (
                "NOT (tipo_contribuyente_juridico = 'SOCIEDAD' "
                "AND regimen = 'RIMPE_NEGOCIO_POPULAR')"
            ),
            name="ck_tbl_empresa_tipo_juridico_regimen",
        ),
        CheckConstraint(
            (
                "(contribuyente_especial = false AND contribuyente_especial_resolucion IS NULL) OR "
                "(contribuyente_especial = true AND trim(coalesce(contribuyente_especial_resolucion, '')) <> '')"
            ),
            name="ck_tbl_empresa_contribuyente_especial_resolucion",
        ),
        CheckConstraint(
            (
                "(gran_contribuyente = false AND gran_contribuyente_resolucion IS NULL) OR "
                "(gran_contribuyente = true AND trim(coalesce(gran_contribuyente_resolucion, '')) <> '')"
            ),
            name="ck_tbl_empresa_gran_contribuyente_resolucion",
        ),
        CheckConstraint(
            (
                "(agente_retencion = false AND agente_retencion_resolucion IS NULL) OR "
                "(agente_retencion = true AND trim(coalesce(agente_retencion_resolucion, '')) <> '')"
            ),
            name="ck_tbl_empresa_agente_retencion_resolucion",
        ),
    )

    razon_social: str = Field(index=True, nullable=False, max_length=255)
    nombre_comercial: Optional[str] = Field(default=None, max_length=255)

    # RUC ecuatoriano (13)
    ruc: str = Field(index=True, nullable=False, max_length=13)

    direccion_matriz: str = Field(nullable=False, max_length=255)
    email: Optional[str] = Field(default=None, max_length=255)
    telefono: Optional[str] = Field(default=None, max_length=15)
    logo: Optional[str] = Field(default=None, max_length=500)

    tipo_contribuyente_juridico: Optional[TipoContribuyenteJuridico] = Field(default=None, nullable=True)
    obligado_contabilidad: bool = Field(default=False)
    regimen: RegimenTributario = Field(default=RegimenTributario.GENERAL, nullable=False)

    contribuyente_especial: bool = Field(default=False, nullable=False)
    contribuyente_especial_resolucion: Optional[str] = Field(default=None, max_length=64)
    gran_contribuyente: bool = Field(default=False, nullable=False)
    gran_contribuyente_resolucion: Optional[str] = Field(default=None, max_length=64)
    agente_retencion: bool = Field(default=False, nullable=False)
    agente_retencion_resolucion: Optional[str] = Field(default=None, max_length=64)

    # Legacy: se mantiene por compatibilidad mientras FE técnica se consolida.
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

    tracked_fields = (
        "ruc",
        "razon_social",
        "nombre_comercial",
        "tipo_contribuyente_juridico",
        "tipo_contribuyente_id",
        "regimen",
        "obligado_contabilidad",
        "contribuyente_especial",
        "contribuyente_especial_resolucion",
        "gran_contribuyente",
        "gran_contribuyente_resolucion",
        "agente_retencion",
        "agente_retencion_resolucion",
        "direccion_matriz",
        "email",
        "telefono",
        "logo",
        "modo_emision",
    )

    for field_name in tracked_fields:
        if field_name not in state.attrs:
            continue
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
            accion="UPDATE_EMPRESA_TRIBUTARIA",
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

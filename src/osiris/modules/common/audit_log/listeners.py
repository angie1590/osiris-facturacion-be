from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.inspection import inspect as sa_inspect

from osiris.modules.common.audit_log.entity import AuditAction, AuditLog
from osiris.modules.sri.core_sri.models import Venta
from osiris.modules.inventario.producto.entity import Producto


_SKIP_DIFF_FIELDS = {
    "creado_en",
    "actualizado_en",
    "usuario_auditoria",
    "created_by",
    "updated_by",
}


def _serialize(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    return value


def _snapshot_model(target) -> dict:
    state = sa_inspect(target)
    data: dict = {}
    for attr in state.mapper.column_attrs:
        key = attr.key
        if key in _SKIP_DIFF_FIELDS:
            continue
        data[key] = _serialize(getattr(target, key))
    return data


def _diff_model_update(target) -> tuple[dict, dict]:
    state = sa_inspect(target)
    before: dict = {}
    after: dict = {}
    for attr in state.mapper.column_attrs:
        key = attr.key
        if key in _SKIP_DIFF_FIELDS:
            continue

        history = state.attrs[key].history
        if not history.has_changes():
            continue

        old_value = history.deleted[0] if history.deleted else None
        new_value = history.added[0] if history.added else getattr(target, key)
        old_ser = _serialize(old_value)
        new_ser = _serialize(new_value)

        if old_ser != new_ser:
            before[key] = old_ser
            after[key] = new_ser

    return before, after


def _current_actor(target) -> str | None:
    return (
        getattr(target, "updated_by", None)
        or getattr(target, "created_by", None)
        or getattr(target, "usuario_auditoria", None)
    )


def _write_audit(connection, *, target, accion: AuditAction, before: dict, after: dict) -> None:
    now = datetime.utcnow()
    table_name = target.__tablename__
    record_id = str(getattr(target, "id"))
    actor = _current_actor(target)

    connection.execute(
        sa.insert(AuditLog.__table__).values(
            tabla_afectada=table_name,
            registro_id=record_id,
            accion=accion.value,
            estado_anterior=before,
            estado_nuevo=after,
            usuario_id=actor,
            fecha=now,
            # Compatibilidad legado
            entidad=table_name,
            entidad_id=getattr(target, "id"),
            before_json=before,
            after_json=after,
            usuario_auditoria=actor,
            creado_en=now,
            created_by=actor,
            updated_by=actor,
        )
    )


@sa.event.listens_for(Producto, "after_insert")
@sa.event.listens_for(Venta, "after_insert")
def _audit_after_insert(_mapper, connection, target):
    _write_audit(
        connection,
        target=target,
        accion=AuditAction.CREATE,
        before={},
        after=_snapshot_model(target),
    )


@sa.event.listens_for(Producto, "after_update")
@sa.event.listens_for(Venta, "after_update")
def _audit_after_update(_mapper, connection, target):
    before, after = _diff_model_update(target)
    if not before and not after:
        return

    accion = AuditAction.UPDATE
    if before.get("activo") is True and after.get("activo") is False:
        accion = AuditAction.ANULAR if isinstance(target, Venta) else AuditAction.DELETE

    _write_audit(connection, target=target, accion=accion, before=before, after=after)


@sa.event.listens_for(Producto, "after_delete")
@sa.event.listens_for(Venta, "after_delete")
def _audit_after_delete(_mapper, connection, target):
    _write_audit(
        connection,
        target=target,
        accion=AuditAction.DELETE,
        before=_snapshot_model(target),
        after={},
    )

"""Add effective Product permissions and copy Inventory grants.

Revision ID: c8d7e9f1a204
Revises: f51c8a2d7e90
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "c8d7e9f1a204"
down_revision: Union[str, None] = "f51c8a2d7e90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACTOR = "migration_product_permissions"
PRODUCT_MODULE_CODE = "PRODUCTOS"
INVENTORY_MODULE_CODE = "INVENTARIO"


def _tables() -> tuple[sa.Table, sa.Table, sa.Table]:
    metadata = sa.MetaData()
    connection = op.get_bind()
    return tuple(
        sa.Table(name, metadata, autoload_with=connection)
        for name in ("tbl_modulo", "tbl_rol", "roles_modulos_permisos")
    )  # type: ignore[return-value]


def _audit() -> dict[str, Any]:
    now = datetime.utcnow()
    return {
        "activo": True,
        "creado_en": now,
        "actualizado_en": now,
        "usuario_auditoria": ACTOR,
        "created_by": ACTOR,
        "updated_by": ACTOR,
    }


def _new_id() -> Any:
    value = uuid4()
    return value.hex if op.get_bind().dialect.name == "sqlite" else value


def upgrade() -> None:
    modules, roles, grants = _tables()
    connection = op.get_bind()
    product_module_id = connection.scalar(
        sa.select(modules.c.id).where(modules.c.codigo == PRODUCT_MODULE_CODE)
    )
    if product_module_id is None:
        product_module_id = _new_id()
        connection.execute(
            modules.insert().values(
                id=product_module_id,
                codigo=PRODUCT_MODULE_CODE,
                nombre="Productos",
                descripcion="Gestión integral de productos",
                orden=21,
                icono="package",
                **_audit(),
            )
        )

    inventory_module_id = connection.scalar(
        sa.select(modules.c.id).where(
            modules.c.codigo == INVENTORY_MODULE_CODE,
            modules.c.activo.is_(True),
        )
    )
    if inventory_module_id is None:
        return

    inventory_grants = connection.execute(
        sa.select(
            grants.c.rol_id,
            grants.c.puede_leer,
            grants.c.puede_crear,
            grants.c.puede_actualizar,
            grants.c.puede_eliminar,
        )
        .select_from(grants.join(roles, grants.c.rol_id == roles.c.id))
        .where(
            grants.c.modulo_id == inventory_module_id,
            grants.c.activo.is_(True),
            roles.c.activo.is_(True),
        )
        .order_by(grants.c.rol_id)
    ).mappings()
    for inventory_grant in inventory_grants:
        existing = connection.scalar(
            sa.select(grants.c.id).where(
                grants.c.rol_id == inventory_grant["rol_id"],
                grants.c.modulo_id == product_module_id,
            )
        )
        if existing is not None:
            continue
        connection.execute(
            grants.insert().values(
                id=_new_id(),
                rol_id=inventory_grant["rol_id"],
                modulo_id=product_module_id,
                puede_leer=inventory_grant["puede_leer"],
                puede_crear=inventory_grant["puede_crear"],
                puede_actualizar=inventory_grant["puede_actualizar"],
                puede_eliminar=inventory_grant["puede_eliminar"],
                **_audit(),
            )
        )


def downgrade() -> None:
    modules, _roles, grants = _tables()
    connection = op.get_bind()
    product_module_id = connection.scalar(
        sa.select(modules.c.id).where(modules.c.codigo == PRODUCT_MODULE_CODE)
    )
    if product_module_id is None:
        return

    connection.execute(
        grants.delete().where(
            grants.c.modulo_id == product_module_id,
            grants.c.created_by == ACTOR,
            grants.c.updated_by == ACTOR,
        )
    )
    remaining_grant = connection.scalar(
        sa.select(grants.c.id).where(grants.c.modulo_id == product_module_id).limit(1)
    )
    module_created_here = connection.scalar(
        sa.select(modules.c.created_by).where(modules.c.id == product_module_id)
    ) == ACTOR
    if module_created_here and remaining_grant is None:
        connection.execute(modules.delete().where(modules.c.id == product_module_id))

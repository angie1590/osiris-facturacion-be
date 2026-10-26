"""Bootstrap explicitly approved directory modules and administrator grants.

Revision ID: a9c3d6e41f82
Revises: f8b2c5d30e71
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from alembic import op

revision = "a9c3d6e41f82"
down_revision = "f8b2c5d30e71"
branch_labels = None
depends_on = None
ACTOR = "migration_directory_bootstrap"
MODULES = {
    "PERSONAS": "Personas",
    "TIPOS_CLIENTE": "Tipos de Cliente",
    "CLIENTES": "Clientes",
    "PROVEEDORES_PERSONA": "Proveedores Persona",
    "PROVEEDORES_SOCIEDAD": "Proveedores Sociedad",
    "EMPLEADOS": "Empleados",
    "USUARIOS": "Usuarios",
}


def _tables() -> tuple[sa.Table, ...]:
    metadata = sa.MetaData()
    connection = op.get_bind()
    return tuple(
        sa.Table(name, metadata, autoload_with=connection)
        for name in (
            "tbl_modulo",
            "tbl_rol",
            "roles_modulos_permisos",
        )
    )


def _audit() -> dict[str, Any]:
    return {
        "activo": True,
        "creado_en": datetime.utcnow(),
        "actualizado_en": datetime.utcnow(),
        "usuario_auditoria": ACTOR,
        "created_by": ACTOR,
        "updated_by": ACTOR,
    }


def _new_id() -> UUID | str:
    value = uuid4()
    return value.hex if op.get_bind().dialect.name == "sqlite" else value


def upgrade() -> None:
    modules, roles, permissions = _tables()
    connection = op.get_bind()
    administrators = (
        connection.execute(
            sa.select(roles.c.id).where(
                sa.func.lower(sa.func.trim(roles.c.nombre)).in_(
                    ["administrador", "admin"]
                ),
                roles.c.activo.is_(True),
            )
        )
        .scalars()
        .all()
    )
    for position, (code, name) in enumerate(MODULES.items(), start=20):
        module_id = connection.scalar(
            sa.select(modules.c.id).where(modules.c.codigo == code)
        )
        if module_id is None:
            module_id = _new_id()
            connection.execute(
                modules.insert().values(
                    id=module_id,
                    codigo=code,
                    nombre=name,
                    descripcion="Directorio: permisos por entidad",
                    orden=position,
                    icono="users",
                    **_audit(),
                )
            )
        for role_id in administrators:
            existing = connection.scalar(
                sa.select(permissions.c.id).where(
                    permissions.c.rol_id == role_id,
                    permissions.c.modulo_id == module_id,
                )
            )
            if existing is None:
                connection.execute(
                    permissions.insert().values(
                        id=_new_id(),
                        rol_id=role_id,
                        modulo_id=module_id,
                        puede_leer=True,
                        puede_crear=True,
                        puede_actualizar=True,
                        puede_eliminar=True,
                        **_audit(),
                    )
                )


def downgrade() -> None:
    modules, _, permissions = _tables()
    connection = op.get_bind()
    module_ids = (
        connection.execute(
            sa.select(modules.c.id).where(
                modules.c.codigo.in_(list(MODULES)),
                modules.c.created_by == ACTOR,
            )
        )
        .scalars()
        .all()
    )
    altered_grant = connection.execute(
        sa.select(permissions.c.id)
        .where(
            permissions.c.modulo_id.in_(module_ids),
            sa.or_(
                permissions.c.created_by != ACTOR,
                permissions.c.updated_by != ACTOR,
                permissions.c.created_by.is_(None),
                permissions.c.updated_by.is_(None),
            ),
        )
        .limit(1)
    ).first()
    if altered_grant is not None:
        raise RuntimeError(
            "No revertir RBAC con permisos administrados posteriormente; requiere revision explicita"
        )
    connection.execute(
        permissions.delete().where(
            permissions.c.created_by == ACTOR, permissions.c.updated_by == ACTOR
        )
    )
    connection.execute(modules.delete().where(modules.c.id.in_(module_ids)))

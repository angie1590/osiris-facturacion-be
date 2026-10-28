from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

VERSIONS = Path(__file__).parents[1] / "src/osiris/db/alembic/versions"
MIGRATION_FILE = "c8d7e9f1a204_add_product_permissions.py"


def _load_migration():
    spec = importlib.util.spec_from_file_location(MIGRATION_FILE, VERSIONS / MIGRATION_FILE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _database(*, product_module_exists: bool = False):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    modules = sa.Table(
        "tbl_modulo",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("codigo", sa.String(50), nullable=False, unique=True),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("descripcion", sa.String(255)),
        sa.Column("orden", sa.Integer()),
        sa.Column("icono", sa.String(50)),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(255)),
        sa.Column("updated_by", sa.String(255)),
        sa.Column("usuario_auditoria", sa.String(255)),
    )
    roles = sa.Table(
        "tbl_rol",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
    )
    grants = sa.Table(
        "roles_modulos_permisos",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("rol_id", sa.Uuid(), nullable=False),
        sa.Column("modulo_id", sa.Uuid(), nullable=False),
        sa.Column("puede_leer", sa.Boolean(), nullable=False),
        sa.Column("puede_crear", sa.Boolean(), nullable=False),
        sa.Column("puede_actualizar", sa.Boolean(), nullable=False),
        sa.Column("puede_eliminar", sa.Boolean(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(255)),
        sa.Column("updated_by", sa.String(255)),
        sa.Column("usuario_auditoria", sa.String(255)),
        sa.UniqueConstraint("rol_id", "modulo_id", name="uq_rol_modulo"),
    )
    metadata.create_all(engine)
    inventory_id = uuid4()
    roles_by_name = {name: uuid4() for name in ("Admin", "Jefe de Almacén", "Vendedor", "Inactivo")}
    with engine.begin() as connection:
        connection.execute(
            modules.insert().values(
                id=inventory_id,
                codigo="INVENTARIO",
                nombre="Inventario",
                activo=True,
                creado_en=datetime.utcnow(),
                actualizado_en=datetime.utcnow(),
            )
        )
        connection.execute(
            roles.insert(),
            [
                {"id": role_id, "nombre": name, "activo": name != "Inactivo"}
                for name, role_id in roles_by_name.items()
            ],
        )
        flags = {
            "Admin": (True, True, True, True),
            "Jefe de Almacén": (True, True, True, True),
            "Vendedor": (True, False, False, False),
            "Inactivo": (True, True, True, True),
        }
        connection.execute(
            grants.insert(),
            [
                {
                    "id": uuid4(),
                    "rol_id": role_id,
                    "modulo_id": inventory_id,
                    "puede_leer": flags[name][0],
                    "puede_crear": flags[name][1],
                    "puede_actualizar": flags[name][2],
                    "puede_eliminar": flags[name][3],
                    "activo": True,
                    "creado_en": datetime.utcnow(),
                    "actualizado_en": datetime.utcnow(),
                }
                for name, role_id in roles_by_name.items()
            ],
        )
        if product_module_exists:
            product_id = uuid4()
            connection.execute(
                modules.insert().values(
                    id=product_id,
                    codigo="PRODUCTOS",
                    nombre="Productos",
                    activo=True,
                    creado_en=datetime.utcnow(),
                    actualizado_en=datetime.utcnow(),
                    created_by="manual",
                )
            )
            connection.execute(
                grants.insert().values(
                    id=uuid4(),
                    rol_id=roles_by_name["Vendedor"],
                    modulo_id=product_id,
                    puede_leer=False,
                    puede_crear=False,
                    puede_actualizar=True,
                    puede_eliminar=False,
                    activo=True,
                    creado_en=datetime.utcnow(),
                    actualizado_en=datetime.utcnow(),
                    created_by="manual",
                    updated_by="manual",
                )
            )
    return engine, modules, roles, grants, roles_by_name


def _run(engine, operation) -> None:
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            operation()


def test_product_permission_migration_copies_inventory_matrix_idempotently():
    migration = _load_migration()
    engine, modules, _roles, grants, roles_by_name = _database()

    _run(engine, migration.upgrade)
    _run(engine, migration.upgrade)

    with engine.connect() as connection:
        product_id = connection.scalar(
            sa.select(modules.c.id).where(modules.c.codigo == "PRODUCTOS")
        )
        copied = {
            row["rol_id"]: (
                row["puede_leer"],
                row["puede_crear"],
                row["puede_actualizar"],
                row["puede_eliminar"],
            )
            for row in connection.execute(
                sa.select(grants).where(grants.c.modulo_id == product_id)
            ).mappings()
        }
        assert len(copied) == 3
        assert copied[roles_by_name["Admin"]] == (True, True, True, True)
        assert copied[roles_by_name["Jefe de Almacén"]] == (True, True, True, True)
        assert copied[roles_by_name["Vendedor"]] == (True, False, False, False)
        assert all(
            row["created_by"] == migration.ACTOR
            for row in connection.execute(
                sa.select(grants).where(grants.c.modulo_id == product_id)
            ).mappings()
        )

    _run(engine, migration.downgrade)
    with engine.connect() as connection:
        assert connection.scalar(
            sa.select(sa.func.count()).select_from(modules).where(modules.c.codigo == "PRODUCTOS")
        ) == 0
    engine.dispose()


def test_product_permission_migration_preserves_existing_product_grants():
    migration = _load_migration()
    engine, modules, _roles, grants, roles_by_name = _database(product_module_exists=True)

    _run(engine, migration.upgrade)

    with engine.connect() as connection:
        product_id = connection.scalar(
            sa.select(modules.c.id).where(modules.c.codigo == "PRODUCTOS")
        )
        seller_grant = connection.execute(
            sa.select(grants).where(
                grants.c.modulo_id == product_id,
                grants.c.rol_id == roles_by_name["Vendedor"],
            )
        ).mappings().one()
        assert (
            seller_grant["puede_leer"],
            seller_grant["puede_crear"],
            seller_grant["puede_actualizar"],
            seller_grant["puede_eliminar"],
        ) == (False, False, True, False)
        assert seller_grant["created_by"] == "manual"

    _run(engine, migration.downgrade)
    with engine.connect() as connection:
        assert connection.scalar(
            sa.select(sa.func.count()).select_from(modules).where(modules.c.codigo == "PRODUCTOS")
        ) == 1
    engine.dispose()

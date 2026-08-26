from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool
from sqlmodel import SQLModel

from osiris.core.settings import get_settings

# IMPORTA tus modelos para que Alembic detecte las tablas
from osiris.modules.sri.impuesto_catalogo import entity as impuesto_catalogo_entity  # noqa: F401
from osiris.modules.sri.tipo_contribuyente import entity as tipo_contribuyente_entity  # noqa: F401
from osiris.modules.common.rol import entity as rol_entity  # noqa: F401
from osiris.modules.common.audit_log import entity as audit_log_entity  # noqa: F401
from osiris.modules.common.empresa import entity as empresa_entity  # noqa: F401
from osiris.modules.common.sucursal import entity as sucursal_entity  # noqa: F401
from osiris.modules.common.punto_emision import entity as punto_emision_entity  # noqa: F401
from osiris.modules.common.persona import entity as persona_entity  # noqa: F401
from osiris.modules.common.tipo_cliente import entity as tipo_cliente_entity  # noqa: F401
from osiris.modules.common.usuario import entity as usuario_entity  # noqa: F401
from osiris.modules.common.cliente import entity as cliente_entity  # noqa: F401
from osiris.modules.common.empleado import entity as empleado_entity  # noqa: F401
from osiris.modules.common.proveedor_persona import entity as proveedor_persona  # noqa: F401
from osiris.modules.common.proveedor_sociedad import entity as proveedor_sociedad  # noqa: F401
from osiris.modules.common.modulo import entity as modulo_entity  # noqa: F401
from osiris.modules.common.rol_modulo_permiso import entity as rol_modulo_permiso_entity  # noqa: F401
from osiris.modules.inventario.categoria import entity as categoria_entity  # noqa: F401
from osiris.modules.inventario.casa_comercial import entity as casa_comercial_entity  # noqa: F401
from osiris.modules.inventario.atributo import entity as atributo_entity  # noqa: F401
from osiris.modules.inventario.producto import entity as producto_entity  # noqa: F401
from osiris.modules.inventario.producto import models_atributos as producto_atributos_entity  # noqa: F401
from osiris.modules.inventario.categoria_atributo import entity as categoria_atributo_entity  # noqa: F401
from osiris.modules.inventario.bodega import entity as bodega_entity  # noqa: F401
from osiris.modules.inventario.movimientos import models as movimiento_inventario_entity  # noqa: F401
from osiris.modules.compras import models as compras_entity  # noqa: F401
from osiris.modules.ventas import models as ventas_entity  # noqa: F401
from osiris.modules.sri.facturacion_electronica import models as fe_entity  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def _get_database_url() -> str:
    """
    Prioridad:
    1) DB_URL_ALEMBIC desde variable de entorno
    2) DB_URL_ALEMBIC desde settings
    3) DATABASE_URL desde settings
    """
    override = os.getenv("DB_URL_ALEMBIC")
    if override:
        return override

    settings = get_settings()
    return settings.DB_URL_ALEMBIC or settings.DATABASE_URL


def run_migrations_offline() -> None:
    """Modo offline: sin Engine."""
    url = _get_database_url()
    config.set_main_option("sqlalchemy.url", url)

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Modo online: con Engine y conexion activa."""
    url = _get_database_url()
    config.set_main_option("sqlalchemy.url", url)

    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

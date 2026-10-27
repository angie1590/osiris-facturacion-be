"""Add the frozen v2 measurement catalog and stable attribute identities."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

revision = "e1a6c2d9b740"
down_revision = "c5e91a7d2b64"
branch_labels = None
depends_on = None

UNITS_V2 = (
    ("UNIDAD", "Unidad", "u", "COUNT"),
    ("GRAMO", "Gramo", "g", "MASS"),
    ("KILOGRAMO", "Kilogramo", "kg", "MASS"),
    ("LIBRA", "Libra", "lb", "MASS"),
    ("MILILITRO", "Mililitro", "mL", "VOLUME"),
    ("LITRO", "Litro", "L", "VOLUME"),
    ("MILIMETRO", "Mil\u00edmetro", "mm", "LENGTH"),
    ("CENTIMETRO", "Cent\u00edmetro", "cm", "LENGTH"),
    ("METRO", "Metro", "m", "LENGTH"),
    ("PULGADA", "Pulgada", "in", "LENGTH"),
    ("SEGUNDO", "Segundo", "s", "TIME"),
    ("MINUTO", "Minuto", "min", "TIME"),
    ("HORA", "Hora", "h", "TIME"),
    ("MEGABYTE", "Megabyte", "MB", "DATA_STORAGE"),
    ("GIGABYTE", "Gigabyte", "GB", "DATA_STORAGE"),
    ("TERABYTE", "Terabyte", "TB", "DATA_STORAGE"),
    ("MEBIBYTE", "Mebibyte", "MiB", "DATA_STORAGE"),
    ("GIBIBYTE", "Gibibyte", "GiB", "DATA_STORAGE"),
    ("MEGAHERCIO", "Megahercio", "MHz", "FREQUENCY"),
    ("GIGAHERCIO", "Gigahercio", "GHz", "FREQUENCY"),
    ("PUNTOS_POR_PULGADA", "Puntos por pulgada", "dpi", "RESOLUTION_DENSITY"),
    ("PORCENTAJE", "Porcentaje", "%", "PERCENTAGE"),
)


def _attribute_code(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    code = re.sub("[^a-z0-9]+", "_", ascii_name.lower()).strip("_") or "atributo"
    if code[0].isdigit():
        code = "atributo_" + code
    if len(code) > 120:
        raise RuntimeError(
            f"ATTRIBUTE_CODE_TOO_LONG: {name!r} generates {len(code)} characters (max 120). "
            "Resolve the source name explicitly before retrying; no truncation is permitted."
        )
    return code


def _preflight(connection: Connection) -> list[tuple[Any, str]]:
    metadata = sa.MetaData()
    attributes = sa.Table("tbl_atributo", metadata, autoload_with=connection)
    categories = sa.Table("tbl_categoria", metadata, autoload_with=connection)
    mappings = sa.Table("tbl_categoria_atributo", metadata, autoload_with=connection)
    errors: list[str] = []

    def duplicates(table: sa.Table, keys: list[Any], code: str, active: bool = False) -> None:
        statement = sa.select(*keys).group_by(*keys).having(sa.func.count() > 1)
        if active:
            statement = statement.where(table.c.activo.is_(True))
        for key in connection.execute(statement):
            predicate = sa.and_(*(column.is_(None) if value is None else column == value
                                  for column, value in zip(keys, key)))
            ids = list(connection.execute(sa.select(table.c.id).where(predicate)).scalars())
            errors.append(f"{code}: key={tuple(key)!r}, ids={list(map(str, ids))}")

    duplicates(attributes, [sa.func.lower(sa.func.trim(attributes.c.nombre))],
               "ATTRIBUTE_DUPLICATE_NAME", True)
    duplicates(categories, [categories.c.parent_id, sa.func.lower(sa.func.trim(categories.c.nombre))],
               "CATEGORY_DUPLICATE_NAME")
    duplicates(mappings, [mappings.c.categoria_id, mappings.c.atributo_id],
               "CATEGORY_ATTRIBUTE_DUPLICATE")
    generated: list[tuple[Any, str]] = []
    code_ids: dict[str, list[str]] = defaultdict(list)
    attribute_ids: set[Any] = set()
    for row in connection.execute(sa.select(attributes)).mappings():
        attribute_ids.add(row["id"])
        try:
            code = _attribute_code(row["nombre"])
        except RuntimeError as exc:
            errors.append(f"{exc} id={row['id']}")
            continue
        generated.append((row["id"], code))
        code_ids[code].append(str(row["id"]))
    for code, ids in code_ids.items():
        if len(ids) > 1:
            errors.append(f"ATTRIBUTE_DUPLICATE_CODE: codigo={code!r}, ids={ids}")

    category_rows = {row["id"]: row for row in
                     connection.execute(sa.select(categories)).mappings()}
    active_parents = {row["parent_id"] for row in category_rows.values() if row["activo"]}
    for category_id, row in category_rows.items():
        parent_id = row["parent_id"]
        parent = category_rows.get(parent_id)
        if parent_id is not None and (
            parent is None or (row["activo"] and not parent["activo"])
        ):
            errors.append(f"CATEGORY_PARENT_INVALID: id={category_id}, parent_id={parent_id}")
        if row["is_default"] and (
            parent is None or parent["is_default"] or category_id in active_parents
        ):
            errors.append(f"CATEGORY_DEFAULT_INVALID: id={category_id}")
        visited: set[Any] = set()
        current = category_id
        while current in category_rows:
            if current in visited:
                errors.append(f"CATEGORY_CYCLE: ids={list(map(str, visited))}")
                break
            visited.add(current)
            current = category_rows[current]["parent_id"]
    for row in connection.execute(sa.select(mappings)).mappings():
        if row["categoria_id"] not in category_rows or row["atributo_id"] not in attribute_ids:
            errors.append(f"CATEGORY_ATTRIBUTE_REFERENCE_INVALID: id={row['id']}")
    if errors:
        raise RuntimeError(
            "Catalog preflight blocked before DDL. Resolve conflicts explicitly; "
            "no merge, suffix or arbitrary survivor is permitted:\n" + "\n".join(errors)
        )
    return generated


def _sqlite_indexes(connection: Connection) -> dict[str, str]:
    if connection.dialect.name != "sqlite":
        return {}
    return {name: statement for name, statement in connection.execute(sa.text(
        "SELECT name, sql FROM sqlite_master WHERE type='index' "
        "AND tbl_name='tbl_atributo' AND sql IS NOT NULL"
    ))}


def _restore_indexes(connection: Connection, indexes: dict[str, str]) -> None:
    if not indexes:
        return
    current = set(connection.execute(sa.text(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='tbl_atributo'"
    )).scalars())
    for name, statement in indexes.items():
        if name not in current:
            connection.exec_driver_sql(statement)


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        connection.execute(sa.text(
            "LOCK TABLE tbl_atributo, tbl_categoria, tbl_categoria_atributo "
            "IN SHARE ROW EXCLUSIVE MODE"
        ))
    generated = _preflight(connection)
    if connection.dialect.name == "sqlite" and connection.exec_driver_sql(
        "PRAGMA foreign_keys"
    ).scalar_one():
        raise RuntimeError(
            "SQLite batch requires PRAGMA foreign_keys=OFF before the migration transaction; "
            "run foreign_key_check and restore enforcement afterwards. Blocked before DDL."
        )
    indexes = _sqlite_indexes(connection)
    symbol_type = sa.String(32, collation="C" if connection.dialect.name == "postgresql"
                            else "BINARY")
    units = op.create_table(
        "tbl_unidad",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.Column("usuario_auditoria", sa.String(255), nullable=True),
        sa.Column("codigo", sa.String(64), nullable=False),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("simbolo", symbol_type, nullable=False),
        sa.Column("magnitud_codigo", sa.String(64), nullable=False),
        sa.Column("es_sistema", sa.Boolean(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        *(sa.CheckConstraint(
            f"length(trim({field}, ' \t\n\r\v\f')) > 0 AND length({field}) <= {limit}",
            name=f"ck_tbl_unidad_{field}_contenido",
        ) for field, limit in (("codigo", 64), ("nombre", 120), ("simbolo", 32),
                               ("magnitud_codigo", 64))),
    )
    op.create_index("uq_tbl_unidad_codigo_normalizado", "tbl_unidad",
                    [sa.text("lower(trim(codigo))")], unique=True)
    op.create_index("uq_tbl_unidad_simbolo_exacto", "tbl_unidad", ["simbolo"],
                    unique=True)
    for column in ("created_by", "updated_by", "activo"):
        op.create_index("ix_tbl_unidad_" + column, "tbl_unidad", [column])
    stamp = datetime(2026, 10, 25)
    op.bulk_insert(units, [
        {"id": uuid5(NAMESPACE_URL, "osiris:unidad:" + code), "codigo": code,
         "nombre": name, "simbolo": symbol, "magnitud_codigo": magnitude,
         "es_sistema": True, "activo": True, "creado_en": stamp, "actualizado_en": stamp,
         "created_by": revision, "updated_by": revision, "usuario_auditoria": revision}
        for code, name, symbol, magnitude in UNITS_V2
    ])
    op.add_column("tbl_atributo", sa.Column("codigo", sa.String(120), nullable=True))
    attributes = sa.table("tbl_atributo", sa.column("id"), sa.column("codigo"))
    for attribute_id, code in generated:
        connection.execute(attributes.update().where(attributes.c.id == attribute_id)
                           .values(codigo=code))
    normalized_check = (
        "codigo ~ '^[a-z][a-z0-9]*(_[a-z0-9]+)*$'"
        if connection.dialect.name == "postgresql" else
        "codigo NOT GLOB '*[^a-z0-9_]*' AND substr(codigo, 1, 1) GLOB '[a-z]' "
        "AND substr(codigo, -1) != '_' AND instr(codigo, '__') = 0"
    )
    with op.batch_alter_table("tbl_atributo") as batch:
        batch.alter_column("codigo", existing_type=sa.String(120), nullable=False)
        batch.add_column(sa.Column("unidad_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key("fk_tbl_atributo_unidad_id", "tbl_unidad", ["unidad_id"], ["id"])
        batch.create_check_constraint(
            "ck_tbl_atributo_unidad_tipo_numerico",
            "unidad_id IS NULL OR lower(CAST(tipo_dato AS TEXT)) IN ('integer', 'decimal')",
        )
        batch.create_check_constraint("ck_tbl_atributo_codigo_normalized",
                                      "length(codigo) BETWEEN 1 AND 120 AND " + normalized_check)
        batch.create_index("ix_tbl_atributo_unidad_id", ["unidad_id"])
    _restore_indexes(connection, indexes)
    op.create_index("uq_tbl_atributo_codigo_normalizado", "tbl_atributo", [sa.text("lower(trim(codigo))")],
                    unique=True)


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        connection.execute(sa.text(
            "LOCK TABLE tbl_atributo, tbl_unidad, tbl_atributo_cambio "
            "IN SHARE ROW EXCLUSIVE MODE"
        ))
    if connection.execute(sa.text("SELECT id FROM tbl_atributo LIMIT 1")).first() or (
        connection.execute(sa.text("SELECT id FROM tbl_atributo_cambio LIMIT 1")).first()
    ):
        raise RuntimeError(
            "Cannot downgrade: stable attribute codes, units or snapshots would be lost. "
            "Preserve the schema and use an operational rollback."
        )
    units = sa.Table("tbl_unidad", sa.MetaData(), autoload_with=connection)
    expected = {str(uuid5(NAMESPACE_URL, "osiris:unidad:" + code)): (code, name, symbol, magnitude)
                for code, name, symbol, magnitude in UNITS_V2}
    for row in connection.execute(sa.select(units)).mappings():
        original = expected.get(str(UUID(str(row["id"]))))
        if original is None:
            raise RuntimeError("Cannot downgrade: custom unit history would be lost.")
        if original != (row["codigo"], row["nombre"], row["simbolo"], row["magnitud_codigo"]) or (
            not row["es_sistema"] or not row["activo"]
            or row["creado_en"] != datetime(2026, 10, 25)
            or row["actualizado_en"] != datetime(2026, 10, 25)
            or any(row[field] != revision for field in
                   ("created_by", "updated_by", "usuario_auditoria"))
        ):
            raise RuntimeError("Cannot downgrade: modified unit history would be lost.")
    indexes = _sqlite_indexes(connection)
    indexes.pop("uq_tbl_atributo_codigo_normalizado", None)
    indexes.pop("ix_tbl_atributo_unidad_id", None)
    op.drop_index("uq_tbl_atributo_codigo_normalizado", table_name="tbl_atributo")
    with op.batch_alter_table("tbl_atributo") as batch:
        batch.drop_index("ix_tbl_atributo_unidad_id")
        batch.drop_constraint("fk_tbl_atributo_unidad_id", type_="foreignkey")
        batch.drop_constraint("ck_tbl_atributo_unidad_tipo_numerico", type_="check")
        batch.drop_constraint("ck_tbl_atributo_codigo_normalized", type_="check")
        batch.drop_column("unidad_id")
        batch.drop_column("codigo")
    _restore_indexes(connection, indexes)
    op.drop_index("uq_tbl_unidad_codigo_normalizado", table_name="tbl_unidad")
    op.drop_index("uq_tbl_unidad_simbolo_exacto", table_name="tbl_unidad")
    op.drop_table("tbl_unidad")
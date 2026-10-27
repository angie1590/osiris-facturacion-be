from __future__ import annotations

import json
import importlib.util
from pathlib import Path
import sys

import pytest
import sqlalchemy as sa

from osiris.utils.catalog_preflight import audit_catalog


def catalog_engine():
    metadata = sa.MetaData()
    sa.Table(
        "tbl_categoria",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("nombre", sa.String),
        sa.Column("parent_id", sa.String),
        sa.Column("activo", sa.Boolean),
        sa.Column("es_padre", sa.Boolean),
        sa.Column("is_default", sa.Boolean),
    )
    sa.Table(
        "tbl_atributo",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("nombre", sa.String),
        sa.Column("codigo", sa.String),
        sa.Column("tipo_dato", sa.String),
        sa.Column("activo", sa.Boolean),
    )
    sa.Table(
        "tbl_categoria_atributo",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("categoria_id", sa.String),
        sa.Column("atributo_id", sa.String),
        sa.Column("obligatorio", sa.Boolean),
        sa.Column("valor_default", sa.String),
        sa.Column("activo", sa.Boolean),
    )
    sa.Table(
        "tbl_producto",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("nombre", sa.String),
        sa.Column("activo", sa.Boolean),
    )
    sa.Table(
        "tbl_producto_categoria",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("producto_id", sa.String),
        sa.Column("categoria_id", sa.String),
    )
    sa.Table(
        "tbl_producto_atributo_valor",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("producto_id", sa.String),
        sa.Column("atributo_id", sa.String),
        sa.Column("valor_string", sa.String),
        sa.Column("valor_integer", sa.Integer),
        sa.Column("valor_decimal", sa.Numeric),
        sa.Column("valor_boolean", sa.Boolean),
        sa.Column("valor_date", sa.Date),
        sa.Column("activo", sa.Boolean),
    )
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)
    return engine, metadata


def snapshot(connection, metadata):
    return {
        name: [
            dict(row)
            for row in connection.execute(sa.select(table).order_by(table.c.id)).mappings()
        ]
        for name, table in metadata.tables.items()
    }


def test_catalog_preflight_reports_historical_duplicates_cycles_and_never_mutates():
    engine, metadata = catalog_engine()
    with engine.begin() as connection:
        connection.execute(
            metadata.tables["tbl_categoria"].insert(),
            [
                {
                    "id": "root",
                    "nombre": "Perifericos",
                    "parent_id": None,
                    "activo": True,
                    "es_padre": True,
                    "is_default": False,
                },
                {
                    "id": "first",
                    "nombre": "Mouse",
                    "parent_id": "root",
                    "activo": True,
                    "es_padre": False,
                    "is_default": False,
                },
                {
                    "id": "second",
                    "nombre": " mouse ",
                    "parent_id": "root",
                    "activo": False,
                    "es_padre": False,
                    "is_default": False,
                },
                {
                    "id": "cycle-a",
                    "nombre": "A",
                    "parent_id": "cycle-b",
                    "activo": True,
                    "es_padre": True,
                    "is_default": False,
                },
                {
                    "id": "cycle-b",
                    "nombre": "B",
                    "parent_id": "cycle-a",
                    "activo": True,
                    "es_padre": True,
                    "is_default": False,
                },
            ],
        )
        connection.execute(
            metadata.tables["tbl_atributo"].insert(),
            [
                {
                    "id": "attr-a",
                    "nombre": "Marca",
                    "codigo": "marca",
                    "tipo_dato": "string",
                    "activo": True,
                },
                {
                    "id": "attr-b",
                    "nombre": " MARCA ",
                    "codigo": "MARCA",
                    "tipo_dato": "string",
                    "activo": True,
                },
            ],
        )
        connection.execute(
            metadata.tables["tbl_categoria_atributo"].insert(),
            [
                {
                    "id": "mapping-a",
                    "categoria_id": "first",
                    "atributo_id": "attr-a",
                    "obligatorio": False,
                    "activo": True,
                },
                {
                    "id": "mapping-b",
                    "categoria_id": "first",
                    "atributo_id": "attr-a",
                    "obligatorio": False,
                    "activo": False,
                },
            ],
        )
        before = snapshot(connection, metadata)
        report = audit_catalog(connection)
        assert snapshot(connection, metadata) == before
        assert report == audit_catalog(connection)
        assert report["apto_para_migrar"] is False
        codes = {issue["code"] for issue in report["conflictos"]}
        assert {
            "CATEGORY_DUPLICATE_NAME",
            "CATEGORY_CYCLE",
            "ATTRIBUTE_DUPLICATE_NAME",
            "ATTRIBUTE_DUPLICATE_CODE",
            "CATEGORY_ATTRIBUTE_DUPLICATE",
        } <= codes
        duplicate = next(
            issue for issue in report["conflictos"] if issue["code"] == "CATEGORY_DUPLICATE_NAME"
        )
        assert duplicate["ids"] == ["first", "second"]
        json.dumps(report)


def test_catalog_preflight_fails_closed_when_required_schema_is_missing():
    with sa.create_engine("sqlite://").connect() as connection:
        report = audit_catalog(connection)
        assert report["apto_para_migrar"] is False
        assert report["conflictos"][0]["code"] == "CATALOG_SCHEMA_INCOMPLETE"


def test_preflight_checks_future_codes_even_before_code_column_is_deployed():
    engine, metadata = catalog_engine()
    with engine.begin() as connection:
        connection.execute(metadata.tables["tbl_atributo"].insert(), [
            {"id": "first", "nombre": "Resolucion", "tipo_dato": "integer", "activo": True},
            {"id": "historical", "nombre": "Resoluci\u00f3n", "tipo_dato": "integer", "activo": False},
        ])
        connection.exec_driver_sql("ALTER TABLE tbl_atributo DROP COLUMN codigo")
        report = audit_catalog(connection)
        collision = next(issue for issue in report["conflictos"] if issue["code"] == "ATTRIBUTE_DUPLICATE_CODE")
        assert collision["ids"] == ["first", "historical"]
        assert collision["clave_normalizada"] == "resolucion"
        assert collision["codigo_previsto"] is True
        assert report["apto_para_migrar"] is False


@pytest.mark.parametrize("name", ["Mouse", " mouse ", "MOUSE"])
def test_same_category_name_in_different_branches_is_allowed(name):
    engine, metadata = catalog_engine()
    with engine.begin() as connection:
        connection.execute(
            metadata.tables["tbl_categoria"].insert(),
            [
                {
                    "id": "root-a",
                    "nombre": "A",
                    "parent_id": None,
                    "activo": True,
                    "es_padre": True,
                    "is_default": False,
                },
                {
                    "id": "root-b",
                    "nombre": "B",
                    "parent_id": None,
                    "activo": True,
                    "es_padre": True,
                    "is_default": False,
                },
                {
                    "id": "first",
                    "nombre": name,
                    "parent_id": "root-a",
                    "activo": True,
                    "es_padre": False,
                    "is_default": False,
                },
                {
                    "id": "second",
                    "nombre": "Mouse",
                    "parent_id": "root-b",
                    "activo": True,
                    "es_padre": False,
                    "is_default": False,
                },
            ],
        )
        assert audit_catalog(connection)["apto_para_migrar"] is True


def test_products_report_missing_multiple_invalid_and_required_without_inferred_units():
    engine, metadata = catalog_engine()
    with engine.begin() as connection:
        connection.execute(
            metadata.tables["tbl_categoria"].insert(),
            [
                {
                    "id": "root",
                    "nombre": "Tecnologia",
                    "parent_id": None,
                    "activo": True,
                    "es_padre": True,
                    "is_default": False,
                },
                {
                    "id": "leaf",
                    "nombre": "Mouse",
                    "parent_id": "root",
                    "activo": True,
                    "es_padre": False,
                    "is_default": False,
                },
                {
                    "id": "other",
                    "nombre": "Teclado",
                    "parent_id": "root",
                    "activo": True,
                    "es_padre": False,
                    "is_default": False,
                },
            ],
        )
        connection.execute(
            metadata.tables["tbl_atributo"].insert(),
            [
                {
                    "id": "ram",
                    "nombre": "RAM",
                    "codigo": "ram",
                    "tipo_dato": "integer",
                    "activo": True,
                },
            ],
        )
        connection.execute(
            metadata.tables["tbl_categoria_atributo"].insert(),
            [
                {
                    "id": "required",
                    "categoria_id": "root",
                    "atributo_id": "ram",
                    "obligatorio": True,
                    "valor_default": "16",
                    "activo": True,
                },
            ],
        )
        connection.execute(
            metadata.tables["tbl_producto"].insert(),
            [
                {"id": name, "nombre": name, "activo": True}
                for name in ["without", "multiple", "non-leaf", "missing-value", "zero"]
            ],
        )
        connection.execute(
            metadata.tables["tbl_producto_categoria"].insert(),
            [
                {"id": "m1", "producto_id": "multiple", "categoria_id": "leaf"},
                {"id": "m2", "producto_id": "multiple", "categoria_id": "other"},
                {"id": "m3", "producto_id": "non-leaf", "categoria_id": "root"},
                {"id": "m4", "producto_id": "missing-value", "categoria_id": "leaf"},
                {"id": "m5", "producto_id": "zero", "categoria_id": "leaf"},
            ],
        )
        connection.execute(
            metadata.tables["tbl_producto_atributo_valor"].insert(),
            [
                {
                    "id": "zero-value",
                    "producto_id": "zero",
                    "atributo_id": "ram",
                    "valor_integer": 0,
                    "activo": True,
                },
            ],
        )
        before = snapshot(connection, metadata)
        report = audit_catalog(connection)
        codes = {issue["code"] for issue in report["conflictos"]}
        assert {
            "PRODUCT_CATEGORY_REQUIRED",
            "PRODUCT_CATEGORY_AMBIGUOUS",
            "PRODUCT_CATEGORY_NOT_LEAF",
            "PRODUCT_REQUIRED_ATTRIBUTES_MISSING",
        } <= codes
        missing = next(
            issue
            for issue in report["conflictos"]
            if issue["code"] == "PRODUCT_REQUIRED_ATTRIBUTES_MISSING"
        )
        assert missing["ids"] == ["missing-value"]
        assert missing["atributo_id"] == "ram"
        assert report["candidatos_anotacion_unidad"] == []
        annotated = audit_catalog(connection, unit_candidates={"ram": "GIGABYTE"})
        assert annotated["candidatos_anotacion_unidad"][0]["unidad_codigo_propuesto"] == "GIGABYTE"
        assert annotated["candidatos_anotacion_unidad"][0]["requiere_confirmacion"] is True
        assert snapshot(connection, metadata) == before


def test_preflight_compares_primary_category_with_legacy_projection_and_lists_backfill_candidates():
    engine, metadata = catalog_engine()
    with engine.begin() as connection:
        connection.execute(
            metadata.tables["tbl_categoria"].insert(),
            [
                {"id": "root", "nombre": "Tecnologia", "parent_id": None, "activo": True, "es_padre": True, "is_default": False},
                {"id": "mouse", "nombre": "Mouse", "parent_id": "root", "activo": True, "es_padre": False, "is_default": False},
                {"id": "teclado", "nombre": "Teclado", "parent_id": "root", "activo": True, "es_padre": False, "is_default": False},
            ],
        )
        connection.execute(
            metadata.tables["tbl_producto"].insert(),
            [
                {"id": "conflict", "nombre": "Conflicto", "activo": True},
                {"id": "candidate", "nombre": "Candidato", "activo": True},
            ],
        )
        connection.execute(
            metadata.tables["tbl_producto_categoria"].insert(),
            [
                {"id": "bridge-conflict", "producto_id": "conflict", "categoria_id": "mouse"},
                {"id": "bridge-candidate", "producto_id": "candidate", "categoria_id": "mouse"},
            ],
        )
        connection.exec_driver_sql(
            "ALTER TABLE tbl_producto ADD COLUMN categoria_principal_id VARCHAR"
        )
        connection.exec_driver_sql(
            "UPDATE tbl_producto SET categoria_principal_id = 'teclado' WHERE id = 'conflict'"
        )
        before = snapshot(connection, metadata)
        report = audit_catalog(connection)

        assert report["fuente_categoria_principal"] == "tbl_producto.categoria_principal_id"
        assert report["candidatos_backfill_categoria"] == [
            {
                "producto_id": "candidate",
                "producto_nombre": "Candidato",
                "categoria_id": "mouse",
                "ruta": "Tecnologia > Mouse",
            }
        ]
        conflict = next(
            item for item in report["conflictos"] if item["code"] == "PRODUCT_PRIMARY_CATEGORY_CONFLICT"
        )
        assert conflict["ids"] == ["conflict"]
        assert conflict["categoria_principal_id"] == "teclado"
        assert conflict["categorias_bridge"] == [{"id": "mouse", "ruta": "Tecnologia > Mouse"}]
        assert snapshot(connection, metadata) == before


def test_preflight_lists_unambiguous_backfill_candidates_before_fk_exists():
    engine, metadata = catalog_engine()
    with engine.begin() as connection:
        connection.execute(
            metadata.tables["tbl_categoria"].insert(),
            [
                {"id": "root", "nombre": "Tecnologia", "parent_id": None, "activo": True, "es_padre": True, "is_default": False},
                {"id": "leaf", "nombre": "Mouse", "parent_id": "root", "activo": True, "es_padre": False, "is_default": False},
            ],
        )
        connection.execute(
            metadata.tables["tbl_producto"].insert().values(id="product", nombre="Mouse", activo=True)
        )
        connection.execute(
            metadata.tables["tbl_producto_categoria"].insert().values(
                id="classification", producto_id="product", categoria_id="leaf"
            )
        )

        report = audit_catalog(connection)

        assert report["fuente_categoria_principal"] == "tbl_producto_categoria_legacy"
        assert report["candidatos_backfill_categoria"] == [
            {
                "producto_id": "product",
                "producto_nombre": "Mouse",
                "categoria_id": "leaf",
                "ruta": "Tecnologia > Mouse",
            }
        ]


def test_preflight_lists_inactive_unambiguous_products_as_backfill_candidates():
    engine, metadata = catalog_engine()
    with engine.begin() as connection:
        connection.execute(
            metadata.tables["tbl_categoria"].insert().values(
                id="leaf",
                nombre="Mouse",
                parent_id=None,
                activo=True,
                es_padre=False,
                is_default=False,
            )
        )
        connection.execute(
            metadata.tables["tbl_producto"].insert().values(
                id="inactive", nombre="Legacy inactivo", activo=False
            )
        )
        connection.execute(
            metadata.tables["tbl_producto_categoria"].insert().values(
                id="classification", producto_id="inactive", categoria_id="leaf"
            )
        )

        report = audit_catalog(connection)

        assert report["apto_para_migrar"] is True
        assert report["candidatos_backfill_categoria"] == [
            {
                "producto_id": "inactive",
                "producto_nombre": "Legacy inactivo",
                "categoria_id": "leaf",
                "ruta": "Mouse",
            }
        ]


def test_preflight_reports_active_eav_values_that_are_duplicate_invalid_or_not_applicable():
    engine, metadata = catalog_engine()
    with engine.begin() as connection:
        connection.execute(
            metadata.tables["tbl_categoria"].insert(),
            [
                {"id": "root", "nombre": "Tecnologia", "parent_id": None, "activo": True, "es_padre": True, "is_default": False},
                {"id": "mouse", "nombre": "Mouse", "parent_id": "root", "activo": True, "es_padre": False, "is_default": False},
                {"id": "office", "nombre": "Oficina", "parent_id": None, "activo": True, "es_padre": False, "is_default": False},
            ],
        )
        connection.execute(
            metadata.tables["tbl_atributo"].insert(),
            [
                {"id": "dpi", "nombre": "DPI", "codigo": "dpi", "tipo_dato": "integer", "activo": True},
                {"id": "material", "nombre": "Material", "codigo": "material", "tipo_dato": "string", "activo": True},
            ],
        )
        connection.execute(
            metadata.tables["tbl_categoria_atributo"].insert(),
            [
                {"id": "dpi-mapping", "categoria_id": "mouse", "atributo_id": "dpi", "obligatorio": False, "activo": True},
                {"id": "material-mapping", "categoria_id": "office", "atributo_id": "material", "obligatorio": False, "activo": True},
            ],
        )
        connection.execute(
            metadata.tables["tbl_producto"].insert().values(id="product", nombre="Mouse", activo=True)
        )
        connection.execute(
            metadata.tables["tbl_producto_categoria"].insert().values(
                id="classification", producto_id="product", categoria_id="mouse"
            )
        )
        connection.execute(
            metadata.tables["tbl_producto_atributo_valor"].insert(),
            [
                {"id": "dpi-one", "producto_id": "product", "atributo_id": "dpi", "valor_string": "no-numero", "valor_integer": None, "activo": True},
                {"id": "dpi-two", "producto_id": "product", "atributo_id": "dpi", "valor_string": None, "valor_integer": 1600, "activo": True},
                {"id": "material-value", "producto_id": "product", "atributo_id": "material", "valor_string": "plastico", "valor_integer": None, "activo": True},
            ],
        )
        before = snapshot(connection, metadata)
        report = audit_catalog(connection, product_cutover=True)
        codes = {item["code"] for item in report["conflictos"]}

        assert {
            "PRODUCT_ATTRIBUTE_NOT_APPLICABLE",
            "PRODUCT_ATTRIBUTE_VALUE_DUPLICATE",
        } <= codes
        invalid = next(
            item for item in report["conflictos"] if item["code"] == "PRODUCT_ATTRIBUTE_VALUE_INVALID"
        )
        assert invalid["atributo_id"] == "dpi"
        assert invalid["valor_ids"] == ["dpi-one"]
        not_applicable = next(
            item for item in report["conflictos"] if item["code"] == "PRODUCT_ATTRIBUTE_NOT_APPLICABLE"
        )
        assert not_applicable["atributo_id"] == "material"
        assert snapshot(connection, metadata) == before


def test_optional_child_override_prevents_false_missing_required_report():
    engine, metadata = catalog_engine()
    with engine.begin() as connection:
        connection.execute(
            metadata.tables["tbl_categoria"].insert(),
            [
                {
                    "id": "root",
                    "nombre": "Tecnologia",
                    "parent_id": None,
                    "activo": True,
                    "es_padre": True,
                    "is_default": False,
                },
                {
                    "id": "leaf",
                    "nombre": "Mouse",
                    "parent_id": "root",
                    "activo": True,
                    "es_padre": False,
                    "is_default": False,
                },
            ],
        )
        connection.execute(
            metadata.tables["tbl_atributo"].insert(),
            [
                {
                    "id": "sku",
                    "nombre": "SKU",
                    "codigo": "sku",
                    "tipo_dato": "string",
                    "activo": True,
                },
            ],
        )
        connection.execute(
            metadata.tables["tbl_categoria_atributo"].insert(),
            [
                {
                    "id": "required",
                    "categoria_id": "root",
                    "atributo_id": "sku",
                    "obligatorio": True,
                    "valor_default": "N/A",
                    "activo": True,
                },
                {
                    "id": "optional",
                    "categoria_id": "leaf",
                    "atributo_id": "sku",
                    "obligatorio": False,
                    "valor_default": None,
                    "activo": True,
                },
            ],
        )
        connection.execute(
            metadata.tables["tbl_producto"]
            .insert()
            .values(id="product", nombre="Mouse", activo=True)
        )
        connection.execute(
            metadata.tables["tbl_producto_categoria"]
            .insert()
            .values(id="classification", producto_id="product", categoria_id="leaf")
        )
        report = audit_catalog(connection)
        assert report["apto_para_migrar"] is True
        assert (
            audit_catalog(connection, unit_candidates={"sku": "GIGABYTE"})["apto_para_migrar"]
            is False
        )


def test_preflight_never_executes_mutating_sql():
    engine, _metadata = catalog_engine()
    statements = []

    def reject_writes(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)
        assert statement.lstrip().split()[0].upper() not in {
            "INSERT",
            "UPDATE",
            "DELETE",
            "CREATE",
            "DROP",
            "ALTER",
            "REPLACE",
        }

    sa.event.listen(engine, "before_cursor_execute", reject_writes)
    try:
        with engine.connect() as connection:
            assert audit_catalog(connection)["apto_para_migrar"] is True
        assert statements
    finally:
        sa.event.remove(engine, "before_cursor_execute", reject_writes)


@pytest.mark.parametrize("has_conflict, expected_exit", [(False, 0), (True, 1)])
def test_cli_summary_and_exit_codes(monkeypatch, capsys, has_conflict, expected_exit):
    from osiris.core import db

    engine, metadata = catalog_engine()
    if has_conflict:
        with engine.begin() as connection:
            connection.execute(
                metadata.tables["tbl_producto"]
                .insert()
                .values(id="private-id", nombre="Private product", activo=True)
            )
    monkeypatch.setattr(db, "engine", engine)
    script_path = Path(__file__).parents[1] / "scripts/audit_catalog_integrity.py"
    spec = importlib.util.spec_from_file_location("catalog_preflight_cli", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(sys, "argv", [str(script_path), "--summary"])
    assert module.main() == expected_exit
    output = capsys.readouterr().out
    summary = json.loads(output)
    assert summary["apto_para_migrar"] is not has_conflict
    assert "private-id" not in output and "Private product" not in output
    assert "conflictos" not in summary


@pytest.mark.parametrize("value_active", [False, True])
def test_b3_bucket_is_structurally_allowed_but_inactive_value_does_not_satisfy_required(
    value_active,
):
    engine, metadata = catalog_engine()
    with engine.begin() as connection:
        connection.execute(
            metadata.tables["tbl_categoria"].insert(),
            [
                {
                    "id": "root",
                    "nombre": "Computadores",
                    "parent_id": None,
                    "activo": True,
                    "es_padre": True,
                    "is_default": False,
                },
                {
                    "id": "bucket",
                    "nombre": "Sin clasificar",
                    "parent_id": "root",
                    "activo": True,
                    "es_padre": False,
                    "is_default": True,
                },
            ],
        )
        connection.execute(
            metadata.tables["tbl_atributo"]
            .insert()
            .values(
                id="wireless",
                nombre="Inalambrico",
                codigo="wireless",
                tipo_dato="boolean",
                activo=True,
            )
        )
        connection.execute(
            metadata.tables["tbl_categoria_atributo"]
            .insert()
            .values(
                id="mapping",
                categoria_id="root",
                atributo_id="wireless",
                obligatorio=True,
                valor_default="true",
                activo=True,
            )
        )
        connection.execute(
            metadata.tables["tbl_producto"]
            .insert()
            .values(id="product", nombre="Mouse", activo=True)
        )
        connection.execute(
            metadata.tables["tbl_producto_categoria"]
            .insert()
            .values(id="classification", producto_id="product", categoria_id="bucket")
        )
        connection.execute(
            metadata.tables["tbl_producto_atributo_valor"]
            .insert()
            .values(
                id="value",
                producto_id="product",
                atributo_id="wireless",
                valor_boolean=False,
                activo=value_active,
            )
        )
        report = audit_catalog(connection)
        assert report["apto_para_migrar"] is value_active
        if not value_active:
            assert report["conflictos"][0]["code"] == "PRODUCT_REQUIRED_ATTRIBUTES_MISSING"
        if value_active:
            cutover_report = audit_catalog(connection, product_cutover=True)
            assert cutover_report["alcance"] == "producto_cutover"
            assert cutover_report["conflictos"][0]["code"] == "PRODUCT_CATEGORY_TEMPORARY"


def test_unit_candidate_counts_inactive_values_and_reverted_history_without_assigning_unit():
    engine, metadata = catalog_engine()
    history = sa.Table(
        "tbl_atributo_cambio",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("atributo_id", sa.String),
        sa.Column("revertido", sa.Boolean),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            metadata.tables["tbl_atributo"]
            .insert()
            .values(id="ram", nombre="RAM", codigo="ram", tipo_dato="integer", activo=True)
        )
        connection.execute(
            metadata.tables["tbl_producto"]
            .insert()
            .values(id="product", nombre="Laptop legacy", activo=False)
        )
        connection.execute(
            metadata.tables["tbl_producto_atributo_valor"]
            .insert()
            .values(
                id="historical-value",
                producto_id="product",
                atributo_id="ram",
                valor_integer=16,
                activo=False,
            )
        )
        connection.execute(
            history.insert().values(id="snapshot", atributo_id="ram", revertido=True)
        )
        before = snapshot(connection, metadata)
        report = audit_catalog(connection, unit_candidates={"ram": "GIGABYTE"})
        candidate = report["candidatos_anotacion_unidad"][0]
        assert candidate["valores_activos"] == 0
        assert candidate["valores_historicos"] == 1
        assert candidate["snapshots_historicos"] == 1
        assert candidate["requiere_confirmacion"] is True
        assert candidate["unidad_destino_validada"] is False
        assert snapshot(connection, metadata) == before

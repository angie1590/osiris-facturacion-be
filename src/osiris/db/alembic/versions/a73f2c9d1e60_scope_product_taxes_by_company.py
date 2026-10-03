"""Scope product tax assignments to the owning company.

Revision ID: a73f2c9d1e60
Revises: f61a8d3c2b90
"""

from __future__ import annotations

import json
from datetime import date
from uuid import UUID

import sqlalchemy as sa
from alembic import op


revision = "a73f2c9d1e60"
down_revision = "f61a8d3c2b90"
branch_labels = None
depends_on = None


def _company_tax_ids(value: object) -> set[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return set()
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {str(item) for item in value if item is not None}


def _canonical_iva_zero(bind) -> UUID:
    taxes = sa.table(
        "aux_impuesto_catalogo",
        sa.column("id", sa.Uuid()),
        sa.column("tipo_impuesto", sa.String()),
        sa.column("porcentaje_iva", sa.Numeric()),
        sa.column("clasificacion_iva", sa.String()),
        sa.column("aplica_a", sa.String()),
        sa.column("vigente_desde", sa.Date()),
        sa.column("vigente_hasta", sa.Date()),
        sa.column("activo", sa.Boolean()),
    )
    rows = bind.execute(
        sa.select(taxes.c.id).where(
            sa.cast(taxes.c.tipo_impuesto, sa.String()) == "IVA",
            taxes.c.porcentaje_iva == 0,
            taxes.c.clasificacion_iva.is_(None),
            sa.cast(taxes.c.aplica_a, sa.String()) == "AMBOS",
            taxes.c.activo.is_(True),
            taxes.c.vigente_desde <= date.today(),
            sa.or_(taxes.c.vigente_hasta.is_(None), taxes.c.vigente_hasta >= date.today()),
        )
    ).scalars().all()
    if len(rows) != 1:
        raise RuntimeError(
            "Cannot migrate product tax profiles: expected exactly one active, current canonical IVA 0% "
            "(IVA, 0%, no classification, applies to AMBOS); found "
            f"{len(rows)}. Correct aux_impuesto_catalogo and retry."
        )
    return rows[0]


def _preflight(bind) -> tuple[dict[UUID, UUID], UUID]:
    companies = sa.table(
        "tbl_empresa",
        sa.column("id", sa.Uuid()),
        sa.column("impuesto_catalogo_ids", sa.JSON()),
        sa.column("activo", sa.Boolean()),
    )
    products = sa.table(
        "tbl_producto",
        sa.column("id", sa.Uuid()),
        sa.column("tipo", sa.String()),
    )
    taxes = sa.table(
        "aux_impuesto_catalogo",
        sa.column("id", sa.Uuid()),
        sa.column("tipo_impuesto", sa.String()),
        sa.column("aplica_a", sa.String()),
        sa.column("vigente_desde", sa.Date()),
        sa.column("vigente_hasta", sa.Date()),
        sa.column("activo", sa.Boolean()),
    )
    assignments = sa.table(
        "tbl_producto_impuesto",
        sa.column("id", sa.Uuid()),
        sa.column("producto_id", sa.Uuid()),
        sa.column("impuesto_catalogo_id", sa.Uuid()),
        sa.column("activo", sa.Boolean()),
    )
    product_warehouses = sa.table(
        "tbl_producto_bodega",
        sa.column("producto_id", sa.Uuid()),
        sa.column("bodega_id", sa.Uuid()),
        sa.column("activo", sa.Boolean()),
    )
    warehouses = sa.table(
        "tbl_bodega",
        sa.column("id", sa.Uuid()),
        sa.column("empresa_id", sa.Uuid()),
        sa.column("activo", sa.Boolean()),
    )

    company_rows = bind.execute(sa.select(companies)).all()
    company_data = {
        row.id: (bool(row.activo), _company_tax_ids(row.impuesto_catalogo_ids))
        for row in company_rows
    }
    tax_data = {
        row.id: row
        for row in bind.execute(sa.select(taxes)).all()
    }
    product_data = {
        row.id: str(row.tipo)
        for row in bind.execute(sa.select(products.c.id, products.c.tipo)).all()
    }
    company_by_assignment: dict[UUID, UUID] = {}
    problems: list[str] = []
    per_type: set[tuple[UUID, UUID, str]] = set()

    active_assignments = bind.execute(
        sa.select(assignments).where(assignments.c.activo.is_(True))
    ).all()
    for assignment in active_assignments:
        scopes = bind.execute(
            sa.select(warehouses.c.empresa_id)
            .select_from(
                product_warehouses.join(
                    warehouses, product_warehouses.c.bodega_id == warehouses.c.id
                )
            )
            .where(
                product_warehouses.c.producto_id == assignment.producto_id,
                product_warehouses.c.activo.is_(True),
                warehouses.c.activo.is_(True),
            )
            .distinct()
        ).scalars().all()
        reasons: list[str] = []
        if len(scopes) != 1:
            reasons.append(f"active warehouse scope resolves to {len(scopes)} companies")
            company_id = None
        else:
            company_id = scopes[0]
            company_state = company_data.get(company_id)
            if company_state is None or not company_state[0]:
                reasons.append("inferred company is missing or inactive")
            elif str(assignment.impuesto_catalogo_id) not in company_state[1]:
                reasons.append("tax is not configured for the inferred company")

        tax = tax_data.get(assignment.impuesto_catalogo_id)
        if tax is None or not tax.activo:
            reasons.append("tax is missing or inactive")
        elif tax.tipo_impuesto not in {"IVA", "ICE"}:
            reasons.append(f"unsupported product tax type {tax.tipo_impuesto}")
        else:
            today = date.today()
            if tax.vigente_desde > today or (tax.vigente_hasta and tax.vigente_hasta < today):
                reasons.append("tax is outside its validity period")
            applies_to = str(tax.aplica_a)
            product_type = product_data.get(assignment.producto_id)
            if applies_to not in {"AMBOS", product_type}:
                reasons.append(f"tax applies to {applies_to}, product type is {product_type}")
            if company_id is not None and tax.tipo_impuesto in {"IVA", "ICE"}:
                type_key = (company_id, assignment.producto_id, str(tax.tipo_impuesto))
                if type_key in per_type:
                    reasons.append(f"multiple active {tax.tipo_impuesto} assignments")
                per_type.add(type_key)

        if company_id is not None:
            company_by_assignment[assignment.id] = company_id
        if reasons:
            problems.append(
                f"producto_impuesto={assignment.id} producto={assignment.producto_id} "
                f"impuesto={assignment.impuesto_catalogo_id} empresa={company_id or 'unresolved'}: "
                + "; ".join(reasons)
            )

    canonical_iva_zero_id = _canonical_iva_zero(bind)
    if problems:
        sample = "\n".join(f"- {problem}" for problem in problems[:100])
        if len(problems) > 100:
            sample += f"\n- ... and {len(problems) - 100} more rows"
        raise RuntimeError(
            "Cannot migrate product tax profiles until legacy assignments are reconciled. "
            f"{len(problems)} active row(s) need review:\n{sample}\n"
            "Reconcile each row's company and configured tax manually, then rerun Alembic. "
            "This migration does not change company tax whitelists or reassign taxes."
        )
    return company_by_assignment, canonical_iva_zero_id


def upgrade() -> None:
    bind = op.get_bind()
    company_by_assignment, iva_zero_id = _preflight(bind)

    companies = sa.table(
        "tbl_empresa",
        sa.column("id", sa.Uuid()),
        sa.column("impuesto_catalogo_ids", sa.JSON()),
        sa.column("activo", sa.Boolean()),
    )
    tax_catalog = sa.table(
        "aux_impuesto_catalogo",
        sa.column("id", sa.Uuid()),
        sa.column("tipo_impuesto", sa.String()),
        sa.column("vigente_desde", sa.Date()),
        sa.column("vigente_hasta", sa.Date()),
        sa.column("activo", sa.Boolean()),
    )
    today = date.today()
    iva_tax_ids = {
        str(tax_id)
        for tax_id, tax_type in bind.execute(
            sa.select(tax_catalog.c.id, tax_catalog.c.tipo_impuesto).where(
                tax_catalog.c.activo.is_(True),
                tax_catalog.c.vigente_desde <= today,
                sa.or_(tax_catalog.c.vigente_hasta.is_(None), tax_catalog.c.vigente_hasta >= today),
            )
        ).all()
        if tax_type == "IVA"
    }
    for company in bind.execute(sa.select(companies)).all():
        configured_ids = _company_tax_ids(company.impuesto_catalogo_ids)
        if not configured_ids.intersection(iva_tax_ids):
            configured_ids.add(str(iva_zero_id))
            bind.execute(
                sa.update(companies)
                .where(companies.c.id == company.id)
                .values(impuesto_catalogo_ids=sorted(configured_ids))
            )

    with op.batch_alter_table("tbl_producto_impuesto") as batch_op:
        batch_op.add_column(sa.Column("empresa_id", sa.Uuid(), nullable=True))
    assignments = sa.table(
        "tbl_producto_impuesto",
        sa.column("id", sa.Uuid()),
        sa.column("empresa_id", sa.Uuid()),
    )
    for assignment_id, company_id in company_by_assignment.items():
        bind.execute(
            sa.update(assignments)
            .where(assignments.c.id == assignment_id)
            .values(empresa_id=company_id)
        )

    with op.batch_alter_table("tbl_producto_impuesto") as batch_op:
        batch_op.create_foreign_key(
            "fk_tbl_producto_impuesto_empresa",
            "tbl_empresa",
            ["empresa_id"],
            ["id"],
        )
        batch_op.create_check_constraint(
            "ck_producto_impuesto_activo_empresa",
            "activo = false OR empresa_id IS NOT NULL",
        )

    op.create_index(
        "ix_tbl_producto_impuesto_empresa_id",
        "tbl_producto_impuesto",
        ["empresa_id"],
    )
    op.create_index(
        "uq_producto_impuesto_empresa_producto_impuesto_activo",
        "tbl_producto_impuesto",
        ["empresa_id", "producto_id", "impuesto_catalogo_id"],
        unique=True,
        postgresql_where=sa.text("activo = true"),
        sqlite_where=sa.text("activo = 1"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_producto_impuesto_empresa_producto_impuesto_activo",
        table_name="tbl_producto_impuesto",
    )
    op.drop_index("ix_tbl_producto_impuesto_empresa_id", table_name="tbl_producto_impuesto")
    with op.batch_alter_table("tbl_producto_impuesto") as batch_op:
        batch_op.drop_constraint("ck_producto_impuesto_activo_empresa", type_="check")
        batch_op.drop_constraint("fk_tbl_producto_impuesto_empresa", type_="foreignkey")
        batch_op.drop_column("empresa_id")
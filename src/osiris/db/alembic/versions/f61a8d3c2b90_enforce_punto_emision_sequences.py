"""enforce point modality and invoice sequence uniqueness

Revision ID: f61a8d3c2b90
Revises: e3b91a7d5c20
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op


revision = "f61a8d3c2b90"
down_revision = "e3b91a7d5c20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    point_columns = {column["name"] for column in inspector.get_columns("tbl_punto_emision")}
    if "modalidad_emision" not in point_columns:
        op.add_column(
            "tbl_punto_emision",
            sa.Column(
                "modalidad_emision",
                sa.String(length=12),
                nullable=False,
                server_default="ELECTRONICA",
            ),
        )

    points = sa.table(
        "tbl_punto_emision",
        sa.column("id", sa.Uuid()),
        sa.column("sucursal_id", sa.Uuid()),
        sa.column("modalidad_emision", sa.String(12)),
    )
    branches = sa.table(
        "tbl_sucursal", sa.column("id", sa.Uuid()), sa.column("empresa_id", sa.Uuid())
    )
    companies = sa.table(
        "tbl_empresa", sa.column("id", sa.Uuid()), sa.column("modo_emision", sa.String(40))
    )
    modality_rows = bind.execute(
        sa.select(points.c.id, companies.c.modo_emision)
        .select_from(points.join(branches, points.c.sucursal_id == branches.c.id)
                     .join(companies, branches.c.empresa_id == companies.c.id))
    ).all()
    for point_id, company_mode in modality_rows:
        modality = "FISICA" if company_mode == "NOTA_VENTA_FISICA" else "ELECTRONICA"
        bind.execute(
            sa.update(points).where(points.c.id == point_id).values(modalidad_emision=modality)
        )

    with op.batch_alter_table("tbl_punto_emision") as batch_op:
        batch_op.create_check_constraint(
            "ck_tbl_pe_secuencial_inicial",
            "secuencial_actual BETWEEN 1 AND 999999999",
        )
        batch_op.create_check_constraint(
            "ck_tbl_pe_modalidad",
            "modalidad_emision IN ('FISICA', 'ELECTRONICA')",
        )

    sales = sa.table(
        "tbl_venta",
        sa.column("id", sa.Uuid()),
        sa.column("empresa_id", sa.Uuid()),
        sa.column("punto_emision_id", sa.Uuid()),
        sa.column("secuencial_formateado", sa.String(20)),
    )
    maxima: dict[object, int] = {}
    for point_id, formatted in bind.execute(
        sa.select(sales.c.punto_emision_id, sales.c.secuencial_formateado).where(
            sales.c.punto_emision_id.is_not(None),
            sales.c.secuencial_formateado.is_not(None),
        )
    ):
        try:
            suffix = int(formatted.rsplit("-", 1)[1])
        except (AttributeError, IndexError, ValueError):
            continue
        if 1 <= suffix <= 999999999:
            maxima[point_id] = max(maxima.get(point_id, 0), suffix)

    counters = sa.table(
        "tbl_punto_emision_secuencial",
        sa.column("id", sa.Uuid()),
        sa.column("punto_emision_id", sa.Uuid()),
        sa.column("tipo_documento", sa.String(40)),
        sa.column("secuencial_actual", sa.Integer()),
        sa.column("creado_en", sa.DateTime()),
        sa.column("actualizado_en", sa.DateTime()),
        sa.column("usuario_auditoria", sa.String(255)),
        sa.column("activo", sa.Boolean()),
    )
    for point_id, last_issued in maxima.items():
        counter = bind.execute(
            sa.select(counters).where(
                counters.c.punto_emision_id == point_id,
                counters.c.tipo_documento == "FACTURA",
            )
        ).first()
        if counter:
            if counter.secuencial_actual < last_issued:
                bind.execute(
                    sa.update(counters)
                    .where(counters.c.id == counter.id)
                    .values(secuencial_actual=last_issued)
                )
        else:
            now = datetime.utcnow()
            bind.execute(
                sa.insert(counters).values(
                    id=uuid4(),
                    punto_emision_id=point_id,
                    tipo_documento="FACTURA",
                    secuencial_actual=last_issued,
                    creado_en=now,
                    actualizado_en=now,
                    usuario_auditoria="alembic_sequence_backfill",
                    activo=True,
                )
            )

    duplicates = bind.execute(
        sa.select(sales.c.empresa_id, sales.c.punto_emision_id, sales.c.secuencial_formateado)
        .where(
            sales.c.empresa_id.is_not(None),
            sales.c.punto_emision_id.is_not(None),
            sales.c.secuencial_formateado.is_not(None),
        )
        .group_by(sales.c.empresa_id, sales.c.punto_emision_id, sales.c.secuencial_formateado)
        .having(sa.func.count() > 1)
        .limit(1)
    ).first()
    if duplicates:
        raise RuntimeError(
            "Duplicate invoice numbers exist for one company and emission point; "
            "resolve them before applying f61a8d3c2b90."
        )

    indexes = {index["name"] for index in inspector.get_indexes("tbl_venta")}
    if "uq_venta_empresa_punto_secuencial" not in indexes:
        op.create_index(
            "uq_venta_empresa_punto_secuencial",
            "tbl_venta",
            ["empresa_id", "punto_emision_id", "secuencial_formateado"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    points = sa.table(
        "tbl_punto_emision",
        sa.column("id", sa.Uuid()),
        sa.column("sucursal_id", sa.Uuid()),
        sa.column("modalidad_emision", sa.String(12)),
    )
    branches = sa.table(
        "tbl_sucursal", sa.column("id", sa.Uuid()), sa.column("empresa_id", sa.Uuid())
    )
    companies = sa.table(
        "tbl_empresa", sa.column("id", sa.Uuid()), sa.column("modo_emision", sa.String(40))
    )
    incompatible = bind.execute(
        sa.select(points.c.id)
        .select_from(points.join(branches, points.c.sucursal_id == branches.c.id)
                     .join(companies, branches.c.empresa_id == companies.c.id))
        .where(
            sa.or_(
                sa.and_(points.c.modalidad_emision == "FISICA", companies.c.modo_emision != "NOTA_VENTA_FISICA"),
                sa.and_(points.c.modalidad_emision == "ELECTRONICA", companies.c.modo_emision != "ELECTRONICO"),
            )
        )
        .limit(1)
    ).first()
    if incompatible:
        raise RuntimeError(
            "Cannot downgrade while an emission point uses a modality not representable by the company legacy mode."
        )
    op.drop_index("uq_venta_empresa_punto_secuencial", table_name="tbl_venta")
    with op.batch_alter_table("tbl_punto_emision") as batch_op:
        batch_op.drop_constraint("ck_tbl_pe_modalidad", type_="check")
        batch_op.drop_constraint("ck_tbl_pe_secuencial_inicial", type_="check")
        batch_op.drop_column("modalidad_emision")

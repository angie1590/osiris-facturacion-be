from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date
from typing import Any

from sqlmodel import Session, select

from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION, engine
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.inventario.bodega.entity import Bodega
from osiris.modules.inventario.producto.entity import (
    Producto,
    ProductoBodega,
    ProductoImpuesto,
    TipoProducto,
)
from osiris.modules.sri.impuesto_catalogo.entity import AplicaA, ImpuestoCatalogo


def _is_tax_current(tax: ImpuestoCatalogo, today: date) -> bool:
    return bool(
        tax.activo
        and tax.vigente_desde <= today
        and (tax.vigente_hasta is None or tax.vigente_hasta >= today)
    )


def _is_compatible(product_type: TipoProducto, applies_to: AplicaA) -> bool:
    return applies_to == AplicaA.AMBOS or (
        product_type == TipoProducto.BIEN and applies_to == AplicaA.BIEN
    ) or (product_type == TipoProducto.SERVICIO and applies_to == AplicaA.SERVICIO)


def build_report(session: Session, *, today: date | None = None) -> dict[str, Any]:
    as_of = today or date.today()
    include_inactive = {SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True}

    assignment_rows = session.exec(
        select(ProductoImpuesto, Producto, ImpuestoCatalogo)
        .join(Producto, Producto.id == ProductoImpuesto.producto_id)
        .join(ImpuestoCatalogo, ImpuestoCatalogo.id == ProductoImpuesto.impuesto_catalogo_id)
        .execution_options(**include_inactive)
    ).all()
    warehouse_rows = session.exec(
        select(ProductoBodega.producto_id, Bodega.empresa_id)
        .join(Bodega, Bodega.id == ProductoBodega.bodega_id)
        .where(
            ProductoBodega.activo.is_(True),
            Bodega.activo.is_(True),
        )
        .execution_options(**include_inactive)
    ).all()
    company_rows = session.exec(
        select(Empresa).execution_options(**include_inactive)
    ).all()

    companies_by_product: dict[Any, set[Any]] = defaultdict(set)
    for product_id, company_id in warehouse_rows:
        companies_by_product[product_id].add(company_id)
    companies_by_id = {company.id: company for company in company_rows}

    records: list[dict[str, Any]] = []
    totals: Counter[str] = Counter()
    for assignment, product, tax in assignment_rows:
        company_ids = sorted(companies_by_product.get(product.id, set()), key=str)
        if not assignment.activo:
            status = "INACTIVE_ASSIGNMENT"
        elif not company_ids:
            status = "NO_ACTIVE_WAREHOUSE_SCOPE"
        elif len(company_ids) > 1:
            status = "MULTIPLE_COMPANY_SCOPE"
        else:
            company = companies_by_id.get(company_ids[0])
            configured_ids = {str(value) for value in (company.impuesto_catalogo_ids or [])} if company else set()
            if not company or not company.activo:
                status = "COMPANY_MISSING_OR_INACTIVE"
            elif not _is_tax_current(tax, as_of):
                status = "TAX_INACTIVE_OR_OUT_OF_DATE"
            elif str(tax.id) not in configured_ids:
                status = "TAX_NOT_CONFIGURED_FOR_COMPANY"
            elif not _is_compatible(product.tipo, tax.aplica_a):
                status = "TAX_PRODUCT_TYPE_MISMATCH"
            else:
                status = "SAFE_SINGLE_COMPANY"

        totals[status] += 1
        records.append(
            {
                "producto_impuesto_id": str(assignment.id),
                "producto_id": str(product.id),
                "producto_nombre": product.nombre,
                "producto_tipo": product.tipo.value,
                "impuesto_catalogo_id": str(tax.id),
                "impuesto_codigo_sri": tax.codigo_sri,
                "impuesto_descripcion": tax.descripcion,
                "empresa_ids_inferidas": [str(company_id) for company_id in company_ids],
                "assignment_active": assignment.activo,
                "status": status,
            }
        )

    return {
        "fecha_analisis": as_of.isoformat(),
        "total_relaciones": len(records),
        "resumen": dict(sorted(totals.items())),
        "requieren_revision": [
            record for record in records if record["status"] != "SAFE_SINGLE_COMPANY"
        ],
        "relaciones": records,
    }


def main() -> None:
    with Session(engine) as session:
        print(json.dumps(build_report(session), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

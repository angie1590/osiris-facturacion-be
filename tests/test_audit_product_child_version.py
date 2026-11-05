from __future__ import annotations

from uuid import uuid4

from sqlmodel import Session

from osiris.core.audit_context import reset_current_company_id, set_current_company_id
from osiris.modules.inventario.producto.models import ProductoIntegralUpdate
from osiris.modules.inventario.producto.service import ProductoService
from tests.test_producto_integral_service import _engine, _payload, _seed_catalog


def test_attribute_only_integral_update_bumps_product_version() -> None:
    engine = _engine()
    with Session(engine) as session:
        company_id, category_id, attribute_id, tax_id = _seed_catalog(
            session, default_value="1600"
        )

    company_token = set_current_company_id(str(company_id))
    try:
        with Session(engine) as session:
            product = ProductoService().create_integral(
                session,
                _payload(category_id, tax_id),
                actor_id=uuid4(),
            )
            product_id = product.id
            original_version = product.actualizado_en

        with Session(engine) as session:
            updated = ProductoService().update_integral(
                session,
                product_id,
                ProductoIntegralUpdate(
                    categoria_principal_id=category_id,
                    expected_updated_at=original_version,
                    atributos=[
                        {"atributo_id": str(attribute_id), "valor": 2400},
                    ],
                ),
                actor_id=uuid4(),
            )
            assert updated is not None
            assert updated.actualizado_en != original_version
    finally:
        reset_current_company_id(company_token)

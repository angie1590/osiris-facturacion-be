from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from osiris.modules.inventario.producto.entity import TipoProducto
from osiris.modules.inventario.producto.models import (
    ProductoIntegralCreate,
    ProductoIntegralUpdate,
)


def test_integral_create_accepts_primary_category_typed_attributes_and_tax_profile() -> None:
    category_id = uuid4()
    tax_id = uuid4()
    attribute_id = uuid4()

    payload = ProductoIntegralCreate.model_validate(
        {
            "nombre": "Mouse M720",
            "tipo": "BIEN",
            "pvp": "35.9",
            "categoria_principal_id": str(category_id),
            "impuesto_catalogo_ids": [str(tax_id)],
            "atributos": [
                {"atributo_id": str(attribute_id), "valor": 1000},
                {"atributo_id": str(uuid4()), "valor": False},
                {"atributo_id": str(uuid4()), "valor": Decimal("1.25")},
                {"atributo_id": str(uuid4()), "valor": date(2026, 10, 27)},
            ],
        }
    )

    assert payload.categoria_principal_id == category_id
    assert payload.tipo == TipoProducto.BIEN
    assert payload.pvp == Decimal("35.90")
    assert payload.atributos[0].valor == 1000
    assert isinstance(payload.atributos[0].valor, int)
    assert payload.atributos[1].valor is False
    assert isinstance(payload.atributos[1].valor, bool)
    assert payload.atributos[2].valor == Decimal("1.25")
    assert payload.atributos[3].valor == date(2026, 10, 27)


def test_integral_create_rejects_empty_tax_profile_and_duplicate_attributes() -> None:
    base = {
        "nombre": "Mouse M720",
        "pvp": 35.9,
        "categoria_principal_id": str(uuid4()),
        "impuesto_catalogo_ids": [],
    }
    with pytest.raises(ValidationError, match="al menos un impuesto"):
        ProductoIntegralCreate.model_validate(base)

    attribute_id = str(uuid4())
    with pytest.raises(ValidationError, match="repetir un atributo"):
        ProductoIntegralCreate.model_validate(
            {
                **base,
                "impuesto_catalogo_ids": [str(uuid4())],
                "atributos": [
                    {"atributo_id": attribute_id, "valor": "A"},
                    {"atributo_id": attribute_id, "valor": "B"},
                ],
            }
        )


def test_integral_dtos_reject_legacy_category_lists_and_client_audit_actor() -> None:
    with pytest.raises(ValidationError):
        ProductoIntegralCreate.model_validate(
            {
                "nombre": "Mouse M720",
                "pvp": 35.9,
                "categoria_principal_id": str(uuid4()),
                "impuesto_catalogo_ids": [str(uuid4())],
                "categoria_ids": [str(uuid4())],
                "usuario_auditoria": "cliente",
            }
        )

    with pytest.raises(ValidationError):
        ProductoIntegralUpdate.model_validate(
            {
                "categoria_principal_id": str(uuid4()),
                "usuario_auditoria": "cliente",
            }
        )


def test_integral_update_requires_category_and_preserves_omitted_attribute_collection() -> None:
    with pytest.raises(ValidationError):
        ProductoIntegralUpdate.model_validate({"nombre": "Mouse M720"})

    payload = ProductoIntegralUpdate.model_validate(
        {"categoria_principal_id": str(uuid4()), "nombre": "Mouse M720"}
    )
    assert payload.atributos is None
    assert payload.impuesto_catalogo_ids is None
    assert payload.precondicion_preview is None


def test_integral_update_accepts_explicit_preview_and_rejects_empty_tax_profile() -> None:
    with pytest.raises(ValidationError, match="no puede quedar vacío"):
        ProductoIntegralUpdate.model_validate(
            {"categoria_principal_id": str(uuid4()), "impuesto_catalogo_ids": []}
        )

    payload = ProductoIntegralUpdate.model_validate(
        {
            "categoria_principal_id": str(uuid4()),
            "impuesto_catalogo_ids": [str(uuid4())],
            "precondicion_preview": "opaque-preview-token",
        }
    )
    assert payload.precondicion_preview == "opaque-preview-token"

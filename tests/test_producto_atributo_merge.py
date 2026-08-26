from __future__ import annotations

from uuid import uuid4

from osiris.modules.inventario.producto.service import ProductoService


def test_merge_atributos_esqueleto_con_valores_rellena_valores_y_conserva_esqueleto():
    service = ProductoService()

    atributo_id_1 = uuid4()
    atributo_id_2 = uuid4()
    esqueleto = [
        {
            "atributo_id": atributo_id_1,
            "atributo_nombre": "Garantía",
            "tipo_dato": "string",
            "obligatorio": True,
            "orden": 1,
        },
        {
            "atributo_id": atributo_id_2,
            "atributo_nombre": "Peso",
            "tipo_dato": "decimal",
            "obligatorio": False,
            "orden": 2,
        },
    ]
    valores_por_atributo = {
        atributo_id_1: "24 meses",
    }

    merged = service._merge_atributos_esqueleto_con_valores(esqueleto, valores_por_atributo)

    assert len(merged) == 2
    assert merged[0]["atributo"]["id"] == atributo_id_1
    assert merged[0]["atributo"]["nombre"] == "Garantía"
    assert merged[0]["valor"] == "24 meses"
    assert merged[0]["obligatorio"] is True
    assert merged[0]["orden"] == 1

    assert merged[1]["atributo"]["id"] == atributo_id_2
    assert merged[1]["atributo"]["nombre"] == "Peso"
    assert merged[1]["valor"] is None
    assert merged[1]["obligatorio"] is False
    assert merged[1]["orden"] == 2

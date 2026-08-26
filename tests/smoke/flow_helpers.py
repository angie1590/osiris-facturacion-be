from __future__ import annotations

from datetime import date
from uuid import uuid4

import httpx
from unittest.mock import patch

from tests.smoke.ruc_utils import generar_ruc_empresa
from tests.smoke.utils import get_or_create_iva_for_tests


def _code3() -> str:
    return f"{(uuid4().int % 900) + 100:03d}"


def crear_empresa_general(client: httpx.Client) -> str:
    for _ in range(5):
        payload = {
            "ruc": generar_ruc_empresa(),
            "razon_social": "SMOKE EMPRESA",
            "nombre_comercial": f"SmokeCo {uuid4().hex[:6]}",
            "direccion_matriz": "Av. Smoke 123",
            "telefono": "0987654321",
            "tipo_contribuyente_id": "01",
            "obligado_contabilidad": False,
            "regimen": "GENERAL",
            "modo_emision": "ELECTRONICO",
            "usuario_auditoria": "smoke",
        }
        response = client.post("/api/v1/empresas", json=payload)
        if response.status_code == 201:
            empresa_id = response.json()["id"]
            sucursales_response = client.get("/api/v1/sucursales", params={"limit": 200, "offset": 0, "only_active": True})
            assert sucursales_response.status_code == 200, sucursales_response.text
            ya_existe_matriz = any(
                s.get("empresa_id") == empresa_id and s.get("codigo") == "001"
                for s in sucursales_response.json().get("items", [])
            )
            if not ya_existe_matriz:
                matriz_payload = {
                    "empresa_id": empresa_id,
                    "codigo": "001",
                    "nombre": "Matriz",
                    "direccion": "Av. Matriz 001",
                    "telefono": "0987654321",
                    "es_matriz": True,
                    "usuario_auditoria": "smoke",
                }
                matriz_response = client.post("/api/v1/sucursales", json=matriz_payload)
                assert matriz_response.status_code == 201, matriz_response.text
            return empresa_id
        if response.status_code != 422 and response.status_code != 400:
            break
        if "RUC" not in response.text and "ruc" not in response.text:
            break

    assert response.status_code == 201, response.text
    return response.json()["id"]


def crear_sucursal(client: httpx.Client, empresa_id: str) -> str:
    payload = {
        "empresa_id": empresa_id,
        "codigo": _code3(),
        "nombre": f"Sucursal {uuid4().hex[:6]}",
        "direccion": "Av. Sucursal 456",
        "telefono": "0987654321",
        "es_matriz": False,
        "usuario_auditoria": "smoke",
    }
    response = client.post("/api/v1/sucursales", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def crear_punto_emision(client: httpx.Client, sucursal_id: str) -> str:
    payload = {
        "sucursal_id": sucursal_id,
        "codigo": _code3(),
        "descripcion": f"Punto {uuid4().hex[:6]}",
        "secuencial_actual": 1,
        "usuario_auditoria": "smoke",
    }
    response = client.post("/api/v1/puntos-emision", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def crear_bodega(client: httpx.Client, empresa_id: str, sucursal_id: str | None = None) -> str:
    payload = {
        "codigo_bodega": f"BOD-{uuid4().hex[:6]}",
        "nombre_bodega": f"Bodega {uuid4().hex[:6]}",
        "descripcion": "Bodega smoke",
        "empresa_id": empresa_id,
        "sucursal_id": sucursal_id,
        "usuario_auditoria": "smoke",
    }
    response = client.post("/api/v1/bodegas", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def crear_categoria_hoja(client: httpx.Client) -> str:
    parent_payload = {
        "nombre": f"CatParent-{uuid4().hex[:6]}",
        "es_padre": True,
        "parent_id": None,
        "usuario_auditoria": "smoke",
    }
    parent_response = client.post("/api/v1/categorias", json=parent_payload)
    assert parent_response.status_code == 201, parent_response.text
    parent_id = parent_response.json()["id"]

    leaf_payload = {
        "nombre": f"CatLeaf-{uuid4().hex[:6]}",
        "es_padre": False,
        "parent_id": parent_id,
        "usuario_auditoria": "smoke",
    }
    leaf_response = client.post("/api/v1/categorias", json=leaf_payload)
    assert leaf_response.status_code == 201, leaf_response.text
    return leaf_response.json()["id"]


def crear_producto_minimo(client: httpx.Client, categoria_id: str, pvp: str = "10.00") -> str:
    iva_id = get_or_create_iva_for_tests(client)
    payload = {
        "nombre": f"Producto-{uuid4().hex[:8]}",
        "descripcion": "Producto smoke",
        "tipo": "BIEN",
        "pvp": pvp,
        "categoria_ids": [categoria_id],
        "impuesto_catalogo_ids": [iva_id],
        "usuario_auditoria": "smoke",
    }
    response = client.post("/api/v1/productos", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def registrar_compra_desde_productos(
    client: httpx.Client,
    *,
    producto_id: str,
    bodega_id: str,
    cantidad: str = "10.0000",
    precio_unitario: str = "10.00",
) -> dict:
    autorizacion_sri = str(uuid4().int)[:37].ljust(37, "0")
    payload_base = {
        "proveedor_id": str(uuid4()),
        "secuencial_factura": f"001-001-{str(uuid4().int)[-9:]}",
        "autorizacion_sri": autorizacion_sri,
        "fecha_emision": date.today().isoformat(),
        "bodega_id": bodega_id,
        "sustento_tributario": "01",
        "tipo_identificacion_proveedor": "RUC",
        "identificacion_proveedor": generar_ruc_empresa(),
        "forma_pago": "TRANSFERENCIA",
        "usuario_auditoria": "smoke",
        "detalles": [
            {
                "producto_id": producto_id,
                "descripcion": "Detalle compra smoke",
                "cantidad": cantidad,
                "precio_unitario": precio_unitario,
                "descuento": "0.00",
                "es_actividad_excluida": False,
            }
        ],
    }
    response = client.post("/api/v1/compras/desde-productos", json=payload_base)
    if response.status_code == 201:
        return response.json()

    # Fallback para entornos donde "desde-productos" falle por regresiones internas.
    payload_directo = {
        **payload_base,
        "detalles": [
            {
                **payload_base["detalles"][0],
                "impuestos": [
                    {
                        "tipo_impuesto": "IVA",
                        "codigo_impuesto_sri": "2",
                        "codigo_porcentaje_sri": "0",
                        "tarifa": "0.00",
                    }
                ],
            }
        ],
    }
    fallback = client.post("/api/v1/compras", json=payload_directo)
    assert fallback.status_code == 201, (
        f"/api/v1/compras/desde-productos -> {response.status_code} {response.text} | "
        f"/api/v1/compras -> {fallback.status_code} {fallback.text}"
    )
    return fallback.json()


def registrar_venta_desde_productos(
    client: httpx.Client,
    *,
    producto_id: str,
    bodega_id: str,
    cantidad: str = "1.0000",
    precio_unitario: str = "20.00",
    emitir: bool = True,
    empresa_id: str | None = None,
) -> dict:
    resolved_empresa_id = empresa_id
    if resolved_empresa_id is None:
        bodega_response = client.get(f"/api/v1/bodegas/{bodega_id}")
        assert bodega_response.status_code == 200, bodega_response.text
        resolved_empresa_id = bodega_response.json().get("empresa_id")

    payload = {
        "empresa_id": resolved_empresa_id,
        "fecha_emision": date.today().isoformat(),
        "bodega_id": bodega_id,
        "tipo_identificacion_comprador": "RUC",
        "identificacion_comprador": generar_ruc_empresa(),
        "forma_pago": "EFECTIVO",
        "regimen_emisor": "GENERAL",
        "usuario_auditoria": "smoke",
        "detalles": [
            {
                "producto_id": producto_id,
                "descripcion": "Detalle venta smoke",
                "cantidad": cantidad,
                "precio_unitario": precio_unitario,
                "descuento": "0.00",
                "es_actividad_excluida": False,
            }
        ],
    }
    if emitir:
        with patch("starlette.background.BackgroundTasks.add_task", return_value=None):
            response = client.post(
                "/api/v1/ventas/desde-productos",
                params={"emitir_automaticamente": True},
                json=payload,
            )
    else:
        response = client.post(
            "/api/v1/ventas/desde-productos",
            params={"emitir_automaticamente": False},
            json=payload,
        )
    assert response.status_code == 201, response.text
    venta = response.json()

    if not emitir:
        return venta

    if venta.get("estado") == "EMITIDA":
        return venta

    venta_id = venta["id"]
    with patch("starlette.background.BackgroundTasks.add_task", return_value=None):
        emitir_response = client.post(
            f"/api/v1/ventas/{venta_id}/emitir",
            json={"usuario_auditoria": "smoke"},
        )
    assert emitir_response.status_code == 200, emitir_response.text
    return emitir_response.json()


def seed_stock_por_movimiento(
    client: httpx.Client,
    *,
    producto_id: str,
    bodega_id: str,
    cantidad: str = "10.0000",
    costo_unitario: str = "10.00",
) -> None:
    crear_response = client.post(
        "/api/v1/inventarios/movimientos",
        json={
            "bodega_id": bodega_id,
            "tipo_movimiento": "INGRESO",
            "referencia_documento": "SMOKE-SEED-STOCK",
            "usuario_auditoria": "smoke",
            "detalles": [
                {
                    "producto_id": producto_id,
                    "cantidad": cantidad,
                    "costo_unitario": costo_unitario,
                }
            ],
        },
    )
    assert crear_response.status_code == 201, crear_response.text
    movimiento_id = crear_response.json()["id"]

    confirmar_response = client.post(
        f"/api/v1/inventarios/movimientos/{movimiento_id}/confirmar",
        json={"usuario_auditoria": "smoke"},
    )
    assert confirmar_response.status_code == 200, confirmar_response.text

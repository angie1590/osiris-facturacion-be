from __future__ import annotations

from fastapi.testclient import TestClient

from osiris.main import app


def test_facturacion_router_publica_endpoints_ventas():
    paths = {route.path for route in app.routes}

    assert "/api/v1/ventas" in paths
    assert "/api/v1/ventas/desde-productos" in paths
    assert "/api/v1/ventas/{venta_id}" in paths
    assert "/api/v1/ventas/{venta_id}/emitir" in paths
    assert "/api/v1/ventas/{venta_id}/anular" in paths
    assert "/api/v1/ventas/{venta_id}/fe-payload" in paths
    assert "/api/v1/compras/{compra_id}/sugerir-retencion" in paths
    assert "/api/v1/compras/{compra_id}/guardar-plantilla-retencion" in paths
    assert "/api/v1/compras/{compra_id}/retenciones" in paths
    assert "/api/v1/retenciones/{retencion_id}/emitir" in paths
    assert "/api/v1/retenciones/{retencion_id}/fe-payload" in paths
    assert "/api/v1/cxp" in paths
    assert "/api/v1/cxp/{compra_id}" in paths
    assert "/api/v1/cxp/{compra_id}/pagos" in paths
    assert "/api/v1/retenciones-recibidas" in paths
    assert "/api/v1/retenciones-recibidas/{retencion_id}" in paths
    assert "/api/v1/retenciones-recibidas/{retencion_id}/aplicar" in paths
    assert "/api/v1/cxc" in paths
    assert "/api/v1/cxc/{venta_id}" in paths
    assert "/api/v1/cxc/{venta_id}/pagos" in paths
    assert "/api/v1/fe/procesar-cola" in paths
    assert "/api/v1/fe/cola" in paths
    assert "/api/v1/fe/procesar/{documento_id}" in paths
    assert "/api/v1/fe/procesar-manual" in paths
    assert "/api/v1/documentos/{documento_id}/xml" in paths
    assert "/api/v1/documentos/{documento_id}/ride" in paths


def test_post_api_ventas_rechaza_iva_para_rimpe_negocio_popular():
    client = TestClient(app)
    payload = {
        "tipo_identificacion_comprador": "RUC",
        "identificacion_comprador": "1790012345001",
        "forma_pago": "EFECTIVO",
        "regimen_emisor": "RIMPE_NEGOCIO_POPULAR",
        "usuario_auditoria": "tester",
        "detalles": [
            {
                "producto_id": "11111111-1111-1111-1111-111111111111",
                "descripcion": "Servicio no excluido",
                "cantidad": "1",
                "precio_unitario": "10.00",
                "descuento": "0.00",
                "es_actividad_excluida": False,
                "impuestos": [
                    {
                        "tipo_impuesto": "IVA",
                        "codigo_impuesto_sri": "2",
                        "codigo_porcentaje_sri": "2",
                        "tarifa": "12",
                    }
                ],
            }
        ],
    }

    response = client.post("/api/v1/ventas", json=payload)

    assert response.status_code == 422
    body = response.json()
    errors = body.get("detail", [])
    assert any(
        "Los Negocios Populares solo pueden facturar con tarifa 0% de IVA para sus actividades incluyentes"
        in str(err.get("msg", ""))
        for err in errors
    )

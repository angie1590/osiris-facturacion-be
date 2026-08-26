"""
Smoke tests para asociación de atributos a productos (TipoProducto)
"""
import socket
import uuid
import pytest
import httpx

BASE = "http://localhost:8000/api/v1"
TIMEOUT = 10.0


def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@pytest.mark.skipif(
    not is_port_open("localhost", 8000),
    reason="Server not listening on localhost:8000"
)
def test_producto_con_atributos():
    """
    Escenario 4.1 y 4.2: Asociar y actualizar atributos en un producto
    - Crear atributos: color_principal (string), fecha_caducidad (date)
    - Crear categoría hoja "Lácteos"
    - Crear producto "Yogurt de Fresa"
    - Asociar atributos al producto con valores
    - Actualizar valor de un atributo
    - Verificar cambios con GET

    Nota: La tabla TipoProducto es una relación M:N entre Producto y Atributo
    que incluye campos adicionales como valor, orden, obligatorio.
    """
    with httpx.Client(timeout=TIMEOUT) as client:
        unique_suffix = uuid.uuid4().hex[:6]

        # 1. Crear atributos
        attr_color = {
            "nombre": f"color_principal_{unique_suffix}",
            "tipo_dato": "string",
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/atributos", json=attr_color)
        assert r.status_code == 201
        color_id = r.json()["id"]

        attr_fecha = {
            "nombre": f"fecha_caducidad_{unique_suffix}",
            "tipo_dato": "date",
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/atributos", json=attr_fecha)
        assert r.status_code == 201
        fecha_id = r.json()["id"]

        # 2. Crear categoría hoja "Lácteos"
        cat_alimentos = {
            "nombre": f"Alimentos_{unique_suffix}",
            "es_padre": True,
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/categorias", json=cat_alimentos)
        assert r.status_code == 201
        alimentos_id = r.json()["id"]

        cat_lacteos = {
            "nombre": f"Lacteos_{unique_suffix}",
            "es_padre": False,
            "parent_id": alimentos_id,
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/categorias", json=cat_lacteos)
        assert r.status_code == 201
        lacteos_id = r.json()["id"]

        # 3. Crear casa comercial
        casa_data = {
            "nombre": f"Casa_Lacteos_{unique_suffix}",
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/casas-comerciales", json=casa_data)
        assert r.status_code == 201
        casa_id = r.json()["id"]

        # Obtener IVA para productos (obligatorio)
        from tests.smoke.utils import get_or_create_iva_for_tests
        iva_id = get_or_create_iva_for_tests(client)

        # 4. Crear producto
        producto_data = {
            "nombre": f"Yogurt_Fresa_{unique_suffix}",
            "tipo": "BIEN",
            "pvp": 2.50,
            "casa_comercial_id": casa_id,
            "impuesto_catalogo_ids": [iva_id],  # Obligatorio
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/productos", json=producto_data)
        assert r.status_code == 201
        producto_id = r.json()["id"]

        # 5. Asociar atributos al producto
        # Nota: La tabla TipoProducto relaciona producto_id con atributo_id
        # y puede incluir campos como orden, obligatorio, valor (si es plantilla)
        #
        # Endpoints esperados (pueden no existir aún):
        # POST /productos/{producto_id}/atributos
        # PUT /productos/{producto_id}/atributos/{atributo_id}
        # GET /productos/{producto_id}/atributos

        # TODO: Implementar cuando existan los endpoints
        # Ejemplo de estructura esperada para asociación:
        # atributos_asociacion = {
        #     "atributos": [
        #         {
        #             "atributo_id": color_id,
        #             "orden": 1,
        #             "obligatorio": True
        #         },
        #         {
        #             "atributo_id": fecha_id,
        #             "orden": 2,
        #             "obligatorio": False
        #         }
        #     ]
        # }
        # r = client.post(
        #     f"{BASE}/productos/{producto_id}/atributos",
        #     json=atributos_asociacion
        # )
        # assert r.status_code == 201

        # Por ahora, verificamos que el producto existe
        r = client.get(f"{BASE}/productos/{producto_id}")
        assert r.status_code == 200
        assert r.json()["nombre"] == producto_data["nombre"]

        # Verificamos que los atributos existen
        r = client.get(f"{BASE}/atributos/{color_id}")
        assert r.status_code == 200
        assert r.json()["tipo_dato"] == "string"

        r = client.get(f"{BASE}/atributos/{fecha_id}")
        assert r.status_code == 200
        assert r.json()["tipo_dato"] == "date"

        # Cleanup: eliminar producto, casa y categorías creadas
        r = client.delete(f"{BASE}/productos/{producto_id}")
        assert r.status_code in (204, 404)
        r = client.delete(f"{BASE}/casas-comerciales/{casa_id}")
        assert r.status_code in (204, 404)
        # eliminar hoja y luego padre
        r = client.delete(f"{BASE}/categorias/{lacteos_id}")
        assert r.status_code in (204, 404)
        r = client.delete(f"{BASE}/categorias/{alimentos_id}")
        assert r.status_code in (204, 404)
        # eliminar atributos
        r = client.delete(f"{BASE}/atributos/{color_id}")
        assert r.status_code in (204, 404)
        r = client.delete(f"{BASE}/atributos/{fecha_id}")
        assert r.status_code in (204, 404)


@pytest.mark.skipif(
    not is_port_open("localhost", 8000),
    reason="Server not listening on localhost:8000"
)
def test_asociar_atributo_inexistente():
    """
    Escenario 6.2: Asociar atributo inexistente debe fallar
    - Crear un producto
    - Intentar asociar atributo con ID inexistente
    - Verificar que devuelve error 400/404

    Nota: Test pendiente de implementación de endpoints de asociación
    """
    with httpx.Client(timeout=TIMEOUT) as client:
        unique_suffix = uuid.uuid4().hex[:6]

        # Crear casa comercial
        casa_data = {
            "nombre": f"Casa_Atributo_Test_{unique_suffix}",
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/casas-comerciales", json=casa_data)
        assert r.status_code == 201
        casa_id = r.json()["id"]

        # Obtener IVA para productos (obligatorio)
        from tests.smoke.utils import get_or_create_iva_for_tests
        iva_id = get_or_create_iva_for_tests(client)

        # Crear producto
        producto_data = {
            "nombre": f"Producto_Test_Atributo_{unique_suffix}",
            "tipo": "BIEN",
            "pvp": 100.00,
            "casa_comercial_id": casa_id,
            "impuesto_catalogo_ids": [iva_id],  # Obligatorio
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/productos", json=producto_data)
        assert r.status_code == 201
        producto_id = r.json()["id"]

        # TODO: Cuando existan los endpoints de asociación, probar con ID inexistente
        # Ejemplo esperado:
        # r = client.post(
        #     f"{BASE}/productos/{producto_id}/atributos",
        #     json={
        #         "atributos": [{
        #             "atributo_id": "99999999-9999-9999-9999-999999999999",
        #             "orden": 1
        #         }]
        #     }
        # )
        # assert r.status_code in (400, 404)

        # Por ahora, solo verificamos que el producto existe
        r = client.get(f"{BASE}/productos/{producto_id}")
        assert r.status_code == 200

        # Cleanup
        r = client.delete(f"{BASE}/productos/{producto_id}")
        assert r.status_code in (204, 404)
        r = client.delete(f"{BASE}/casas-comerciales/{casa_id}")
        assert r.status_code in (204, 404)

"""
Smoke tests para operaciones CRUD generales de Producto
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
def test_producto_crud_completo():
    """
    Escenario 5: CRUD general de Producto
    - Crear múltiples productos
    - Listar y verificar que aparecen
    - Actualizar un producto
    - Eliminar un producto
    - Verificar eliminación
    """
    with httpx.Client(timeout=TIMEOUT) as client:
        unique_suffix = uuid.uuid4().hex[:6]

        # 1. Crear casa comercial
        casa_data = {
            "nombre": f"Casa_CRUD_{unique_suffix}",
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/casas-comerciales", json=casa_data)
        assert r.status_code == 201
        casa_id = r.json()["id"]

        # Obtener IVA para productos (obligatorio)
        from tests.smoke.utils import get_or_create_iva_for_tests
        iva_id = get_or_create_iva_for_tests(client)

        # 2. Crear múltiples productos
        productos_nombres = [
            f"Laptop_Gamer_X_{unique_suffix}",
            f"Mouse_Inalambrico_{unique_suffix}",
            f"Yogurt_Fresa_{unique_suffix}"
        ]

        productos_ids = []
        for nombre in productos_nombres:
            producto_data = {
                "nombre": nombre,
                "tipo": "BIEN",
                "pvp": 100.00,
                "casa_comercial_id": casa_id,
                "impuesto_catalogo_ids": [iva_id],  # Obligatorio
                "usuario_auditoria": "smoke_test"
            }
            r = client.post(f"{BASE}/productos", json=producto_data)
            assert r.status_code == 201, f"Failed to create producto {nombre}: {r.text}"
            productos_ids.append(r.json()["id"])

        # 3. Listar productos con límite alto para asegurar que aparezcan
        r = client.get(f"{BASE}/productos?limit=500&only_active=true")
        assert r.status_code == 200
        items = r.json().get("items", [])
        nombres_en_lista = [item["nombre"] for item in items]

        for nombre in productos_nombres:
            assert nombre in nombres_en_lista, f"Producto {nombre} not found in list"

        # Verificar metadatos de paginación (dentro de meta)
        meta = r.json().get("meta", {})
        assert "total" in meta, "Missing pagination metadata"
        assert meta["total"] >= len(productos_nombres)

        # 4. Actualización - Tomar "Laptop Gamer X"
        laptop_id = productos_ids[0]
        nuevo_nombre = f"Laptop_Gamer_X_Pro_{unique_suffix}"

        update_data = {
            "nombre": nuevo_nombre,
            "usuario_auditoria": "smoke_test"
        }
        r = client.put(f"{BASE}/productos/{laptop_id}", json=update_data)
        assert r.status_code == 200
        assert r.json()["nombre"] == nuevo_nombre

        # Verificar con GET
        r = client.get(f"{BASE}/productos/{laptop_id}")
        assert r.status_code == 200
        assert r.json()["nombre"] == nuevo_nombre

        # 5. Eliminación - Eliminar "Mouse Inalámbrico"
        mouse_id = productos_ids[1]
        mouse_nombre = productos_nombres[1]

        r = client.delete(f"{BASE}/productos/{mouse_id}")
        assert r.status_code == 204

        # Verificar soft delete: GET devuelve 404 o 200 con activo=False
        r = client.get(f"{BASE}/productos/{mouse_id}")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert r.json().get("activo") is False

        # Verificar que no aparece en la lista
        r = client.get(f"{BASE}/productos")
        assert r.status_code == 200
        items = r.json().get("items", [])
        nombres_en_lista = [item["nombre"] for item in items]
        assert mouse_nombre not in nombres_en_lista, "Deleted product still appears in list"

        # Cleanup adicional utilizando utilidad común
        from tests.smoke.utils import cleanup_product_scenario
        cleanup_product_scenario(
            client,
            producto_id=laptop_id,
            casa_id=casa_id,
        )
        # Cleanup del mouse (soft deleted en línea 107)
        cleanup_product_scenario(client, producto_id=mouse_id)
        # Cleanup del yogurt
        yogurt_id = productos_ids[2]
        cleanup_product_scenario(client, producto_id=yogurt_id)


@pytest.mark.skipif(
    not is_port_open("localhost", 8000),
    reason="Server not listening on localhost:8000"
)
def test_producto_get_completo_con_impuestos():
    """
    Test: Verificar que el endpoint GET /productos/{id} devuelve el producto completo
    y que existe el endpoint separado /productos/{id}/impuestos para obtener impuestos
    """
    with httpx.Client(timeout=TIMEOUT) as client:
        unique_suffix = uuid.uuid4().hex[:6]

        # Crear casa comercial
        casa_data = {
            "nombre": f"Casa_Impuestos_{unique_suffix}",
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
            "nombre": f"Producto_Completo_{unique_suffix}",
            "tipo": "BIEN",
            "pvp": 200.00,
            "casa_comercial_id": casa_id,
            "impuesto_catalogo_ids": [iva_id],  # Obligatorio
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/productos", json=producto_data)
        assert r.status_code == 201
        producto_id = r.json()["id"]

        # Obtener el producto completo (con casa_comercial, categorias, etc)
        r = client.get(f"{BASE}/productos/{producto_id}")
        assert r.status_code == 200
        data = r.json()

        # Verificar estructura del producto completo
        assert "id" in data
        assert "nombre" in data
        assert "tipo" in data
        assert data["tipo"] == producto_data["tipo"]
        assert "pvp" in data
        # Comparar como Decimal con 2 decimales para evitar diferencias de representación
        from decimal import Decimal
        pvp_resp = Decimal(str(data["pvp"]))
        pvp_req = Decimal(str(producto_data["pvp"]))
        assert pvp_resp.quantize(Decimal("0.01")) == pvp_req.quantize(Decimal("0.01"))
        assert "casa_comercial" in data, "Debe tener objeto casa_comercial anidado"
        assert "categorias" in data, "Debe tener array categorias"
        assert "proveedores_persona" in data
        assert "proveedores_sociedad" in data
        assert "atributos" in data
        assert data["nombre"] == producto_data["nombre"]
        # Verificar campo cantidad (debe existir y ser 0 por defecto)
        assert "cantidad" in data, "Debe tener campo cantidad"
        assert data["cantidad"] == 0, "Cantidad debe inicializarse en 0"

        # Cleanup común
        from tests.smoke.utils import cleanup_product_scenario
        cleanup_product_scenario(client, producto_id=producto_id, casa_id=casa_id)

        # Obtener impuestos del producto (endpoint separado)
        r = client.get(f"{BASE}/productos/{producto_id}/impuestos")
        assert r.status_code == 200
        impuestos = r.json()
        assert isinstance(impuestos, list), "impuestos debe ser una lista"
        # Por ahora, el producto no tiene impuestos asignados (lista vacía)


@pytest.mark.skipif(
    not is_port_open("localhost", 8000),
    reason="Server not listening on localhost:8000"
)
def test_producto_tipos_bien_y_servicio():
    """
    Test adicional: Verificar tipos de producto BIEN y SERVICIO
    - Crear producto tipo BIEN
    - Crear producto tipo SERVICIO
    - Verificar que ambos se crean correctamente
    """
    with httpx.Client(timeout=TIMEOUT) as client:
        unique_suffix = uuid.uuid4().hex[:6]

        # Crear casa comercial
        casa_data = {
            "nombre": f"Casa_Tipos_{unique_suffix}",
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/casas-comerciales", json=casa_data)
        assert r.status_code == 201
        casa_id = r.json()["id"]

        # Obtener IVA para productos (obligatorio)
        from tests.smoke.utils import get_or_create_iva_for_tests
        iva_id = get_or_create_iva_for_tests(client)

        # Producto tipo BIEN
        bien_data = {
            "nombre": f"Laptop_BIEN_{unique_suffix}",
            "tipo": "BIEN",
            "pvp": 1000.00,
            "casa_comercial_id": casa_id,
            "impuesto_catalogo_ids": [iva_id],  # Obligatorio
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/productos", json=bien_data)
        assert r.status_code == 201
        bien_id = r.json()["id"]

        # Producto tipo SERVICIO
        servicio_data = {
            "nombre": f"Consultoria_SERVICIO_{unique_suffix}",
            "tipo": "SERVICIO",
            "pvp": 500.00,
            "casa_comercial_id": casa_id,
            "impuesto_catalogo_ids": [iva_id],  # Obligatorio
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/productos", json=servicio_data)
        assert r.status_code == 201
        servicio_id = r.json()["id"]

        # Verificar con GET
        r = client.get(f"{BASE}/productos/{bien_id}")
        assert r.status_code == 200
        assert r.json()["tipo"] == "BIEN"
        assert r.json()["cantidad"] == 0

        r = client.get(f"{BASE}/productos/{servicio_id}")
        assert r.status_code == 200
        assert r.json()["tipo"] == "SERVICIO"
        assert r.json()["cantidad"] == 0

        # Cleanup
        from tests.smoke.utils import cleanup_product_scenario
        cleanup_product_scenario(client, producto_id=bien_id)
        cleanup_product_scenario(client, producto_id=servicio_id, casa_id=casa_id)

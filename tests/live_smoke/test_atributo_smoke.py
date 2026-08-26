"""
Smoke tests para Atributo - Escenarios básicos de CRUD
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
def test_atributo_crear_y_listar():
    """
    Escenario 1.1: Crear y listar atributos
    - Crear atributo "color" con tipo_dato "string"
    - Crear atributo "peso" con tipo_dato "decimal"
    - Crear atributo "fecha_caducidad" con tipo_dato "date"
    - Verificar que GET /inventario/atributos incluye esos atributos
    """
    with httpx.Client(timeout=TIMEOUT) as client:
        # Crear atributos con nombres únicos
        unique_suffix = uuid.uuid4().hex[:6]
        atributos_data = [
            {
                "nombre": f"color_{unique_suffix}",
                "tipo_dato": "string",
                "usuario_auditoria": "smoke_test"
            },
            {
                "nombre": f"peso_{unique_suffix}",
                "tipo_dato": "decimal",
                "usuario_auditoria": "smoke_test"
            },
            {
                "nombre": f"fecha_caducidad_{unique_suffix}",
                "tipo_dato": "date",
                "usuario_auditoria": "smoke_test"
            }
        ]

        created_ids = []
        for attr_data in atributos_data:
            r = client.post(f"{BASE}/atributos", json=attr_data)
            assert r.status_code == 201, f"Failed to create atributo: {r.text}"
            data = r.json()
            assert data.get("id") is not None
            assert data.get("nombre") == attr_data["nombre"]
            assert data.get("tipo_dato") == attr_data["tipo_dato"]
            created_ids.append(data["id"])

        # Listar atributos con límite alto para asegurar aparición
        r = client.get(f"{BASE}/atributos?limit=500&only_active=true")
        assert r.status_code == 200
        items = r.json().get("items", [])

        # Verificar que los atributos creados están en la lista
        nombres_en_lista = [item["nombre"] for item in items]
        for attr_data in atributos_data:
            assert attr_data["nombre"] in nombres_en_lista, \
                f"Atributo {attr_data['nombre']} no encontrado. Total items: {len(items)}"


@pytest.mark.skipif(
    not is_port_open("localhost", 8000),
    reason="Server not listening on localhost:8000"
)
def test_atributo_actualizar_y_eliminar():
    """
    Escenario 1.2: Actualizar y eliminar atributo
    - Crear atributo "color"
    - Actualizarlo a "color_principal"
    - Verificar el cambio con GET
    - Eliminar atributo "peso"
    - Verificar que devuelve 404
    """
    with httpx.Client(timeout=TIMEOUT) as client:
        unique_suffix = uuid.uuid4().hex[:6]

        # Crear atributo "color"
        color_data = {
            "nombre": f"color_{unique_suffix}",
            "tipo_dato": "string",
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/atributos", json=color_data)
        assert r.status_code == 201
        color_id = r.json()["id"]

        # Actualizar a "color_principal"
        update_data = {
            "nombre": f"color_principal_{unique_suffix}",
            "usuario_auditoria": "smoke_test"
        }
        r = client.put(f"{BASE}/atributos/{color_id}", json=update_data)
        assert r.status_code == 200
        assert r.json()["nombre"] == update_data["nombre"]

        # Verificar con GET
        r = client.get(f"{BASE}/atributos/{color_id}")
        assert r.status_code == 200
        assert r.json()["nombre"] == update_data["nombre"]

        # Crear atributo "peso" para eliminar
        peso_data = {
            "nombre": f"peso_{unique_suffix}",
            "tipo_dato": "decimal",
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/atributos", json=peso_data)
        assert r.status_code == 201
        peso_id = r.json()["id"]

        # Eliminar el atributo (soft delete)
        r = client.delete(f"{BASE}/atributos/{peso_id}")
        assert r.status_code == 204

        # Verificar soft delete: GET devuelve 404 o 200 con activo=False
        r = client.get(f"{BASE}/atributos/{peso_id}")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert r.json()["activo"] is False

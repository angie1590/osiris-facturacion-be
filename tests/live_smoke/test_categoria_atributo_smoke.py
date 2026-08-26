"""
Smoke test para endpoints de CategoriaAtributo
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
def test_categoria_atributo_crud_completo():
    """
    Verificar CRUD de categoria_atributo:
    - Crear una categoría
    - Crear un atributo
    - Asociar atributo a categoría con orden y obligatorio
    - Listar asociaciones por categoria_id
    - Actualizar orden y obligatorio
    - Eliminar (soft delete)
    """
    with httpx.Client(timeout=TIMEOUT) as client:
        unique_suffix = uuid.uuid4().hex[:6]

        # 1. Crear categoría hoja
        categoria_data = {
            "nombre": f"Cat_AtribTest_{unique_suffix}",
            "es_padre": False,
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/categorias", json=categoria_data)
        assert r.status_code == 201, f"Failed to create categoria: {r.text}"
        categoria_id = r.json()["id"]

        # 2. Crear atributo
        atributo_data = {
            "nombre": f"atrib_test_{unique_suffix}",
            "tipo_dato": "string",
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/atributos", json=atributo_data)
        assert r.status_code == 201, f"Failed to create atributo: {r.text}"
        atributo_id = r.json()["id"]

        # 3. Asociar atributo a categoría
        asociacion_data = {
            "categoria_id": categoria_id,
            "atributo_id": atributo_id,
            "orden": 1,
            "obligatorio": True,
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/categorias-atributos", json=asociacion_data)
        assert r.status_code == 201, f"Failed to create categoria_atributo: {r.text}"
        asociacion_id = r.json()["id"]

        # 4. Verificar con GET individual
        r = client.get(f"{BASE}/categorias-atributos/{asociacion_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["categoria_id"] == categoria_id
        assert data["atributo_id"] == atributo_id
        assert data["orden"] == 1
        assert data["obligatorio"] is True

        # 5. Listar asociaciones de esta categoría
        r = client.get(f"{BASE}/categorias-atributos?categoria_id={categoria_id}")
        assert r.status_code == 200
        items = r.json()  # El servicio devuelve lista directa
        assert len(items) >= 1
        found = any(item["id"] == asociacion_id for item in items)
        assert found, "Asociación no encontrada en listado por categoria_id"

        # 6. Actualizar orden y obligatorio
        update_data = {
            "orden": 10,
            "obligatorio": False,
            "usuario_auditoria": "smoke_test"
        }
        r = client.put(f"{BASE}/categorias-atributos/{asociacion_id}", json=update_data)
        assert r.status_code == 200
        updated = r.json()
        assert updated["orden"] == 10
        assert updated["obligatorio"] is False

        # 7. Eliminar (soft delete)
        r = client.delete(f"{BASE}/categorias-atributos/{asociacion_id}")
        assert r.status_code == 204

        # 8. Verificar que ya no aparece en lista activa
        r = client.get(f"{BASE}/categorias-atributos?categoria_id={categoria_id}")
        assert r.status_code == 200
        items = r.json()  # El servicio devuelve lista directa
        found = any(item["id"] == asociacion_id for item in items)
        assert not found, "Asociación eliminada aún aparece en lista activa"


@pytest.mark.skipif(
    not is_port_open("localhost", 8000),
    reason="Server not listening on localhost:8000"
)
def test_categoria_atributo_herencia_de_atributos():
    """
    Verificar que un producto asociado a una categoría hoja
    hereda los atributos de toda la cadena de categorías.

    Estructura:
      Raíz -> Padre -> Hoja

    Se asignan atributos a cada nivel y se verifica que
    el producto obtenga la unión de atributos.
    """
    with httpx.Client(timeout=TIMEOUT) as client:
        unique_suffix = uuid.uuid4().hex[:6]

        # Crear categoría raíz
        raiz_data = {
            "nombre": f"Raiz_{unique_suffix}",
            "es_padre": True,
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/categorias", json=raiz_data)
        assert r.status_code == 201
        raiz_id = r.json()["id"]

        # Crear categoría padre intermedia
        padre_data = {
            "nombre": f"Padre_{unique_suffix}",
            "es_padre": True,
            "parent_id": raiz_id,
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/categorias", json=padre_data)
        assert r.status_code == 201
        padre_id = r.json()["id"]

        # Crear categoría hoja
        hoja_data = {
            "nombre": f"Hoja_{unique_suffix}",
            "es_padre": False,
            "parent_id": padre_id,
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/categorias", json=hoja_data)
        assert r.status_code == 201
        hoja_id = r.json()["id"]

        # Crear 3 atributos
        atributos = []
        for i, nivel in enumerate(["raiz", "padre", "hoja"]):
            atributo_data = {
                "nombre": f"atrib_{nivel}_{unique_suffix}",
                "tipo_dato": "string",
                "usuario_auditoria": "smoke_test"
            }
            r = client.post(f"{BASE}/atributos", json=atributo_data)
            assert r.status_code == 201
            atributos.append(r.json()["id"])

        # Asociar atributo a raíz
        r = client.post(f"{BASE}/categorias-atributos", json={
            "categoria_id": raiz_id,
            "atributo_id": atributos[0],
            "orden": 1,
            "obligatorio": False,
            "usuario_auditoria": "smoke_test"
        })
        assert r.status_code == 201

        # Asociar atributo a padre
        r = client.post(f"{BASE}/categorias-atributos", json={
            "categoria_id": padre_id,
            "atributo_id": atributos[1],
            "orden": 2,
            "obligatorio": False,
            "usuario_auditoria": "smoke_test"
        })
        assert r.status_code == 201

        # Asociar atributo a hoja
        r = client.post(f"{BASE}/categorias-atributos", json={
            "categoria_id": hoja_id,
            "atributo_id": atributos[2],
            "orden": 3,
            "obligatorio": True,
            "usuario_auditoria": "smoke_test"
        })
        assert r.status_code == 201

        # Crear casa comercial
        casa_data = {
            "nombre": f"Casa_Herencia_{unique_suffix}",
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/casas-comerciales", json=casa_data)
        assert r.status_code == 201
        casa_id = r.json()["id"]

        # Obtener IVA obligatorio
        from tests.smoke.utils import get_or_create_iva_for_tests
        iva_id = get_or_create_iva_for_tests(client)

        # Crear producto asociado a la categoría hoja
        producto_data = {
            "nombre": f"Producto_Herencia_{unique_suffix}",
            "tipo": "BIEN",
            "pvp": 99.99,
            "casa_comercial_id": casa_id,
            "categoria_ids": [hoja_id],
            "impuesto_catalogo_ids": [iva_id],
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/productos", json=producto_data)
        assert r.status_code == 201
        producto_id = r.json()["id"]

        # Obtener producto completo y verificar que tiene los 3 atributos heredados
        r = client.get(f"{BASE}/productos/{producto_id}")
        assert r.status_code == 200
        producto = r.json()

        atributos_producto = producto.get("atributos", [])
        atributos_nombres = [a["atributo"]["nombre"] for a in atributos_producto]

        assert f"atrib_raiz_{unique_suffix}" in atributos_nombres, "Atributo de raíz no heredado"
        assert f"atrib_padre_{unique_suffix}" in atributos_nombres, "Atributo de padre no heredado"
        assert f"atrib_hoja_{unique_suffix}" in atributos_nombres, "Atributo de hoja no heredado"

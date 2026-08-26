# tests/smoke/test_modulo_smoke.py
import pytest
import uuid
import httpx

from tests.smoke.utils import is_port_open


client = httpx.Client(base_url="http://localhost:8000", timeout=10.0)


@pytest.mark.skipif(not is_port_open("localhost", 8000), reason="Server not listening on localhost:8000")
def test_modulo_crud_completo():
    """Test smoke del flujo CRUD completo de módulos."""

    # 1. Crear módulo
    suf = uuid.uuid4().hex[:6]
    create_data = {
        "codigo": f"SMOKE_TEST_MOD_{suf}",
        "nombre": "Módulo Smoke Test",
        "descripcion": "Módulo para pruebas smoke",
        "orden": 99,
        "icono": "smoke-icon",
        "usuario_auditoria": "smoke_test"
    }

    response = client.post("/api/v1/modulos", json=create_data)
    assert response.status_code == 201, f"Error creando módulo: {response.text}"
    modulo_creado = response.json()
    modulo_id = modulo_creado["id"]

    assert modulo_creado["codigo"] == f"SMOKE_TEST_MOD_{suf}"
    assert modulo_creado["nombre"] == "Módulo Smoke Test"
    assert modulo_creado["activo"] is True

    # 2. Listar módulos
    response = client.get("/api/v1/modulos")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict) and "meta" in data and "items" in data
    assert data["meta"]["total"] >= 1

    # Verificar que el módulo creado está en la lista
    modulos = data["items"]
    modulo_encontrado = any(m["id"] == modulo_id for m in modulos)
    assert modulo_encontrado, "El módulo creado no aparece en el listado"

    # 3. Obtener módulo por ID
    response = client.get(f"/api/v1/modulos/{modulo_id}")
    assert response.status_code == 200
    modulo = response.json()
    assert modulo["codigo"] == f"SMOKE_TEST_MOD_{suf}"

    # 4. Actualizar módulo
    update_data = {
        "nombre": "Módulo Smoke Actualizado",
        "descripcion": "Descripción actualizada",
        "orden": 100,
        "usuario_auditoria": "smoke_test"
    }

    response = client.put(f"/api/v1/modulos/{modulo_id}", json=update_data)
    assert response.status_code == 200
    modulo_actualizado = response.json()
    assert modulo_actualizado["nombre"] == "Módulo Smoke Actualizado"
    assert modulo_actualizado["codigo"] == f"SMOKE_TEST_MOD_{suf}"  # No cambia

    # 5. Eliminar módulo
    response = client.delete(f"/api/v1/modulos/{modulo_id}")
    assert response.status_code in (200, 204)

    # 6. Verificar que está inactivo
    response = client.get(f"/api/v1/modulos/{modulo_id}")
    assert response.status_code == 404 or (response.status_code == 200 and not response.json()["activo"])


@pytest.mark.skipif(not is_port_open("localhost", 8000), reason="Server not listening on localhost:8000")
def test_modulo_codigo_unico():
    """Test que el código del módulo debe ser único."""

    suf = uuid.uuid4().hex[:6]
    create_data = {
        "codigo": f"UNIQUE_CODE_TEST_{suf}",
        "nombre": "Módulo Único",
        "usuario_auditoria": "smoke_test"
    }

    # Primera creación exitosa
    response = client.post("/api/v1/modulos", json=create_data)
    assert response.status_code == 201
    modulo_id = response.json()["id"]

    # Segunda creación con mismo código debe fallar
    response = client.post("/api/v1/modulos", json=create_data)
    assert response.status_code in [400, 409, 422], "Debería fallar por código duplicado"

    # Limpiar
    client.delete(f"/api/v1/modulos/{modulo_id}")


@pytest.mark.skipif(not is_port_open("localhost", 8000), reason="Server not listening on localhost:8000")
def test_modulo_campos_minimos():
    """Test crear módulo solo con campos obligatorios."""

    suf = uuid.uuid4().hex[:6]
    create_data = {
        "codigo": f"MIN_MOD_TEST_{suf}",
        "nombre": "Módulo Mínimo",
        "usuario_auditoria": "smoke_test"
    }

    response = client.post("/api/v1/modulos", json=create_data)
    assert response.status_code == 201
    modulo = response.json()

    assert modulo["codigo"] == f"MIN_MOD_TEST_{suf}"
    assert modulo["nombre"] == "Módulo Mínimo"
    assert modulo.get("descripcion") is None
    assert modulo.get("orden") is None
    assert modulo.get("icono") is None

    # Limpiar
    client.delete(f"/api/v1/modulos/{modulo['id']}")


@pytest.mark.skipif(not is_port_open("localhost", 8000), reason="Server not listening on localhost:8000")
def test_modulo_paginacion():
    """Test paginación de módulos."""

    # Crear varios módulos
    suf = uuid.uuid4().hex[:6]
    modulos_ids = []
    for i in range(5):
        create_data = {
            "codigo": f"PAG_MOD_{suf}_{i}",
            "nombre": f"Módulo Paginación {i}",
            "orden": i,
            "usuario_auditoria": "smoke_test"
        }
        response = client.post("/api/v1/modulos", json=create_data)
        assert response.status_code == 201
        modulos_ids.append(response.json()["id"])

    # Probar paginación
    response = client.get("/api/v1/modulos?skip=0&limit=3")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3

    response = client.get("/api/v1/modulos?skip=3&limit=3")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) >= 2

    # Limpiar
    for modulo_id in modulos_ids:
        client.delete(f"/api/v1/modulos/{modulo_id}")

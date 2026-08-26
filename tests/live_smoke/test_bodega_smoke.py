"""
Smoke test para endpoints de Bodega
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
def test_bodega_crud_completo():
    """
    Verificar CRUD de bodega:
    - Crear una empresa
    - Crear una sucursal (opcional)
    - Crear bodega asociada a empresa y sucursal
    - Listar bodegas por empresa_id
    - Actualizar datos de bodega
    - Eliminar (soft delete)
    """
    with httpx.Client(timeout=TIMEOUT) as client:
        unique_suffix = uuid.uuid4().hex[:6]

        # 1. Crear empresa (con reintento si falla validación RUC)
        from tests.smoke.ruc_utils import generar_ruc_empresa
        empresa_id = None
        max_attempts = 5
        for attempt in range(max_attempts):
            empresa_data = {
                "razon_social": "Empresa Test Bodega SRL",
                "nombre_comercial": f"Comercial Bod-{unique_suffix}",
                "ruc": generar_ruc_empresa(),
                "direccion_matriz": "Calle Test 123",
                "telefono": "0987654321",
                "obligado_contabilidad": True,
                "tipo_contribuyente_id": "01",
                "usuario_auditoria": "smoke_test"
            }
            r = client.post(f"{BASE}/empresas", json=empresa_data)
            if r.status_code in (201, 409):
                empresa_id = r.json()["id"] if r.status_code == 201 else r.json().get("id")
                break
            elif r.status_code == 422:
                # RUC inválido, reintentar
                continue
            else:
                assert False, f"Error inesperado: {r.status_code} - {r.text}"

        assert empresa_id is not None, "No se pudo crear empresa después de varios intentos"

        # 2. Crear sucursal
        sucursal_data = {
            "codigo": f"{unique_suffix[:3]}",
            "nombre": f"Sucursal_Test_{unique_suffix}",
            "direccion": "Av. Test 456",
            "telefono": "0987654322",
            "empresa_id": empresa_id,
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/sucursales", json=sucursal_data)
        assert r.status_code == 201, f"Failed to create sucursal: {r.text}"
        sucursal_id = r.json()["id"]

        # 3. Crear bodega con sucursal
        bodega_data = {
            "codigo_bodega": f"BOD{unique_suffix[:6].upper()}",
            "nombre_bodega": f"Bodega_Test_{unique_suffix}",
            "descripcion": "Bodega de prueba para smoke test",
            "empresa_id": empresa_id,
            "sucursal_id": sucursal_id,
        }
        r = client.post(f"{BASE}/bodegas", json=bodega_data)
        assert r.status_code == 201, f"Failed to create bodega: {r.text}"
        bodega_id = r.json()["id"]

        # 4. Verificar con GET individual
        r = client.get(f"{BASE}/bodegas/{bodega_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["empresa_id"] == empresa_id
        assert data["sucursal_id"] == sucursal_id
        assert data["codigo_bodega"] == f"BOD{unique_suffix[:6].upper()}"
        assert data["nombre_bodega"] == f"Bodega_Test_{unique_suffix}"

        # 5. Listar bodegas de esta empresa
        r = client.get(f"{BASE}/bodegas?empresa_id={empresa_id}")
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1
        found = any(item["id"] == bodega_id for item in items)
        assert found, "Bodega no encontrada en listado por empresa_id"

        # 6. Actualizar bodega
        update_data = {
            "codigo_bodega": f"BOD{unique_suffix[:6].upper()}_UPD",
            "nombre_bodega": f"Bodega_Actualizada_{unique_suffix}",
            "descripcion": "Descripción actualizada",
        }
        r = client.put(f"{BASE}/bodegas/{bodega_id}", json=update_data)
        assert r.status_code == 200
        updated = r.json()
        assert updated["codigo_bodega"] == f"BOD{unique_suffix[:6].upper()}_UPD"
        assert updated["nombre_bodega"] == f"Bodega_Actualizada_{unique_suffix}"
        assert updated["descripcion"] == "Descripción actualizada"

        # 7. Eliminar (soft delete)
        r = client.delete(f"{BASE}/bodegas/{bodega_id}")
        assert r.status_code == 204

        # 8. Verificar que ya no aparece en listado (soft delete)
        r = client.get(f"{BASE}/bodegas/{bodega_id}")
        # Si implementas filtro de activos, debería retornar 404 o no encontrarse
        # Por ahora verificamos que no está en el listado activo
        r = client.get(f"{BASE}/bodegas?empresa_id={empresa_id}")
        items = r.json()
        found = any(item["id"] == bodega_id for item in items)
        assert not found, "Bodega eliminada aún aparece en listado activo"

        # Cleanup: eliminar sucursal y empresa
        client.delete(f"{BASE}/sucursales/{sucursal_id}")
        client.delete(f"{BASE}/empresas/{empresa_id}")


@pytest.mark.skipif(
    not is_port_open("localhost", 8000),
    reason="Server not listening on localhost:8000"
)
def test_bodega_sin_sucursal():
    """
    Verificar que se puede crear bodega sin sucursal (bodega de matriz)
    """
    with httpx.Client(timeout=TIMEOUT) as client:
        unique_suffix = uuid.uuid4().hex[:6]

        # Crear empresa (con reintento si falla validación RUC)
        from tests.smoke.ruc_utils import generar_ruc_empresa
        empresa_id = None
        max_attempts = 5
        for attempt in range(max_attempts):
            empresa_data = {
                "razon_social": "Empresa Matriz Bodega SA",
                "nombre_comercial": f"Comercial Mat-{unique_suffix}",
                "ruc": generar_ruc_empresa(),
                "direccion_matriz": "Calle Matriz 789",
                "telefono": "0987654323",
                "obligado_contabilidad": False,
                "tipo_contribuyente_id": "01",
                "usuario_auditoria": "smoke_test"
            }
            r = client.post(f"{BASE}/empresas", json=empresa_data)
            if r.status_code in (201, 409):
                empresa_id = r.json()["id"] if r.status_code == 201 else r.json().get("id")
                break
            elif r.status_code == 422:
                # RUC inválido, reintentar
                continue
            else:
                assert False, f"Error inesperado: {r.status_code} - {r.text}"

        assert empresa_id is not None, "No se pudo crear empresa después de varios intentos"

        # Crear bodega sin sucursal
        bodega_data = {
            "codigo_bodega": f"BODMAT{unique_suffix[:4].upper()}",
            "nombre_bodega": f"Bodega_Matriz_{unique_suffix}",
            "descripcion": None,
            "empresa_id": empresa_id,
            "sucursal_id": None,
        }
        r = client.post(f"{BASE}/bodegas", json=bodega_data)
        assert r.status_code == 201, f"Failed to create bodega sin sucursal: {r.text}"
        bodega_id = r.json()["id"]

        # Verificar que sucursal_id es null
        r = client.get(f"{BASE}/bodegas/{bodega_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["sucursal_id"] is None
        assert data["empresa_id"] == empresa_id

        # Cleanup
        client.delete(f"{BASE}/bodegas/{bodega_id}")
        client.delete(f"{BASE}/empresas/{empresa_id}")


@pytest.mark.skipif(
    not is_port_open("localhost", 8000),
    reason="Server not listening on localhost:8000"
)
def test_bodega_filtro_por_sucursal():
    """
    Verificar filtrado de bodegas por sucursal_id
    """
    with httpx.Client(timeout=TIMEOUT) as client:
        unique_suffix = uuid.uuid4().hex[:6]

        # Crear empresa (con reintento si falla validación RUC)
        from tests.smoke.ruc_utils import generar_ruc_empresa
        empresa_id = None
        max_attempts = 5
        for attempt in range(max_attempts):
            empresa_data = {
                "razon_social": "Empresa Filtro Bodega CIA",
                "nombre_comercial": f"Comercial Fil-{unique_suffix}",
                "ruc": generar_ruc_empresa(),
                "direccion_matriz": "Calle Filtro 321",
                "telefono": "0987654324",
                "obligado_contabilidad": True,
                "tipo_contribuyente_id": "01",
                "usuario_auditoria": "smoke_test"
            }
            r = client.post(f"{BASE}/empresas", json=empresa_data)
            if r.status_code in (201, 409):
                empresa_id = r.json()["id"] if r.status_code == 201 else r.json().get("id")
                break
            elif r.status_code == 422:
                # RUC inválido, reintentar
                continue
            else:
                assert False, f"Error inesperado: {r.status_code} - {r.text}"

        assert empresa_id is not None, "No se pudo crear empresa después de varios intentos"

        # Crear dos sucursales
        sucursal1_data = {
            "codigo": "101",
            "nombre": "Sucursal Norte",
            "direccion": "Av. Test 111",
            "telefono": "0987654325",
            "empresa_id": empresa_id,
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/sucursales", json=sucursal1_data)
        assert r.status_code in (201, 409)
        sucursal1_id = r.json()["id"] if r.status_code == 201 else r.json().get("id")

        sucursal2_data = {
            "codigo": "102",
            "nombre": "Sucursal Sur",
            "direccion": "Av. Test 222",
            "telefono": "0987654326",
            "empresa_id": empresa_id,
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/sucursales", json=sucursal2_data)
        assert r.status_code in (201, 409)
        sucursal2_id = r.json()["id"] if r.status_code == 201 else r.json().get("id")

        # Crear bodegas en cada sucursal
        bodega1_data = {
            "codigo_bodega": f"BOD1{unique_suffix[:5].upper()}",
            "nombre_bodega": f"Bodega_Suc1_{unique_suffix}",
            "descripcion": "Bodega de sucursal 1",
            "empresa_id": empresa_id,
            "sucursal_id": sucursal1_id,
        }
        r = client.post(f"{BASE}/bodegas", json=bodega1_data)
        assert r.status_code == 201
        bodega1_id = r.json()["id"]

        bodega2_data = {
            "codigo_bodega": f"BOD2{unique_suffix[:5].upper()}",
            "nombre_bodega": f"Bodega_Suc2_{unique_suffix}",
            "descripcion": "Bodega de sucursal 2",
            "empresa_id": empresa_id,
            "sucursal_id": sucursal2_id,
        }
        r = client.post(f"{BASE}/bodegas", json=bodega2_data)
        assert r.status_code == 201
        bodega2_id = r.json()["id"]

        # Filtrar por sucursal 1
        r = client.get(f"{BASE}/bodegas?sucursal_id={sucursal1_id}")
        assert r.status_code == 200
        items = r.json()
        found_bodega1 = any(item["id"] == bodega1_id for item in items)
        found_bodega2 = any(item["id"] == bodega2_id for item in items)
        assert found_bodega1, "Bodega 1 no encontrada en filtro por sucursal 1"
        assert not found_bodega2, "Bodega 2 aparece en filtro por sucursal 1"

        # Filtrar por sucursal 2
        r = client.get(f"{BASE}/bodegas?sucursal_id={sucursal2_id}")
        assert r.status_code == 200
        items = r.json()
        found_bodega1 = any(item["id"] == bodega1_id for item in items)
        found_bodega2 = any(item["id"] == bodega2_id for item in items)
        assert not found_bodega1, "Bodega 1 aparece en filtro por sucursal 2"
        assert found_bodega2, "Bodega 2 no encontrada en filtro por sucursal 2"

        # Cleanup
        client.delete(f"{BASE}/bodegas/{bodega1_id}")
        client.delete(f"{BASE}/bodegas/{bodega2_id}")
        client.delete(f"{BASE}/sucursales/{sucursal1_id}")
        client.delete(f"{BASE}/sucursales/{sucursal2_id}")
        client.delete(f"{BASE}/empresas/{empresa_id}")

import pytest

from tests.smoke.utils import BASE, get_client, is_port_open, wait_for_service, retry_on_exception


@pytest.mark.skipif(not is_port_open("localhost", 8000), reason="Server not listening on localhost:8000")
def test_empresa_sucursal_punto_emision_flow():
    # Esperar que la app esté lista (docs)
    if not wait_for_service("/docs", timeout=20):
        pytest.skip("server not ready on /docs")

    with get_client() as client:
        # Create empresa with valid RUC
        from tests.smoke.ruc_utils import generar_ruc_empresa
        empresa_payload = {
            "ruc": generar_ruc_empresa(),  # genera RUC válido (13 dígitos, verificador calculado)
            "razon_social": "Smoke Empresa SRL",  # solo letras y espacios
            "nombre_comercial": "SmokeEmp 001",  # letras, números, espacios, puntos, comas, guiones
            "direccion_matriz": "Av Principal 123",
            "telefono": "0987654321",  # 10 dígitos
            "tipo_contribuyente_id": "01",  # exactamente 2 caracteres
            "obligado_contabilidad": False,
            "regimen": "GENERAL",
            "modo_emision": "ELECTRONICO",
            "usuario_auditoria": "ci",
        }

        # Create empresa (with retry)
        @retry_on_exception(retries=3, backoff=1.0)
        def create_empresa():
            return client.post(f"{BASE}/empresas", json=empresa_payload)
        r = create_empresa()
        for _ in range(4):
            if r.status_code in (201, 409):
                break
            if r.status_code in (400, 422) and ("ruc" in r.text.lower() or "RUC" in r.text):
                empresa_payload["ruc"] = generar_ruc_empresa()
                r = create_empresa()
                continue
            break
        assert r.status_code in (201, 409)
        empresa_id = r.json().get("id") if r.status_code == 201 else None

        # Si no se creó ahora, intentar buscar una empresa con ese RUC: (list + filter simple)
        if not empresa_id:
            r = client.get(f"{BASE}/empresas?limit=10&offset=0&only_active=true")
            assert r.status_code == 200
            items = r.json().get("items", [])
            for it in items:
                if it.get("ruc") == empresa_payload["ruc"]:
                    empresa_id = it.get("id")
                    break

        assert empresa_id is not None, "No se pudo determinar empresa_id"

        # Sucursal (con código de 3 dígitos y otras validaciones)
        sucursal_payload = {
            "empresa_id": empresa_id,
            "codigo": "001",  # 3 dígitos requerido
            "nombre": "Sucursal Principal",  # min 3 chars
            "direccion": "Avenida Central 123",  # min 3 chars
            "telefono": "0987654321",  # 7-10 dígitos
            "es_matriz": True,
            "usuario_auditoria": "ci",
        }
        r = client.post(f"{BASE}/sucursales", json=sucursal_payload)
        assert r.status_code in (201, 409, 400)
        sucursal_id = r.json().get("id") if r.status_code == 201 else None

        # Si no se creó ahora, buscar por empresa_id
        if not sucursal_id:
            r = client.get(f"{BASE}/sucursales?limit=50&offset=0&only_active=true")
            assert r.status_code == 200
            for it in r.json().get("items", []):
                if it.get("empresa_id") == empresa_id:
                    sucursal_id = it.get("id")
                    break

        assert sucursal_id is not None, "No se pudo determinar sucursal_id"

        # Punto de emisión
        punto_payload = {
            "sucursal_id": sucursal_id,
            "codigo": "001",  # 3 dígitos
            "descripcion": "Punto Principal",  # Requerido
            "secuencial_actual": 1,
            "usuario_auditoria": "ci",
        }
        r = client.post(f"{BASE}/puntos-emision", json=punto_payload)
        assert r.status_code in (201, 409)
        punto_id = r.json().get("id") if r.status_code == 201 else None

        # Si no se creó ahora, buscar por sucursal_id y código
        if not punto_id:
            r = client.get(f"{BASE}/puntos-emision?limit=50&offset=0&only_active=true")
            assert r.status_code == 200
            for it in r.json().get("items", []):
                if it.get("sucursal_id") == sucursal_id and it.get("codigo") == punto_payload["codigo"]:
                    punto_id = it.get("id")
                    break

        assert punto_id is not None, "No se pudo determinar punto_id"

        # Limpieza (best-effort)
        try:
            client.delete(f"{BASE}/puntos-emision/{punto_id}")
        except Exception:
            pass
        try:
            client.delete(f"{BASE}/sucursales/{sucursal_id}")
        except Exception:
            pass
        # No borramos empresa para evitar romper otras pruebas

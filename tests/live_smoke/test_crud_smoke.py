import contextlib
import socket
import uuid
import pytest

BASE = "http://localhost:8000/api/v1"
TIMEOUT = 5.0


def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not is_port_open("localhost", 8000), reason="Server not listening on localhost:8000")
def test_roles_crud(client):
    with contextlib.nullcontext(client):
        # Clean list
        r = client.get(f"{BASE}/roles")
        assert r.status_code == 200

        # Create or find role
        payload = {"nombre": "smoke-role", "descripcion": "smoke test", "usuario_auditoria": "ci"}
        r = client.post(f"{BASE}/roles", json=payload)
        assert r.status_code in (201, 409)

        # Si ya existe, buscar por nombre
        if r.status_code == 409:
            r = client.get(f"{BASE}/roles?limit=50&offset=0")
            assert r.status_code == 200
            for item in r.json().get("items", []):
                if item.get("nombre") == payload["nombre"]:
                    role_id = item.get("id")
                    break
            assert role_id, "Role 'smoke-role' not found"
        else:
            data = r.json()
            role_id = data.get("id")
            assert role_id

        # Get by id
        r = client.get(f"{BASE}/roles/{role_id}")
        assert r.status_code == 200
        assert r.json().get("nombre") == "smoke-role"

        # Update (usando nombre único para evitar conflictos)
        unique_name = f"smoke-role-{uuid.uuid4().hex[:8]}"
        up = {"nombre": unique_name, "descripcion": "updated", "usuario_auditoria": "ci"}
        r = client.put(f"{BASE}/roles/{role_id}", json=up)
        assert r.status_code == 200
        assert r.json().get("nombre") == unique_name

        # Delete
        r = client.delete(f"{BASE}/roles/{role_id}")
        assert r.status_code == 204


@pytest.mark.skipif(not is_port_open("localhost", 8000), reason="Server not listening on localhost:8000")
def test_persona_and_cliente_flow(client):
    with contextlib.nullcontext(client):
        # Create or find tipo cliente
        tipo = {"nombre": "smoke-tipo", "descuento": 0, "usuario_auditoria": "ci"}
        r = client.post(f"{BASE}/tipos-cliente", json=tipo)
        assert r.status_code in (201, 409)

        # Si ya existe, buscar por nombre
        if r.status_code == 409:
            r = client.get(f"{BASE}/tipos-cliente?limit=50&offset=0")
            assert r.status_code == 200
            for item in r.json().get("items", []):
                if item.get("nombre") == tipo["nombre"]:
                    tipo_id = item.get("id")
                    break
            assert tipo_id, "Tipo cliente 'smoke-tipo' not found"
        else:
            tipo_id = r.json().get("id")
            assert tipo_id

        # Create persona with unique ID to avoid conflicts
        unique_id = f"TST{uuid.uuid4().hex[:8]}"
        persona = {
            "identificacion": unique_id,
            "tipo_identificacion": "PASAPORTE",
            "nombre": "Smoke",
            "apellido": "Tester",
            "usuario_auditoria": "ci"
        }
        r = client.post(f"{BASE}/personas", json=persona)
        assert r.status_code == 201  # Ahora debería ser único
        persona_id = r.json().get("id")

        # Create cliente using persona + tipo
        cliente = {"persona_id": persona_id, "tipo_cliente_id": tipo_id, "usuario_auditoria": "ci"}
        r = client.post(f"{BASE}/clientes", json=cliente)
        assert r.status_code == 201
        cliente_id = r.json().get("id")

        # Cleanup: delete cliente
        r = client.delete(f"{BASE}/clientes/{cliente_id}")
        assert r.status_code == 204


@pytest.mark.skipif(not is_port_open("localhost", 8000), reason="Server not listening on localhost:8000")
def test_inventory_categories_flow(client):
    with contextlib.nullcontext(client):
        try:
            # Create parent category
            payload = {
                "nombre": "Categoría Padre Test",
                "es_padre": True,
                "parent_id": None,
                "usuario_auditoria": "ci"
            }
            r = client.post(f"{BASE}/categorias", json=payload)
            assert r.status_code == 201
            parent_id = r.json().get("id")
            assert parent_id

            # Create child category
            child = {
                "nombre": "Subcategoría Test",
                "es_padre": False,
                "parent_id": parent_id,
                "usuario_auditoria": "ci"
            }
            r = client.post(f"{BASE}/categorias", json=child)
            assert r.status_code == 201
            child_id = r.json().get("id")
            assert child_id

            # Verify parent category
            r = client.get(f"{BASE}/categorias/{parent_id}")
            assert r.status_code == 200
            assert r.json().get("es_padre") is True
            assert r.json().get("parent_id") is None

            # Verify child category
            r = client.get(f"{BASE}/categorias/{child_id}")
            assert r.status_code == 200
            assert r.json().get("es_padre") is False
            assert r.json().get("parent_id") == parent_id

            # Update child category with unique name
            unique_name = f"Subcategoría-{uuid.uuid4().hex[:8]}"
            up = {"nombre": unique_name, "es_padre": False, "parent_id": parent_id, "usuario_auditoria": "ci"}
            r = client.put(f"{BASE}/categorias/{child_id}", json=up)
            assert r.status_code == 200
            assert r.json().get("nombre") == unique_name

            # Try to make parent category a child (should fail)
            bad_update = {"nombre": "Test", "es_padre": False, "parent_id": child_id, "usuario_auditoria": "ci"}
            r = client.put(f"{BASE}/categorias/{parent_id}", json=bad_update)
            assert r.status_code in (400, 422)  # Debería fallar por ciclo o validación

        finally:
            # Cleanup: Intentar eliminar todas las categorías creadas en orden correcto
            print("\nLimpiando categorías...")

            # 1. Obtener todas las categorías
            r = client.get(f"{BASE}/categorias")
            if r.status_code == 200:
                cats = r.json().get("items", [])

                # 2. Primero eliminar todas las categorías hijas
                for cat in cats:
                    if not cat.get("es_padre"):
                        print(f"Eliminando categoría hija: {cat.get('nombre')}")
                        r = client.delete(f"{BASE}/categorias/{cat.get('id')}")
                        if r.status_code != 204:
                            print(f"Error al eliminar categoría hija {cat.get('id')}: {r.status_code}")

                # 3. Luego eliminar todas las categorías padre
                for cat in cats:
                    if cat.get("es_padre"):
                        print(f"Eliminando categoría padre: {cat.get('nombre')}")
                        r = client.delete(f"{BASE}/categorias/{cat.get('id')}")
                        if r.status_code != 204:
                            print(f"Error al eliminar categoría padre {cat.get('id')}: {r.status_code}")

                # 4. Verificar que no queden categorías
                r = client.get(f"{BASE}/categorias")
                assert r.status_code == 200
                final_cats = r.json().get("items", [])
                if len(final_cats) > 0:
                    print(f"ADVERTENCIA: Quedaron {len(final_cats)} categorías sin eliminar")
                else:
                    print("Todas las categorías fueron eliminadas correctamente")


@pytest.mark.skipif(not is_port_open("localhost", 8000), reason="Server not listening on localhost:8000")
def test_casas_comerciales_crud(client):
    with contextlib.nullcontext(client):
        # Clean list
        r = client.get(f"{BASE}/casas-comerciales")
        assert r.status_code == 200

        # Create casa comercial with unique name
        unique_name = f"Casa-{uuid.uuid4().hex[:8]}"
        payload = {"nombre": unique_name, "usuario_auditoria": "ci"}
        r = client.post(f"{BASE}/casas-comerciales", json=payload)
        assert r.status_code == 201
        data = r.json()
        casa_id = data.get("id")
        assert casa_id
        assert data.get("nombre") == unique_name
        assert data.get("activo") is True

        # Get by id
        r = client.get(f"{BASE}/casas-comerciales/{casa_id}")
        assert r.status_code == 200
        assert r.json().get("nombre") == unique_name

        # Update with another unique name
        updated_name = f"Casa-Updated-{uuid.uuid4().hex[:8]}"
        up = {"nombre": updated_name, "usuario_auditoria": "ci"}
        r = client.put(f"{BASE}/casas-comerciales/{casa_id}", json=up)
        assert r.status_code == 200
        assert r.json().get("nombre") == updated_name

        # Delete
        r = client.delete(f"{BASE}/casas-comerciales/{casa_id}")
        assert r.status_code == 204

        # Verify it's marked as inactive (soft delete): GET devuelve 404 o 200
        r = client.get(f"{BASE}/casas-comerciales/{casa_id}")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert r.json().get("activo") is False


@pytest.mark.skipif(not is_port_open("localhost", 8000), reason="Server not listening on localhost:8000")
def test_users_employees_and_providers_flow(client):
    with contextlib.nullcontext(client):
        # Create role for user/employee (or find existing)
        role_name = f"smoke-role-{uuid.uuid4().hex[:8]}"
        payload = {"nombre": role_name, "descripcion": "role for tests", "usuario_auditoria": "ci"}
        r = client.post(f"{BASE}/roles", json=payload)
        assert r.status_code in (201, 409)

        # Si hay conflicto, buscar por nombre
        if r.status_code == 409:
            r = client.get(f"{BASE}/roles?limit=50&offset=0")
            assert r.status_code == 200
            for item in r.json().get("items", []):
                if item.get("nombre") == role_name:
                    role_id = item.get("id")
                    break
            assert role_id, f"Role '{role_name}' not found"
        else:
            role_id = r.json().get("id")
            assert role_id

        # Create tipo cliente with unique name
        tipo_name = f"smoke-tipo-{uuid.uuid4().hex[:8]}"
        payload = {"nombre": tipo_name, "descuento": 0, "usuario_auditoria": "ci"}
        r = client.post(f"{BASE}/tipos-cliente", json=payload)
        assert r.status_code == 201
        tipo_id = r.json().get("id")

        # Create persona (con RUC válido de persona natural para proveedor)
        from tests.smoke.ruc_utils import generar_ruc_persona_natural
        persona = {
            "identificacion": generar_ruc_persona_natural(),  # RUC persona natural
            "tipo_identificacion": "RUC",  # Solo RUC para proveedores
            "nombre": "SmokeP",
            "apellido": "Tester",
            "usuario_auditoria": "ci"
        }
        r = client.post(f"{BASE}/personas", json=persona)
        assert r.status_code == 201
        persona_id = r.json().get("id")

        # Create usuario with unique username
        unique_user = f"smoke_user_{uuid.uuid4().hex[:8]}"
        usuario = {"persona_id": persona_id, "rol_id": role_id, "username": unique_user, "password": "secret123", "usuario_auditoria": "ci"}
        r = client.post(f"{BASE}/usuarios", json=usuario)
        assert r.status_code == 201

        # Create cliente
        cliente = {"persona_id": persona_id, "tipo_cliente_id": tipo_id, "usuario_auditoria": "ci"}
        r = client.post(f"{BASE}/clientes", json=cliente)
        assert r.status_code == 201
        cliente_id = r.json().get("id")

        # Create empresa for empleado
        from tests.smoke.ruc_utils import generar_ruc_empresa
        empresa_payload = {
            "ruc": generar_ruc_empresa(),
            "razon_social": "Empresa de Pruebas SmokeTest",
            "nombre_comercial": f"EmpTest{uuid.uuid4().hex[:8]}",
            "direccion_matriz": "Av Principal 123",
            "telefono": "0987654321",
            "tipo_contribuyente_id": "01",
            "usuario_auditoria": "ci"
        }
        # Reintentar hasta 3 veces si el RUC generado no es válido
        empresa_id = None
        for attempt in range(3):
            r = client.post(f"{BASE}/empresas", json=empresa_payload)
            if r.status_code == 201:
                empresa_id = r.json().get("id")
                break
            # Si el RUC no es válido, generar otro
            if r.status_code in (400, 422) and attempt < 2:
                empresa_payload["ruc"] = generar_ruc_empresa()
                continue
            assert r.status_code == 201, f"Error creando empresa: {r.text}"
        assert empresa_id, "No se pudo crear la empresa"

        # Create empleado with unique username
        unique_emp = f"smoke_emp_{uuid.uuid4().hex[:8]}"
        empleado_payload = {
            "persona_id": persona_id,
            "empresa_id": empresa_id,
            "salario": "1000.00",
            "fecha_ingreso": "2024-01-01",
            "fecha_nacimiento": "1990-01-01",
            "usuario": {"username": unique_emp, "password": "secret123", "rol_id": role_id, "usuario_auditoria": "ci"},
            "usuario_auditoria": "ci",
        }
        r = client.post(f"{BASE}/empleados", json=empleado_payload)
        assert r.status_code in (201, 409)  # La persona puede ya estar registrada como empleado

        # Create proveedor persona with unique nombre_comercial
        unique_prov = f"ProvPerson_{uuid.uuid4().hex[:8]}"
        provp = {
            "nombre_comercial": unique_prov,
            "tipo_contribuyente_id": "01",
            "persona_id": persona_id,
            "usuario_auditoria": "ci"
        }
        r = client.post(f"{BASE}/proveedores-persona", json=provp)
        assert r.status_code == 201, f"Error creating proveedor persona: {r.text}"
        provp_id = r.json().get("id")

        # Create proveedor sociedad with unique RUC and nombre_comercial
        from tests.smoke.ruc_utils import generar_ruc_empresa
        provs = {
            "ruc": generar_ruc_empresa(),
            "razon_social": f"Prov SA {uuid.uuid4().hex[:8]}",
            "nombre_comercial": f"ProvSA {uuid.uuid4().hex[:8]}",
            "direccion": "Calle Principal 123",
            "telefono": "0987654321",
            "email": f"prov{uuid.uuid4().hex[:8]}@example.com",
            "tipo_contribuyente_id": "02",  # Cambiado a tipo 02, 01 no está permitido para sociedades
            "persona_contacto_id": persona_id,
            "usuario_auditoria": "ci"
        }
        # Algunos RUC generados pueden fallar validación en el servidor; reintentar hasta 3 veces
        provs_id = None
        for attempt in range(3):
            r = client.post(f"{BASE}/proveedores-sociedad", json=provs)
            print(f"[Debug][attempt {attempt+1}] Response: {r.text}")
            if r.status_code == 201:
                provs_id = r.json().get("id")
                break
            # Si la respuesta indica RUC inválido, generar otro y reintentar
            if r.status_code == 400 and "RUC no es válido" in r.text and attempt < 2:
                from tests.smoke.ruc_utils import generar_ruc_empresa
                provs["ruc"] = generar_ruc_empresa()
                continue
            # otro error: fallar
            assert r.status_code == 201, f"Error creando proveedor sociedad: {r.text}"

        # Cleanup created resources (best-effort)
        client.delete(f"{BASE}/clientes/{cliente_id}")
        client.delete(f"{BASE}/proveedores-persona/{provp_id}")
        client.delete(f"{BASE}/proveedores-sociedad/{provs_id}")
        client.delete(f"{BASE}/empresas/{empresa_id}")
        client.delete(f"{BASE}/roles/{role_id}")

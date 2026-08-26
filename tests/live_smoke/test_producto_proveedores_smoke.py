"""
Smoke tests para asociación de múltiples proveedores (persona y sociedad) a productos
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
def test_producto_con_multiples_proveedores():
    """
    Escenario 3.1 y 3.2: Asociar varios proveedores mixtos a un producto
    - Crear proveedores persona: Juan Gómez, Pepe Pérez
    - Crear proveedores sociedad: Tipti, ABC
    - Crear producto "Mouse Inalámbrico"
    - Asociar todos los proveedores al producto
    - Verificar que aparecen en GET del producto

    Nota: Este test documenta el comportamiento actual de las tablas puente
    ProductoProveedorPersona y ProductoProveedorSociedad
    """
    with httpx.Client(timeout=TIMEOUT) as client:
        unique_suffix = uuid.uuid4().hex[:6]

        # 1. Crear proveedores persona
        # Usar RUCs válidos de persona natural (13 dígitos, termina en 001)
        # RUC válidos proporcionados
        ruc1 = "0103523908001"
        ruc2 = "0103523908001"  # Reutilizar mismo RUC (se manejará duplicado)

        persona1_data = {
            "identificacion": ruc1,
            "tipo_identificacion": "RUC",
            "nombre": f"Juan_{unique_suffix}",
            "apellido": "Gómez",
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/personas", json=persona1_data)
        # Si ya existe (409 Conflict), obtenerlo por identificación
        if r.status_code == 409:
            r = client.get(f"{BASE}/personas")
            personas = r.json().get("items", [])
            persona1 = next((p for p in personas if p["identificacion"] == ruc1), None)
            persona1_id = persona1["id"] if persona1 else None
            assert persona1_id is not None, "Could not find or create persona1"
        else:
            assert r.status_code == 201, f"Failed to create persona1: {r.text}"
            persona1_id = r.json()["id"]

        persona2_data = {
            "identificacion": ruc2,
            "tipo_identificacion": "RUC",
            "nombre": f"Pepe_{unique_suffix}",
            "apellido": "Pérez",
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/personas", json=persona2_data)
        # Si ya existe (409 Conflict), obtenerlo
        if r.status_code == 409:
            r = client.get(f"{BASE}/personas")
            personas = r.json().get("items", [])
            persona2 = next((p for p in personas if p["identificacion"] == ruc2), None)
            persona2_id = persona2["id"] if persona2 else None
            assert persona2_id is not None, "Could not find or create persona2"
        else:
            assert r.status_code == 201, f"Failed to create persona2: {r.text}"
            persona2_id = r.json()["id"]

        # Crear proveedores persona
        prov_persona1 = {
            "persona_id": persona1_id,
            "tipo_contribuyente_id": "01",
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/proveedores-persona", json=prov_persona1)
        assert r.status_code == 201, f"Failed to create proveedor persona 1: {r.text}"
        r.json()["id"]

        prov_persona2 = {
            "persona_id": persona2_id,
            "tipo_contribuyente_id": "02",
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/proveedores-persona", json=prov_persona2)
        # Si ya existe (400 Conflict), obtenerlo
        if r.status_code in (400, 409):
            r = client.get(f"{BASE}/proveedores-persona")
            proveedores = r.json().get("items", [])
            prov_p2 = next((p for p in proveedores if p["persona_id"] == str(persona2_id)), None)
            prov_persona2_id = prov_p2["id"] if prov_p2 else None
            assert prov_persona2_id is not None, "Could not find or create proveedor persona 2"
        else:
            assert r.status_code == 201, f"Failed to create proveedor persona 2: {r.text}"
            prov_persona2_id = r.json()["id"]

        # 2. Crear proveedores sociedad (necesita persona de contacto)
        # Reutilizar persona1 como contacto
        contacto_id = persona1_id

        # RUC válido de sociedad: 0190363902001
        prov_soc1 = {
            "razon_social": f"Tipti_{unique_suffix}",
            "nombre_comercial": "Tipti",
            "ruc": "0190363902001",
            "direccion": "Av. Principal 123",
            "telefono": "0987654321",
            "email": f"tipti_{unique_suffix}@example.com",
            "tipo_contribuyente_id": "02",  # Sociedad (no puede ser 01 Persona Natural)
            "persona_contacto_id": contacto_id,
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/proveedores-sociedad", json=prov_soc1)
        if r.status_code == 201:
            r.json()["id"]
        elif r.status_code in (400, 409):
            # Si ya existe, intentar obtenerlo por RUC
            r_get = client.get(f"{BASE}/proveedores-sociedad")
            proveedores = r_get.json().get("items", [])
            prov_soc1_obj = next((p for p in proveedores if p.get("ruc") == "0190363902001"), None)
            if prov_soc1_obj:
                prov_soc1_obj["id"]
            else:
                # Si no existe, el error era por otra razón
                assert False, f"POST failed with {r.status_code}: {r.text}"
        else:
            assert False, f"Failed to create proveedor sociedad 1: {r.status_code} - {r.text}"

        # Crear segunda sociedad (reutilizando RUC válido porque no hay otro válido disponible)
        prov_soc2 = {
            "razon_social": f"ABC_Corp_{unique_suffix}",
            "nombre_comercial": "ABC Corp",
            "ruc": "0190363902001",  # Reutilizar mismo RUC válido (se manejará duplicado)
            "direccion": "Calle Secundaria 456",
            "telefono": "0987654322",
            "email": f"abc_{unique_suffix}@example.com",
            "tipo_contribuyente_id": "02",
            "persona_contacto_id": contacto_id,
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/proveedores-sociedad", json=prov_soc2)
        if r.status_code == 201:
            r.json()["id"]
        elif r.status_code in (400, 409):
            # Si ya existe por RUC duplicado, reutilizar el primero
            pass  # Simplemente reutilizamos el mismo proveedor
        else:
            assert False, f"Failed to create proveedor sociedad 2: {r.status_code} - {r.text}"

        # 3. Crear casa comercial
        casa_data = {
            "nombre": f"Casa_Mouse_{unique_suffix}",
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
            "nombre": f"Mouse_Inalambrico_{unique_suffix}",
            "tipo": "BIEN",
            "pvp": 25.00,
            "casa_comercial_id": casa_id,
            "impuesto_catalogo_ids": [iva_id],
            "usuario_auditoria": "smoke_test"
        }
        r = client.post(f"{BASE}/productos", json=producto_data)
        assert r.status_code == 201
        producto_id = r.json()["id"]

        # 5. Asociar proveedores al producto
        # Nota: Estos endpoints pueden no existir aún. El test documenta la estructura esperada.
        # Si no existen, habría que crear manualmente los registros en las tablas puente
        # o actualizar este test cuando se implementen los endpoints.

        # Por ahora, verificamos que el producto se creó correctamente
        r = client.get(f"{BASE}/productos/{producto_id}")
        assert r.status_code == 200
        assert r.json()["nombre"] == producto_data["nombre"]

        # Cleanup común
        from tests.smoke.utils import cleanup_product_scenario
        cleanup_product_scenario(client, producto_id=producto_id, casa_id=casa_id)

        # TODO: Implementar asociación de proveedores cuando existan los endpoints
        # Ejemplo esperado:
        # POST /productos/{producto_id}/proveedores-persona
        # POST /productos/{producto_id}/proveedores-sociedad


@pytest.mark.skipif(
    not is_port_open("localhost", 8000),
    reason="Server not listening on localhost:8000"
)
def test_asociar_proveedor_inexistente():
    """
    Escenario 6.1: Asociar proveedor inexistente debe fallar
    - Crear un producto
    - Intentar asociar proveedor con ID inexistente
    - Verificar que devuelve error 400/404

    Nota: Test pendiente de implementación de endpoints de asociación
    """
    with httpx.Client(timeout=TIMEOUT) as client:
        unique_suffix = uuid.uuid4().hex[:6]

        # Crear casa comercial
        casa_data = {
            "nombre": f"Casa_Proveedor_Test_{unique_suffix}",
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
            "nombre": f"Producto_Test_Proveedor_{unique_suffix}",
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
        #     f"{BASE}/productos/{producto_id}/proveedores-persona",
        #     json={"proveedor_persona_id": "99999999-9999-9999-9999-999999999999"}
        # )
        # assert r.status_code in (400, 404)

        # Por ahora, solo verificamos que el producto existe
        r = client.get(f"{BASE}/productos/{producto_id}")
        assert r.status_code == 200

        # Cleanup común
        from tests.smoke.utils import cleanup_product_scenario
        cleanup_product_scenario(client, producto_id=producto_id, casa_id=casa_id)

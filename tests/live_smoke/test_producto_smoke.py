import uuid
import pytest
import httpx
import socket

BASE = "http://localhost:8000/api/v1"
TIMEOUT = 8.0


def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not is_port_open("localhost", 8000), reason="Server not listening on localhost:8000")
def test_producto_flow_with_leaf_categories_and_relations():
    with httpx.Client(timeout=TIMEOUT) as client:
        # 1) Crear jerarquía de categorías: Tec (padre) -> Computadoras (padre) -> Laptop (hoja)
        padre_tec = {
            "nombre": f"Tec-{uuid.uuid4().hex[:6]}",
            "es_padre": True,
            "parent_id": None,
            "usuario_auditoria": "ci",
        }
        r = client.post(f"{BASE}/categorias", json=padre_tec)
        assert r.status_code == 201, r.text
        tec_id = r.json()["id"]

        padre_comp = {
            "nombre": f"Comp-{uuid.uuid4().hex[:6]}",
            "es_padre": True,
            "parent_id": tec_id,
            "usuario_auditoria": "ci",
        }
        r = client.post(f"{BASE}/categorias", json=padre_comp)
        assert r.status_code == 201, r.text
        comp_id = r.json()["id"]

        hoja_laptop = {
            "nombre": f"Laptop-{uuid.uuid4().hex[:6]}",
            "es_padre": False,
            "parent_id": comp_id,
            "usuario_auditoria": "ci",
        }
        r = client.post(f"{BASE}/categorias", json=hoja_laptop)
        assert r.status_code == 201, r.text
        laptop_id = r.json()["id"]

        # 2) Crear casa comercial
        casa_payload = {"nombre": f"Casa-{uuid.uuid4().hex[:6]}", "usuario_auditoria": "ci"}
        r = client.post(f"{BASE}/casas-comerciales", json=casa_payload)
        assert r.status_code == 201, r.text
        casa_id = r.json()["id"]

        # 3) Crear proveedores (persona y sociedad)
        # Persona base para proveedor persona/sociedad
        from tests.smoke.ruc_utils import generar_ruc_persona_natural, generar_ruc_empresa

        persona_payload = {
            "identificacion": generar_ruc_persona_natural(),
            "tipo_identificacion": "RUC",
            "nombre": "Prov",
            "apellido": "Tester",
            "usuario_auditoria": "ci",
        }
        r = client.post(f"{BASE}/personas", json=persona_payload)
        assert r.status_code == 201, r.text
        persona_id = r.json()["id"]

        provp_payload = {
            "nombre_comercial": f"ProvP-{uuid.uuid4().hex[:6]}",
            "tipo_contribuyente_id": "01",
            "persona_id": persona_id,
            "usuario_auditoria": "ci",
        }
        r = client.post(f"{BASE}/proveedores-persona", json=provp_payload)
        assert r.status_code == 201, r.text
        provp_id = r.json()["id"]

        provs_payload = {
            "ruc": generar_ruc_empresa(),
            "razon_social": f"Prov SA {uuid.uuid4().hex[:6]}",
            "nombre_comercial": f"ProvSA {uuid.uuid4().hex[:6]}",
            "direccion": "Av. Siempre Viva",
            "telefono": "0987654321",
            "email": f"prov{uuid.uuid4().hex[:6]}@example.com",
            "tipo_contribuyente_id": "02",
            "persona_contacto_id": persona_id,
            "usuario_auditoria": "ci",
        }
        # Reintentar en caso de RUC inválido aleatorio
        provs_id = None
        for attempt in range(3):
            r = client.post(f"{BASE}/proveedores-sociedad", json=provs_payload)
            if r.status_code == 201:
                provs_id = r.json()["id"]
                break
            if r.status_code == 400 and "RUC no es válido" in r.text and attempt < 2:
                provs_payload["ruc"] = generar_ruc_empresa()
                continue
            assert r.status_code == 201, r.text

        # 4) Crear atributos
        attr1 = {"nombre": f"Color-{uuid.uuid4().hex[:4]}", "tipo_dato": "string", "usuario_auditoria": "ci"}
        r = client.post(f"{BASE}/atributos", json=attr1)
        assert r.status_code == 201, r.text
        attr1_id = r.json()["id"]

        attr2 = {"nombre": f"Peso-{uuid.uuid4().hex[:4]}", "tipo_dato": "decimal", "usuario_auditoria": "ci"}
        r = client.post(f"{BASE}/atributos", json=attr2)
        assert r.status_code == 201, r.text
        attr2_id = r.json()["id"]

        # Obtener IVA para incluir en productos (obligatorio)
        from tests.smoke.utils import get_or_create_iva_for_tests
        iva_id = get_or_create_iva_for_tests(client)

        # 5) Intentar crear producto con categoría NO hoja (debe fallar)
        prod_bad = {
            "nombre": f"Prod-{uuid.uuid4().hex[:6]}",
            "casa_comercial_id": casa_id,
            "categoria_ids": [comp_id],  # comp_id tiene hijo, no es hoja
            "proveedor_persona_ids": [provp_id],
            "proveedor_sociedad_ids": [provs_id],
            "atributo_ids": [attr1_id, attr2_id],
            "impuesto_catalogo_ids": [iva_id],  # Obligatorio: incluir al menos un IVA
            "usuario_auditoria": "ci",
        }
        r = client.post(f"{BASE}/productos", json=prod_bad)
        assert r.status_code in (400, 422)

        # 6) Crear producto con categoría hoja + relaciones
        prod_ok = {
            "nombre": f"Prod-{uuid.uuid4().hex[:6]}",
            "casa_comercial_id": casa_id,
            "categoria_ids": [laptop_id],
            "proveedor_persona_ids": [provp_id],
            "proveedor_sociedad_ids": [provs_id],
            "atributo_ids": [attr1_id, attr2_id],
            "impuesto_catalogo_ids": [iva_id],  # Obligatorio: incluir al menos un IVA
            "usuario_auditoria": "ci",
            "pvp": 10.99,
        }
        r = client.post(f"{BASE}/productos", json=prod_ok)
        assert r.status_code == 201, r.text
        prod_id = r.json()["id"]
        # Nuevo contrato: casa_comercial es un objeto con nombre
        created = r.json()
        assert created.get("casa_comercial") is not None
        assert created["casa_comercial"].get("nombre") == casa_payload["nombre"]

        # 7) Actualizar cambiando a otra categoría hoja (misma rama): debe permitir
        otra_hoja = {
            "nombre": f"Tablet-{uuid.uuid4().hex[:6]}",
            "es_padre": False,
            "parent_id": comp_id,
            "usuario_auditoria": "ci",
        }
        r = client.post(f"{BASE}/categorias", json=otra_hoja)
        assert r.status_code == 201, r.text
        tablet_id = r.json()["id"]

        up = {
            "categoria_ids": [tablet_id],
            "proveedor_persona_ids": [provp_id],
            "proveedor_sociedad_ids": [provs_id],
            "atributo_ids": [attr1_id],
            "usuario_auditoria": "ci",
        }
        r = client.put(f"{BASE}/productos/{prod_id}", json=up)
        assert r.status_code == 200, r.text

        # 8) Listar productos y verificar que el creado existe
        r = client.get(f"{BASE}/productos?limit=500&offset=0&only_active=true")
        assert r.status_code == 200
        items = r.json().get("items", [])
        assert any(it.get("id") == prod_id for it in items), \
            f"Producto {prod_id} no encontrado. Total items: {len(items)}"

        # Limpieza con utilidad común
        from tests.smoke.utils import cleanup_product_scenario
        cleanup_product_scenario(
            client,
            producto_id=prod_id,
            casa_id=casa_id,
            categoria_ids=[tablet_id, laptop_id, comp_id, tec_id],
            atributo_ids=[attr1_id, attr2_id],
            proveedor_persona_id=provp_id,
            proveedor_sociedad_id=provs_id,
        )

import socket
import pytest
import httpx

BASE = "http://localhost:8000/api/v1"
TIMEOUT = 5.0


def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not is_port_open("localhost", 8000), reason="Server not listening on localhost:8000")
def test_create_category_hierarchy_and_prevent_cycle():
    with httpx.Client(timeout=TIMEOUT) as client:
        # Create root category: Tecnología
        r = client.post(f"{BASE}/categorias", json={"nombre": "Tecnología", "es_padre": True, "parent_id": None, "usuario_auditoria": "ci"})
        assert r.status_code in (201, 409)
        if r.status_code == 201:
            root_id = r.json().get("id")
        else:
            # find existing
            r = client.get(f"{BASE}/categorias?limit=50&offset=0")
            items = r.json().get("items", [])
            root = next((i for i in items if i.get("nombre") == "Tecnología"), None)
            assert root
            root_id = root.get("id")

        # Create mid category: Computadoras (child of Tecnología, also parent of Laptop)
        r = client.post(f"{BASE}/categorias", json={"nombre": "Computadoras", "es_padre": True, "parent_id": root_id, "usuario_auditoria": "ci"})
        assert r.status_code in (201, 409)
        if r.status_code == 201:
            mid_id = r.json().get("id")
        else:
            r = client.get(f"{BASE}/categorias?limit=50&offset=0")
            items = r.json().get("items", [])
            mid = next((i for i in items if i.get("nombre") == "Computadoras"), None)
            assert mid
            mid_id = mid.get("id")

        # Create leaf category: Laptop (child of Computadoras)
        r = client.post(f"{BASE}/categorias", json={"nombre": "Laptop", "es_padre": False, "parent_id": mid_id, "usuario_auditoria": "ci"})
        assert r.status_code in (201, 409)
        if r.status_code == 201:
            leaf_id = r.json().get("id")
        else:
            r = client.get(f"{BASE}/categorias?limit=50&offset=0")
            items = r.json().get("items", [])
            leaf = next((i for i in items if i.get("nombre") == "Laptop"), None)
            assert leaf
            leaf_id = leaf.get("id")

        # Verify relationships
        r = client.get(f"{BASE}/categorias/{mid_id}")
        assert r.status_code == 200
        assert r.json().get("parent_id") == root_id

        r = client.get(f"{BASE}/categorias/{leaf_id}")
        assert r.status_code == 200
        assert r.json().get("parent_id") == mid_id

        # Attempt to create a cycle: make root's parent = leaf -> should fail
        bad_update = {"nombre": "Tecnología", "es_padre": True, "parent_id": leaf_id, "usuario_auditoria": "ci"}
        r = client.put(f"{BASE}/categorias/{root_id}", json=bad_update)
        assert r.status_code == 400
        assert "ciclo" in r.text.lower()

        # Cleanup best-effort
        # delete leaf
        client.delete(f"{BASE}/categorias/{leaf_id}")
        # delete mid
        client.delete(f"{BASE}/categorias/{mid_id}")
        # delete root
        client.delete(f"{BASE}/categorias/{root_id}")

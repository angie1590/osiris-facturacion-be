import httpx
import pytest

BASE = "http://localhost:8000/api/v1"
TIMEOUT = 8.0


def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not is_port_open("localhost", 8000), reason="Server not listening on localhost:8000")
def test_listar_catalogo_impuestos_paginado_ok():
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.get(f"{BASE}/impuestos", params={"limit": 5, "offset": 0})
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data.get("items"), list)
        meta = data.get("meta")
        assert meta is not None
        # Meta debe contener valores enteros correctamente calculados
        assert isinstance(meta.get("total"), int)
        assert isinstance(meta.get("limit"), int)
        assert isinstance(meta.get("offset"), int)
        assert isinstance(meta.get("page"), int)
        assert isinstance(meta.get("page_count"), int)


@pytest.mark.skipif(not is_port_open("localhost", 8000), reason="Server not listening on localhost:8000")
def test_listar_catalogo_impuestos_filtrado_por_tipo_ok():
    with httpx.Client(timeout=TIMEOUT) as client:
        # Filtrar por IVA
        r = client.get(f"{BASE}/impuestos", params={"limit": 50, "offset": 0, "tipo_impuesto": "IVA"})
        assert r.status_code == 200, r.text
        data = r.json()
        items = data.get("items", [])
        assert isinstance(items, list)
        # Todos los items devueltos deben ser del tipo solicitado
        for it in items:
            assert it.get("tipo_impuesto") == "IVA"
        meta = data.get("meta")
        assert meta is not None
        # Meta debe contener valores enteros correctamente calculados
        assert isinstance(meta.get("total"), int)
        assert isinstance(meta.get("limit"), int)
        assert isinstance(meta.get("offset"), int)
        assert isinstance(meta.get("page"), int)
        assert isinstance(meta.get("page_count"), int)

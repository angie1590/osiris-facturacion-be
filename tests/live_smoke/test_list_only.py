import pytest

from tests.smoke.utils import BASE, get_client, is_port_open, wait_for_service, retry_on_exception


@pytest.mark.skipif(not is_port_open("localhost", 8000), reason="Server not listening on localhost:8000")
def test_list_endpoints_simple():
    if not wait_for_service("/docs", timeout=15):
        pytest.skip("server not ready on /docs")

    # decorador de retry para list endpoints
    @retry_on_exception(retries=3, backoff=1.0)
    def list_endpoint(prefix: str):
        return client.get(f"{BASE}/{prefix}?limit=5&offset=0&only_active=true")

    prefixes = [
        "roles",
        "empresas",
        "sucursales",
        "puntos-emision",
        "personas",
        "tipos-cliente",
        "usuarios",
        "clientes",
        "empleados",
        "proveedores-persona",
        "proveedores-sociedad",
    ]

    with get_client() as client:
        for p in prefixes:
            r = list_endpoint(p)  # usa el decorador de retry
            assert r.status_code == 200, f"GET /{p} returned {r.status_code}"
            data = r.json()
            assert "items" in data and "meta" in data

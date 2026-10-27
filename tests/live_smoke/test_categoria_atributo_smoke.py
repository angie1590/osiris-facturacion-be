"""Smoke checks for category-attribute compatibility boundaries without writes."""

import socket
import uuid
from urllib.parse import urlparse

import httpx
import pytest

from tests.live_smoke.config import BASE

TIMEOUT = 10.0
BASE_URL = urlparse(BASE)
SMOKE_HOST = BASE_URL.hostname or "localhost"
SMOKE_PORT = BASE_URL.port or (443 if BASE_URL.scheme == "https" else 80)


def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@pytest.mark.skipif(
    not is_port_open(SMOKE_HOST, SMOKE_PORT),
    reason=f"Server not listening on {SMOKE_HOST}:{SMOKE_PORT}",
)
def test_legacy_category_attribute_writes_are_disabled() -> None:
    with httpx.Client(timeout=TIMEOUT) as client:
        legacy_id = str(uuid.uuid4())
        responses = [
            client.post(f"{BASE}/categorias-atributos", json={}),
            client.put(f"{BASE}/categorias-atributos/{legacy_id}", json={}),
            client.delete(f"{BASE}/categorias-atributos/{legacy_id}"),
        ]
        for response in responses:
            assert response.status_code == 410, response.text
            assert response.json()["code"] == "LEGACY_CATEGORY_ATTRIBUTE_WRITE_DISABLED"


@pytest.mark.skipif(
    not is_port_open(SMOKE_HOST, SMOKE_PORT),
    reason=f"Server not listening on {SMOKE_HOST}:{SMOKE_PORT}",
)
def test_contextual_category_attribute_write_requires_authentication() -> None:
    with httpx.Client(timeout=TIMEOUT) as client:
        response = client.post(
            f"{BASE}/categorias/{uuid.uuid4()}/atributos",
            json={"atributo_id": str(uuid.uuid4())},
        )
    assert response.status_code == 401, response.text
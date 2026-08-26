import socket
import time
import functools
import logging
from typing import Callable
import os

import httpx

BASE = "http://localhost:8000/api/v1"
TIMEOUT = 10.0

# Flag para determinar si hacer hard delete (físico) o soft delete (a través de API)
USE_HARD_DELETE = os.getenv("TEST_HARD_DELETE", "false").lower() == "true"
RUN_LIVE_SMOKE = os.getenv("RUN_LIVE_SMOKE", "false").lower() in {"true", "1", "yes"}


def is_port_open(host: str, port: int) -> bool:
    if not RUN_LIVE_SMOKE:
        return False
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def wait_for_service(path: str = "/docs", timeout: int = 30, interval: float = 0.5) -> bool:
    """Espera hasta que la ruta `http://localhost:8000{path}` responda 200 o hasta agotar `timeout`.
    Devuelve True si el servicio respondió 200 dentro del timeout, False en caso contrario.
    """
    url = f"http://localhost:8000{path}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=2.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def retry_on_exception(retries: int = 3, backoff: float = 0.5):
    def decorator(fn: Callable):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, retries + 1):
                try:
                    response = fn(*args, **kwargs)
                    # si devuelve Response, verificar código exitoso
                    if hasattr(response, "status_code"):
                        if response.status_code < 500:  # 2xx/3xx/4xx son "ok"
                            return response
                        raise Exception(f"HTTP {response.status_code}")
                    return response
                except Exception as exc:
                    last_exc = exc
                    if attempt < retries:  # no dormir en el último intento
                        time.sleep(backoff * attempt)
            # re-raise the last exception
            raise last_exc

        return wrapper

    return decorator


def get_client():
    return httpx.Client(timeout=TIMEOUT)


def hard_delete_from_db(resource: str, resource_id: str) -> None:
    """Elimina físicamente un recurso de la base de datos (hard delete)."""
    from osiris.core.db import engine
    from sqlalchemy import text

    # Mapeo de recursos a tablas
    table_map = {
        "productos": "tbl_producto",
        "atributos": "tbl_atributo",
        "proveedores-persona": "tbl_proveedor_persona",
        "proveedores-sociedad": "tbl_proveedor_sociedad",
        "casas-comerciales": "tbl_casa_comercial",
        "categorias": "tbl_categoria",
        "personas": "tbl_persona",
        "clientes": "tbl_cliente",
        "empleados": "tbl_empleado",
        "usuarios": "tbl_usuario",
        "roles": "tbl_rol",
        "tipos-cliente": "tbl_tipo_cliente",
        "empresas": "tbl_empresa",
        "sucursales": "tbl_sucursal",
        "puntos-emision": "tbl_punto_emision",
    }

    table_name = table_map.get(resource)
    if not table_name:
        logging.warning("No se encontró mapeo para recurso %s, skip hard delete", resource)
        return

    try:
        with engine.begin() as conn:
            result = conn.execute(
                text(f"DELETE FROM {table_name} WHERE id = :id"),
                {"id": resource_id}
            )
            if result.rowcount > 0:
                logging.debug("Hard delete %s/%s: %d registros eliminados", resource, resource_id, result.rowcount)
    except Exception as exc:
        logging.warning("Hard delete %s/%s failed: %s", resource, resource_id, exc)


def safe_delete(client: httpx.Client, resource: str, resource_id: str) -> None:
    """Elimina un recurso ignorando 404/204 diferencias.
    resource: segmento del endpoint, ej: "productos".

    Si USE_HARD_DELETE=true, hace eliminación física de la BD.
    Si no, usa el endpoint DELETE (soft delete).
    """
    if USE_HARD_DELETE:
        hard_delete_from_db(resource, resource_id)
        return

    try:
        r = client.delete(f"{BASE}/{resource}/{resource_id}")
        if r.status_code not in (204, 404):
            logging.warning("DELETE %s/%s -> %s %s", resource, resource_id, r.status_code, r.text)
    except Exception as exc:
        logging.warning("DELETE %s/%s failed: %s", resource, resource_id, exc)


def cleanup_product_relations(producto_id: str) -> None:
    """Elimina las relaciones de un producto antes de eliminarlo (solo para hard delete)."""
    if not USE_HARD_DELETE:
        return

    from osiris.core.db import engine
    from sqlalchemy import text

    try:
        with engine.begin() as conn:
            # Eliminar relaciones producto-categoria
            conn.execute(
                text("DELETE FROM tbl_producto_categoria WHERE producto_id = :id"),
                {"id": producto_id}
            )
            # Eliminar relaciones producto-proveedor persona
            conn.execute(
                text("DELETE FROM tbl_producto_proveedor_persona WHERE producto_id = :id"),
                {"id": producto_id}
            )
            # Eliminar relaciones producto-proveedor sociedad
            conn.execute(
                text("DELETE FROM tbl_producto_proveedor_sociedad WHERE producto_id = :id"),
                {"id": producto_id}
            )
            # Eliminar producto-impuesto
            conn.execute(
                text("DELETE FROM tbl_producto_impuesto WHERE producto_id = :id"),
                {"id": producto_id}
            )
    except Exception as exc:
        logging.warning("Error eliminando relaciones de producto %s: %s", producto_id, exc)


def cleanup_product_scenario(
    client: httpx.Client,
    *,
    producto_id: str | None = None,
    casa_id: str | None = None,
    categoria_ids: list[str] | None = None,
    atributo_ids: list[str] | None = None,
    proveedor_persona_id: str | None = None,
    proveedor_sociedad_id: str | None = None,
) -> None:
    """Limpia entidades típicas creadas en smoke alrededor de Producto.
    Elimina en orden seguro: producto -> atributos -> proveedores -> casa -> categorías (hoja→padre→raíz).

    Si USE_HARD_DELETE=true (env TEST_HARD_DELETE=true), hace eliminación física de la BD.
    """
    if producto_id:
        # Si es hard delete, eliminar primero las relaciones
        if USE_HARD_DELETE:
            cleanup_product_relations(producto_id)
        safe_delete(client, "productos", producto_id)
    if atributo_ids:
        for aid in atributo_ids:
            safe_delete(client, "atributos", aid)
    if proveedor_persona_id:
        safe_delete(client, "proveedores-persona", proveedor_persona_id)
    if proveedor_sociedad_id:
        safe_delete(client, "proveedores-sociedad", proveedor_sociedad_id)
    if casa_id:
        safe_delete(client, "casas-comerciales", casa_id)
    if categoria_ids:
        # eliminar en orden provisto (idealmente hoja → padre → raíz)
        for cid in categoria_ids:
            safe_delete(client, "categorias", cid)


def get_or_create_iva_for_tests(client: httpx.Client) -> str:
    """Busca un IVA activo (código '2') via API HTTP.
    Retorna el ID del impuesto IVA para usar en tests.
    Si no encuentra ninguno, asume que hay uno con ID conocido del seed.
    """
    # Buscar IVA existente via API
    try:
        r = client.get(f"{BASE}/impuestos?tipo_impuesto=IVA&solo_vigentes=true&limit=50&offset=0")
        if r.status_code == 200:
            data = r.json()
            items = data.get("items", [])
            # Buscar uno con codigo_sri '2' (IVA)
            for item in items:
                if item.get("codigo_sri") == "2":
                    return str(item["id"])
            # Si no hay con código '2', tomar el primero disponible
            if items:
                return str(items[0]["id"])
    except Exception as exc:
        logging.warning(f"Error buscando IVA via API: {exc}")

    # Fallback: asumir un UUID conocido del seed o lanzar error
    raise RuntimeError("No se pudo encontrar un IVA activo. Ejecutar 'make seed' primero.")

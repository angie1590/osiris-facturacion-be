from __future__ import annotations

import argparse
import json
import os
import secrets
import tempfile
from datetime import timedelta
from importlib import import_module
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy import create_engine
from sqlmodel import Session, col, select

from osiris.core.auth import create_token
from osiris.core.db import engine
from osiris.modules.common.rol.entity import Rol
from osiris.modules.common.usuario.entity import Usuario
from osiris.utils.validacion_identificacion import ValidacionCedulaRucService


BASE = "http://127.0.0.1:8003/api/v1"


def request(method, path, token=None, body=None, form=False):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
        data = (urlencode(body) if form else json.dumps(body)).encode()
    try:
        with urlopen(Request(BASE + path, data=data, headers=headers, method=method), timeout=30) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except HTTPError as error:
        raise RuntimeError(f"HTTP {error.code}: {method} {path.split('?')[0]}") from None


def save(path, facts):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as output:
        json.dump(facts, output)
    os.chmod(path, 0o600)


def cleanup(path):
    facts = json.loads(path.read_text())
    pending = []
    order = ["proveedores-sociedad", "empleados", "clientes", "proveedores-persona", "usuarios", "roles-modulos-permisos", "tipos-cliente", "roles", "personas"]
    actor_ids = {facts["actor"]["id"], facts["actor"]["persona_id"]} if facts.get("actor") else set()
    entries = [entry for entry in facts["created"] if entry["id"] not in actor_ids]
    for resource in order:
        for entry in reversed(entries):
            if entry["resource"] != resource:
                continue
            try:
                token = facts["originToken"]
                try:
                    current = request("GET", f"/{resource}/{entry['id']}", token)
                except RuntimeError as error:
                    if not str(error).startswith("HTTP 404:"):
                        raise
                    inactive = request("GET", f"/{resource}?only_active=false&estado=inactivo&limit=1000", token)
                    if any(item["id"] == entry["id"] and not item["activo"] for item in inactive["items"]):
                        continue
                    raise
                if current["activo"]:
                    request("DELETE", f"/{resource}/{entry['id']}", token)
            except RuntimeError as error:
                pending.append({**entry, "error": str(error)})
    if facts.get("actor"):
        for resource, identifier in [("usuarios", facts["actor"]["id"]), ("personas", facts["actor"]["persona_id"])]:
            try:
                current = request("GET", f"/{resource}/{identifier}", facts["originToken"])
                if current["activo"]:
                    request("DELETE", f"/{resource}/{identifier}", facts["originToken"])
            except RuntimeError as error:
                pending.append({"resource": resource, "id": identifier, "error": str(error)})
    facts["cleanup_pending"] = pending
    save(path, facts)
    print(json.dumps({"cleanup_pending_count": len(pending), "journal": str(path)}))


def setup():
    import_module("osiris.main")
    local = create_engine(engine.url.set(host="127.0.0.1", port=5435), echo=False)
    with Session(local) as session:
        admin = session.exec(select(Usuario).join(Rol, Usuario.rol_id == Rol.id).where(col(Usuario.activo).is_(True), col(Rol.activo).is_(True), Rol.nombre == "Administrador")).first()
        if not admin:
            raise RuntimeError("No active Administrador exists")
        origin_token = create_token(admin.id, "access", timedelta(hours=3))
        role_id = str(admin.rol_id)
    local.dispose()
    folder = Path(tempfile.mkdtemp(prefix="osiris-directory-uat-"))
    os.chmod(folder, 0o700)
    path = folder / "fixture.json"
    suffix = secrets.token_hex(5)
    facts = {"originToken": origin_token, "created": [], "suffix": suffix, "base": BASE}
    save(path, facts)
    try:
        password = secrets.token_urlsafe(24)
        actor = request("POST", "/usuarios", origin_token, {"username": f"uat_admin_{suffix}", "password": password, "rol_id": role_id, "persona_nueva": {"tipo_identificacion": "PASAPORTE", "identificacion": f"UATADMIN{suffix}", "nombre": "UAT", "apellido": f"Admin{suffix}"}})
        facts["actor"] = actor
        facts["created"].extend([{"resource": "usuarios", "id": actor["id"]}, {"resource": "personas", "id": actor["persona_id"]}])
        save(path, facts)
        login = request("POST", "/auth/login", body={"username": actor["username"], "password": password}, form=True)
        if login.get("require_password_change"):
            replacement = secrets.token_urlsafe(24)
            request("POST", "/auth/change-password", login["access_token"], {"current_password": password, "new_password": replacement})
            password = replacement
            login = request("POST", "/auth/login", body={"username": actor["username"], "password": password}, form=True)
        facts.update(login)
        facts["password"] = password
        facts["role_id"] = role_id
        token = login["access_token"]
        facts["companies"] = request("GET", "/empresas?only_active=true&limit=100", token)["items"]
        facts["roles"] = request("GET", "/roles?only_active=true&limit=100", token)["items"]
        types = request("GET", "/tipos-cliente?only_active=true&limit=100", token)["items"]
        if not types:
            catalog = request("POST", "/tipos-cliente", token, {"nombre": f"UAT {suffix}", "descuento": "0"})
            types = [catalog]
            facts["created"].append({"resource": "tipos-cliente", "id": catalog["id"]})
        facts["customer_types"] = types
        facts["tax_types"] = request("GET", "/tipos-contribuyente", token)
        facts["contract"] = request("GET", "/personas/contrato", token)
        facts["natural_rucs"] = []
        facts["society_rucs"] = []
        for kind, validator, resource in [("natural", ValidacionCedulaRucService.es_ruc_persona_natural_valido, "personas"), ("society", ValidacionCedulaRucService.es_ruc_sociedad_privada_valido, "proveedores-sociedad")]:
            while len(facts[f"{kind}_rucs"]) < 4:
                prefix = "17" + ("1" if kind == "natural" else "9") + f"{secrets.randbelow(1000000):06d}"
                candidate = next((prefix + str(digit) + "001" for digit in range(10) if validator(prefix + str(digit) + "001")), None)
                if not candidate or candidate in facts[f"{kind}_rucs"]:
                    continue
                existing = request("GET", f"/{resource}?only_active=false&q={candidate}&limit=100", token)
                if not existing["items"]:
                    facts[f"{kind}_rucs"].append(candidate)
        save(path, facts)
        print(json.dumps({"fixture": str(path), "actor_created": True, "companies": len(facts["companies"]), "customer_types": len(types), "natural_rucs": 4, "society_rucs": 4}))
    except Exception:
        save(path, facts)
        cleanup(path)
        raise RuntimeError("Fixture setup failed; inspect restricted journal") from None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cleanup", type=Path)
    arguments = parser.parse_args()
    if arguments.cleanup:
        cleanup(arguments.cleanup)
    else:
        setup()
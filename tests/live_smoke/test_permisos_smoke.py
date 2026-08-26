# tests/smoke/test_permisos_smoke.py
import pytest
import httpx

from tests.smoke.utils import is_port_open


client = httpx.Client(base_url="http://localhost:8000", timeout=10.0)


@pytest.mark.skipif(not is_port_open("localhost", 8000), reason="Server not listening on localhost:8000")
def test_permisos_crud_completo():
    """Test smoke del flujo CRUD completo de permisos."""

    # 1. Crear rol
    import uuid
    suf = uuid.uuid4().hex[:6]
    rol_data = {
        "nombre": f"Rol Smoke Permisos {suf}",
        "descripcion": "Rol para test smoke de permisos",
        "usuario_auditoria": "smoke_test"
    }
    response = client.post("/api/v1/roles", json=rol_data)
    assert response.status_code in (201, 409)
    rol_id = response.json().get("id") if response.status_code == 409 else response.json()["id"]

    # 2. Crear módulo
    modulo_data = {
        "codigo": f"SMOKE_PERM_MOD_{suf}",
        "nombre": "Módulo Smoke Permisos",
        "usuario_auditoria": "smoke_test"
    }
    response = client.post("/api/v1/modulos", json=modulo_data)
    assert response.status_code == 201
    modulo_id = response.json()["id"]

    # 3. Crear permiso
    permiso_data = {
        "rol_id": rol_id,
        "modulo_id": modulo_id,
        "puede_leer": True,
        "puede_crear": True,
        "puede_actualizar": False,
        "puede_eliminar": False,
        "usuario_auditoria": "smoke_test"
    }

    response = client.post("/api/v1/roles-modulos-permisos", json=permiso_data)
    assert response.status_code == 201
    permiso_creado = response.json()
    permiso_id = permiso_creado["id"]

    assert permiso_creado["rol_id"] == rol_id
    assert permiso_creado["modulo_id"] == modulo_id
    assert permiso_creado["puede_leer"] is True
    assert permiso_creado["puede_crear"] is True
    assert permiso_creado["puede_actualizar"] is False

    # 4. Listar permisos
    response = client.get("/api/v1/roles-modulos-permisos")
    assert response.status_code == 200
    data = response.json()
    if isinstance(data, dict) and "meta" in data and "items" in data:
        assert data["meta"]["total"] >= 1
        data["items"]
    else:
        assert isinstance(data, list)

    # 5. Obtener permiso por ID
    response = client.get(f"/api/v1/roles-modulos-permisos/{permiso_id}")
    assert response.status_code == 200
    permiso = response.json()
    assert permiso["rol_id"] == rol_id

    # 6. Actualizar permiso
    update_data = {
        "puede_actualizar": True,
        "puede_eliminar": True,
        "usuario_auditoria": "smoke_test"
    }

    response = client.put(f"/api/v1/roles-modulos-permisos/{permiso_id}", json=update_data)
    assert response.status_code == 200
    permiso_actualizado = response.json()
    assert permiso_actualizado["puede_actualizar"] is True
    assert permiso_actualizado["puede_eliminar"] is True
    assert permiso_actualizado["puede_leer"] is True  # No cambia

    # 7. Eliminar permiso
    response = client.delete(f"/api/v1/roles-modulos-permisos/{permiso_id}")
    assert response.status_code in (200, 204)

    # Limpiar
    client.delete(f"/api/v1/modulos/{modulo_id}")
    client.delete(f"/api/v1/roles/{rol_id}")


@pytest.mark.skipif(not is_port_open("localhost", 8000), reason="Server not listening on localhost:8000")
def test_obtener_permisos_usuario():
    """Test obtener permisos de un usuario."""
    import os as _os
    _os.environ["DISABLE_ID_VALIDATION"] = "true"

    # Nota: Para estos tests de permisos, la creación de empresa no es requerida
    empresa_id = None

    # Crear rol con nombre único
    import uuid as _uuid_rol_perms
    suf_rol_perms = _uuid_rol_perms.uuid4().hex[:6]
    rol_nombre = f"Rol Usuario Permisos Test {suf_rol_perms}"
    rol_data = {
        "nombre": rol_nombre,
        "usuario_auditoria": "smoke_test"
    }
    response = client.post("/api/v1/roles", json=rol_data)
    assert response.status_code in (201, 409)
    if response.status_code == 201:
        rol_id = response.json()["id"]
    else:
        # Buscar el rol por nombre - obtener más registros para evitar paginación
        response = client.get("/api/v1/roles?limit=100")
        roles_data = response.json()
        if isinstance(roles_data, dict) and "items" in roles_data:
            roles = roles_data["items"]
        else:
            roles = roles_data
        rol = next((r for r in roles if r["nombre"] == rol_nombre), None)
        assert rol is not None, f"No se encontró el rol '{rol_nombre}' en {len(roles)} roles"
        rol_id = rol["id"]

    # Crear módulos
    suf_mods = __import__("uuid").uuid4().hex[:6]
    modulo1_codigo = f"PERM_USER_MOD1_{suf_mods}"
    modulo1_data = {
        "codigo": modulo1_codigo,
        "nombre": "Módulo 1",
        "usuario_auditoria": "smoke_test"
    }
    response = client.post("/api/v1/modulos", json=modulo1_data)
    assert response.status_code == 201
    modulo1_id = response.json()["id"]

    modulo2_codigo = f"PERM_USER_MOD2_{suf_mods}"
    modulo2_data = {
        "codigo": modulo2_codigo,
        "nombre": "Módulo 2",
        "usuario_auditoria": "smoke_test"
    }
    response = client.post("/api/v1/modulos", json=modulo2_data)
    assert response.status_code == 201
    modulo2_id = response.json()["id"]

    # Crear permisos para el rol
    permiso1_data = {
        "rol_id": rol_id,
        "modulo_id": modulo1_id,
        "puede_leer": True,
        "puede_crear": True,
        "usuario_auditoria": "smoke_test"
    }
    response = client.post("/api/v1/roles-modulos-permisos", json=permiso1_data)
    assert response.status_code == 201
    permiso1_id = response.json()["id"]

    permiso2_data = {
        "rol_id": rol_id,
        "modulo_id": modulo2_id,
        "puede_leer": True,
        "puede_crear": False,
        "usuario_auditoria": "smoke_test"
    }
    response = client.post("/api/v1/roles-modulos-permisos", json=permiso2_data)
    assert response.status_code == 201
    permiso2_id = response.json()["id"]

    # Crear persona con identificación única válida
    from tests.smoke.ruc_utils import generar_ruc_persona_natural
    cedula_valida = generar_ruc_persona_natural()[:10]  # Solo los primeros 10 dígitos (cédula)
    persona_data = {
        "identificacion": cedula_valida,
        "tipo_identificacion": "CEDULA",
        "nombre": "Test",
        "apellido": "Permisos Usuario",
        "usuario_auditoria": "smoke_test"
    }
    response = client.post("/api/v1/personas", json=persona_data)
    assert response.status_code == 201
    persona_id = response.json()["id"]

    # Crear usuario
    import uuid as _uuid1
    suf_user = _uuid1.uuid4().hex[:6]
    usuario_data = {
        "persona_id": persona_id,
        "rol_id": rol_id,
        "username": f"test_permisos_smoke_{suf_user}",
        "password": "TestPassword123!",
        "usuario_auditoria": "smoke_test"
    }
    response = client.post("/api/v1/usuarios", json=usuario_data)
    if response.status_code == 409:
        # Usuario ya existe para esta persona, obtenerlo
        response_usuarios = client.get("/api/v1/usuarios")
        usuarios_data = response_usuarios.json()
        usuarios_list = usuarios_data.get("items", usuarios_data) if isinstance(usuarios_data, dict) else usuarios_data
        usuario_existente = next((u for u in usuarios_list if u.get("persona_id") == persona_id), None)
        if usuario_existente:
            usuario_id = usuario_existente["id"]
        else:
            raise Exception(f"Usuario con persona_id {persona_id} no encontrado tras 409")
    else:
        assert response.status_code == 201
        usuario_id = response.json()["id"]

    # Obtener permisos del usuario
    response = client.get(f"/api/v1/usuarios/{usuario_id}/permisos")
    assert response.status_code == 200
    permisos = response.json()

    # Verificar estructura de respuesta
    assert isinstance(permisos, list)
    assert len(permisos) >= 2

    # Buscar permisos de los módulos creados
    perm_mod1 = next((p for p in permisos if p["codigo"] == modulo1_codigo), None)
    assert perm_mod1 is not None
    assert perm_mod1["puede_leer"] is True
    assert perm_mod1["puede_crear"] is True

    perm_mod2 = next((p for p in permisos if p["codigo"] == modulo2_codigo), None)
    assert perm_mod2 is not None
    assert perm_mod2["puede_leer"] is True
    assert perm_mod2["puede_crear"] is False

    # Limpiar
    client.delete(f"/api/v1/usuarios/{usuario_id}")
    client.delete(f"/api/v1/personas/{persona_id}")
    client.delete(f"/api/v1/roles-modulos-permisos/{permiso1_id}")
    client.delete(f"/api/v1/roles-modulos-permisos/{permiso2_id}")
    client.delete(f"/api/v1/modulos/{modulo1_id}")
    client.delete(f"/api/v1/modulos/{modulo2_id}")
    client.delete(f"/api/v1/roles/{rol_id}")
    if empresa_id:
        client.delete(f"/api/v1/empresas/{empresa_id}")


@pytest.mark.skipif(not is_port_open("localhost", 8000), reason="Server not listening on localhost:8000")
def test_obtener_menu_usuario():
    """Test obtener menú dinámico de usuario."""
    import os as _os
    _os.environ["DISABLE_ID_VALIDATION"] = "true"

    # Nota: No es necesario crear empresa para menú de usuario
    empresa_id = None

    # Crear rol con nombre único
    import uuid as _uuid_rol_menu
    suf_rol_menu = _uuid_rol_menu.uuid4().hex[:6]
    rol_nombre = f"Rol Menu Test {suf_rol_menu}"
    rol_data = {
        "nombre": rol_nombre,
        "usuario_auditoria": "smoke_test"
    }
    response = client.post("/api/v1/roles", json=rol_data)
    assert response.status_code in (201, 409)
    if response.status_code == 201:
        rol_id = response.json()["id"]
    else:
        # Buscar el rol por nombre - obtener más registros para evitar paginación
        response = client.get("/api/v1/roles?limit=100")
        roles_data = response.json()
        if isinstance(roles_data, dict) and "items" in roles_data:
            roles = roles_data["items"]
        else:
            roles = roles_data
        rol = next((r for r in roles if r["nombre"] == rol_nombre), None)
        assert rol is not None, f"No se encontró el rol '{rol_nombre}' en {len(roles)} roles"
        rol_id = rol["id"]

    # Crear módulos
    suf_menu = __import__("uuid").uuid4().hex[:6]
    modulo_visible_codigo = f"MENU_VISIBLE_{suf_menu}"
    modulo_visible = {
        "codigo": modulo_visible_codigo,
        "nombre": "Módulo Visible",
        "usuario_auditoria": "smoke_test"
    }
    response = client.post("/api/v1/modulos", json=modulo_visible)
    assert response.status_code == 201
    modulo_visible_id = response.json()["id"]

    modulo_oculto_codigo = f"MENU_OCULTO_{suf_menu}"
    modulo_oculto = {
        "codigo": modulo_oculto_codigo,
        "nombre": "Módulo Oculto",
        "usuario_auditoria": "smoke_test"
    }
    response = client.post("/api/v1/modulos", json=modulo_oculto)
    assert response.status_code == 201
    modulo_oculto_id = response.json()["id"]

    # Dar permiso de lectura solo al módulo visible
    permiso_visible = {
        "rol_id": rol_id,
        "modulo_id": modulo_visible_id,
        "puede_leer": True,
        "usuario_auditoria": "smoke_test"
    }
    response = client.post("/api/v1/roles-modulos-permisos", json=permiso_visible)
    assert response.status_code == 201
    permiso_visible_id = response.json()["id"]

    permiso_oculto = {
        "rol_id": rol_id,
        "modulo_id": modulo_oculto_id,
        "puede_leer": False,
        "puede_crear": True,  # Tiene otros permisos pero no lectura
        "usuario_auditoria": "smoke_test"
    }
    response = client.post("/api/v1/roles-modulos-permisos", json=permiso_oculto)
    assert response.status_code == 201
    permiso_oculto_id = response.json()["id"]

    # Crear persona y usuario con identificación única válida
    from tests.smoke.ruc_utils import generar_ruc_persona_natural
    cedula_valida2 = generar_ruc_persona_natural()[:10]  # Solo los primeros 10 dígitos (cédula)
    persona_data = {
        "identificacion": cedula_valida2,
        "tipo_identificacion": "CEDULA",
        "nombre": "Test",
        "apellido": "Menu",
        "usuario_auditoria": "smoke_test"
    }
    response = client.post("/api/v1/personas", json=persona_data)
    assert response.status_code == 201
    persona_id = response.json()["id"]

    import uuid as _uuid2
    suf_user2 = _uuid2.uuid4().hex[:6]
    usuario_data = {
        "persona_id": persona_id,
        "rol_id": rol_id,
        "username": f"test_menu_smoke_{suf_user2}",
        "password": "TestPassword123!",
        "usuario_auditoria": "smoke_test"
    }
    response = client.post("/api/v1/usuarios", json=usuario_data)
    if response.status_code == 409:
        # Usuario ya existe para esta persona, obtenerlo
        response_usuarios = client.get("/api/v1/usuarios")
        usuarios_data = response_usuarios.json()
        usuarios_list = usuarios_data.get("items", usuarios_data) if isinstance(usuarios_data, dict) else usuarios_data
        usuario_existente = next((u for u in usuarios_list if u.get("persona_id") == persona_id), None)
        if usuario_existente:
            usuario_id = usuario_existente["id"]
        else:
            raise Exception(f"Usuario con persona_id {persona_id} no encontrado tras 409")
    else:
        assert response.status_code == 201
        usuario_id = response.json()["id"]

    # Obtener menú
    response = client.get(f"/api/v1/usuarios/{usuario_id}/menu")
    assert response.status_code == 200
    menu = response.json()

    # Verificar que solo aparece el módulo con puede_leer=True
    codigos_menu = [m["codigo"] for m in menu]
    assert modulo_visible_codigo in codigos_menu
    assert modulo_oculto_codigo not in codigos_menu

    # Limpiar
    client.delete(f"/api/v1/usuarios/{usuario_id}")
    client.delete(f"/api/v1/personas/{persona_id}")
    client.delete(f"/api/v1/roles-modulos-permisos/{permiso_visible_id}")
    client.delete(f"/api/v1/roles-modulos-permisos/{permiso_oculto_id}")
    client.delete(f"/api/v1/modulos/{modulo_visible_id}")
    client.delete(f"/api/v1/modulos/{modulo_oculto_id}")
    client.delete(f"/api/v1/roles/{rol_id}")
    if empresa_id:
        client.delete(f"/api/v1/empresas/{empresa_id}")

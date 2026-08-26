#!/usr/bin/env python3
"""
Script para poblar la base de datos con datos de prueba completos.
Lee la estructura desde seed_data_structure.yaml y crea todos los registros.

Uso:
    ENVIRONMENT=development python scripts/seed_complete_data.py
"""

import sys
import json
import subprocess
from pathlib import Path
from datetime import date
from decimal import Decimal
from uuid import UUID
from sqlmodel import Session, select

try:
    import yaml
except ModuleNotFoundError:
    yaml = None

# Añadir src al path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from osiris.core.db import engine
from osiris.modules.common.persona.entity import Persona
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.common.punto_emision.entity import PuntoEmision
from osiris.modules.inventario.bodega.entity import Bodega
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.atributo.entity import Atributo, TipoDato
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.common.proveedor_persona.entity import ProveedorPersona
from osiris.modules.common.proveedor_sociedad.entity import ProveedorSociedad
from osiris.modules.inventario.producto.entity import Producto, ProductoCategoria, ProductoProveedorPersona, ProductoProveedorSociedad, ProductoImpuesto, ProductoBodega
from osiris.modules.inventario.producto.models_atributos import ProductoAtributoValor
from osiris.modules.sri.impuesto_catalogo.entity import ImpuestoCatalogo
from osiris.modules.sri.tipo_contribuyente.entity import TipoContribuyente  # noqa: F401
from osiris.modules.common.usuario.entity import Usuario
from osiris.modules.common.rol.entity import Rol
from osiris.modules.common.empleado.entity import Empleado
from osiris.modules.common.modulo.entity import Modulo
from osiris.modules.common.rol_modulo_permiso.entity import RolModuloPermiso
from osiris.core.security import hash_password


AUDIT_USER = "seed_script"


def load_yaml_structure():
    """Carga la estructura de datos desde el archivo YAML."""
    yaml_path = Path(__file__).parent / "seed_data_structure.yaml"
    if yaml is not None:
        with open(yaml_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    # Fallback sin dependencia PyYAML: parsea YAML usando Ruby stdlib (Psych)
    # y lo convierte a JSON para consumirlo en Python.
    cmd = [
        "ruby",
        "-ryaml",
        "-rjson",
        "-e",
        "puts JSON.generate(YAML.safe_load(File.read(ARGV[0]), aliases: true))",
        str(yaml_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            "No se pudo cargar seed_data_structure.yaml "
            "ni con PyYAML ni con fallback Ruby.\n"
            f"stderr: {result.stderr}"
        )
    return json.loads(result.stdout)


def _safe_default_by_tipo(tipo_dato: TipoDato | str | None) -> str | None:
    tipo = tipo_dato.value if hasattr(tipo_dato, "value") else str(tipo_dato).lower() if tipo_dato else None
    if tipo == TipoDato.STRING.value:
        return "N/A"
    if tipo == TipoDato.INTEGER.value:
        return "0"
    if tipo == TipoDato.DECIMAL.value:
        return "0.00"
    if tipo == TipoDato.BOOLEAN.value:
        return "false"
    if tipo == TipoDato.DATE.value:
        return date.today().isoformat()
    return None


def _parse_bool(value) -> bool:
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "t", "yes", "y", "si", "s"}:
        return True
    if normalized in {"false", "0", "f", "no", "n"}:
        return False
    raise ValueError(f"Valor booleano invalido: {value}")


def _build_eav_value_columns(tipo_dato: TipoDato | str, raw_value) -> dict:
    tipo = tipo_dato.value if hasattr(tipo_dato, "value") else str(tipo_dato).lower()
    values = {
        "valor_string": None,
        "valor_integer": None,
        "valor_decimal": None,
        "valor_boolean": None,
        "valor_date": None,
    }
    if tipo == TipoDato.STRING.value:
        values["valor_string"] = str(raw_value)
    elif tipo == TipoDato.INTEGER.value:
        values["valor_integer"] = int(raw_value)
    elif tipo == TipoDato.DECIMAL.value:
        values["valor_decimal"] = Decimal(str(raw_value))
    elif tipo == TipoDato.BOOLEAN.value:
        values["valor_boolean"] = _parse_bool(raw_value)
    elif tipo == TipoDato.DATE.value:
        if isinstance(raw_value, date):
            values["valor_date"] = raw_value
        else:
            values["valor_date"] = date.fromisoformat(str(raw_value))
    else:
        raise ValueError(f"Tipo de dato no soportado: {tipo_dato}")
    return values


def crear_persona(session: Session, data: dict) -> Persona:
    """Crea o recupera una persona."""
    stmt = select(Persona).where(Persona.identificacion == data["identificacion"])
    persona = session.exec(stmt).first()

    if persona:
        print(f"  ✓ Persona ya existe: {data['identificacion']}")
        return persona

    persona = Persona(
        identificacion=data["identificacion"],
        tipo_identificacion=data["tipo_identificacion"],
        nombre=data.get("nombre", data.get("nombres", "")),
        apellido=data.get("apellido", data.get("apellidos", "")),
        email=data.get("email"),
        telefono=data.get("telefono"),
        usuario_auditoria=AUDIT_USER
    )
    session.add(persona)
    session.commit()
    session.refresh(persona)
    print(f"  ✓ Persona creada: {data['identificacion']}")
    return persona


def crear_empresa(session: Session, data: dict, persona_id: UUID) -> Empresa:
    """Crea la empresa."""
    stmt = select(Empresa).where(Empresa.ruc == data["ruc"])
    empresa = session.exec(stmt).first()

    if empresa:
        print(f"  ✓ Empresa ya existe: {data['nombre_comercial']}")
        return empresa

    empresa = Empresa(
        nombre_comercial=data["nombre_comercial"],
        razon_social=data["razon_social"],
        ruc=data["ruc"],
        direccion_matriz=data["direccion"],
        telefono=data["telefono"],
        logo=data.get("logo"),
        tipo_contribuyente_id=data.get("tipo_contribuyente_id", "01"),
        usuario_auditoria=AUDIT_USER
    )
    session.add(empresa)
    session.commit()
    session.refresh(empresa)
    print(f"  ✓ Empresa creada: {data['nombre_comercial']}")
    return empresa


def crear_sucursales(session: Session, sucursales_data: list, empresa_id: UUID) -> dict:
    """Crea las sucursales y retorna un mapa código -> id."""
    sucursales_map = {}

    for suc_data in sucursales_data:
        stmt = select(Sucursal).where(
            Sucursal.empresa_id == empresa_id,
            Sucursal.codigo == suc_data["codigo"]
        )
        sucursal = session.exec(stmt).first()

        if not sucursal:
            es_matriz = bool(suc_data.get("es_matriz", False))
            if "es_matriz" not in suc_data:
                es_matriz = suc_data["codigo"] == "001"
            sucursal = Sucursal(
                codigo=suc_data["codigo"],
                nombre=suc_data["nombre"],
                direccion=suc_data["direccion"],
                telefono=suc_data.get("telefono"),
                es_matriz=es_matriz,
                empresa_id=empresa_id,
                usuario_auditoria=AUDIT_USER
            )
            session.add(sucursal)
            session.commit()
            session.refresh(sucursal)
            print(f"  ✓ Sucursal creada: {suc_data['codigo']} - {suc_data['nombre']}")
        else:
            print(f"  ✓ Sucursal ya existe: {suc_data['codigo']}")

        sucursales_map[suc_data["codigo"]] = sucursal.id

    return sucursales_map


def crear_puntos_emision(session: Session, puntos_data: list, empresa_id: UUID, sucursales_map: dict):
    """Crea los puntos de emisión."""
    _ = empresa_id
    for punto_data in puntos_data:
        sucursal_codigo = punto_data.get("sucursal") or "001"
        sucursal_id = sucursales_map.get(sucursal_codigo)
        if sucursal_id is None:
            raise ValueError(f"Sucursal '{sucursal_codigo}' no encontrada para punto de emisión {punto_data['codigo']}.")

        stmt = select(PuntoEmision).where(
            PuntoEmision.codigo == punto_data["codigo"],
            PuntoEmision.sucursal_id == sucursal_id
        )
        punto = session.exec(stmt).first()

        if not punto:
            punto = PuntoEmision(
                codigo=punto_data["codigo"],
                descripcion=punto_data["descripcion"],
                sucursal_id=sucursal_id,
                usuario_auditoria=AUDIT_USER
            )
            session.add(punto)
            session.commit()
            print(f"  ✓ Punto de emisión creado: {punto_data['codigo']} - {punto_data['descripcion']}")
        else:
            print(f"  ✓ Punto de emisión ya existe: {punto_data['codigo']}")


def crear_bodegas(session: Session, bodegas_data: list, empresa_id: UUID, sucursales_map: dict) -> dict:
    """Crea las bodegas y retorna un mapa código -> id."""
    bodegas_map = {}

    for bod_data in bodegas_data:
        sucursal_id = sucursales_map.get(bod_data["sucursal"]) if bod_data["sucursal"] else None

        stmt = select(Bodega).where(
            Bodega.empresa_id == empresa_id,
            Bodega.codigo_bodega == bod_data["codigo_bodega"]
        )
        bodega = session.exec(stmt).first()

        if not bodega:
            bodega = Bodega(
                codigo_bodega=bod_data["codigo_bodega"],
                nombre_bodega=bod_data["nombre_bodega"],
                descripcion=bod_data.get("descripcion"),
                empresa_id=empresa_id,
                sucursal_id=sucursal_id,
                usuario_auditoria=AUDIT_USER
            )
            session.add(bodega)
            session.commit()
            session.refresh(bodega)
            print(f"  ✓ Bodega creada: {bod_data['codigo_bodega']} - {bod_data['nombre_bodega']}")
        else:
            print(f"  ✓ Bodega ya existe: {bod_data['codigo_bodega']}")

        bodegas_map[bod_data["codigo_bodega"]] = bodega.id

    return bodegas_map


def crear_categorias_recursivo(session: Session, cat_data: dict, parent_id: UUID = None, categorias_map: dict = None) -> UUID:
    """Crea categorías recursivamente y retorna su ID."""
    if categorias_map is None:
        categorias_map = {}

    # Buscar si ya existe
    stmt = select(Categoria).where(Categoria.nombre == cat_data["nombre"])
    categoria = session.exec(stmt).first()

    if not categoria:
        categoria = Categoria(
            nombre=cat_data["nombre"],
            es_padre=cat_data["es_padre"],
            parent_id=parent_id,
            usuario_auditoria=AUDIT_USER
        )
        session.add(categoria)
        session.commit()
        session.refresh(categoria)
        nivel = "padre" if cat_data["es_padre"] else "hoja"
        print(f"  ✓ Categoría creada ({nivel}): {cat_data['nombre']}")
    else:
        print(f"  ✓ Categoría ya existe: {cat_data['nombre']}")

    categorias_map[cat_data["nombre"]] = categoria.id

    # Procesar hijos si existen
    if "hijos" in cat_data:
        for hijo in cat_data["hijos"]:
            crear_categorias_recursivo(session, hijo, categoria.id, categorias_map)

    return categoria.id


def crear_atributos(session: Session, atributos_data: list, categorias_map: dict) -> dict:
    """Crea atributos y sus relaciones con categorías."""
    atributos_map = {}

    for idx, atr_data in enumerate(atributos_data, start=1):
        # Crear atributo
        stmt = select(Atributo).where(Atributo.nombre == atr_data["nombre"])
        atributo = session.exec(stmt).first()

        if not atributo:
            atributo = Atributo(
                nombre=atr_data["nombre"],
                tipo_dato=atr_data["tipo_dato"],
                usuario_auditoria=AUDIT_USER
            )
            session.add(atributo)
            session.commit()
            session.refresh(atributo)
            print(f"  ✓ Atributo creado: {atr_data['nombre']} ({atr_data['tipo_dato']})")
        else:
            print(f"  ✓ Atributo ya existe: {atr_data['nombre']}")

        atributos_map[atr_data["nombre"]] = atributo.id

        # Asignar a categoría si se especifica
        if "nivel_asignacion" in atr_data:
            categoria_id = categorias_map.get(atr_data["nivel_asignacion"])
            if categoria_id:
                obligatorio = bool(atr_data.get("obligatorio", False))
                valor_default = atr_data.get("valor_default")
                if obligatorio and (valor_default is None or str(valor_default).strip() == ""):
                    valor_default = _safe_default_by_tipo(atributo.tipo_dato)

                stmt = select(CategoriaAtributo).where(
                    CategoriaAtributo.categoria_id == categoria_id,
                    CategoriaAtributo.atributo_id == atributo.id
                )
                cat_atr = session.exec(stmt).first()
                if not cat_atr:
                    cat_atr = CategoriaAtributo(
                        categoria_id=categoria_id,
                        atributo_id=atributo.id,
                        orden=int(atr_data.get("orden", idx)),
                        obligatorio=obligatorio,
                        valor_default=valor_default,
                        usuario_auditoria=AUDIT_USER
                    )
                    session.add(cat_atr)
                    session.commit()
                    print(f"    → Atributo asignado a categoría: {atr_data['nivel_asignacion']}")
                else:
                    updated = False
                    if cat_atr.orden is None:
                        cat_atr.orden = int(atr_data.get("orden", idx))
                        updated = True
                    if cat_atr.obligatorio is None and obligatorio:
                        cat_atr.obligatorio = True
                        updated = True
                    if (cat_atr.valor_default is None or str(cat_atr.valor_default).strip() == "") and valor_default:
                        cat_atr.valor_default = valor_default
                        updated = True
                    if updated:
                        cat_atr.usuario_auditoria = AUDIT_USER
                        session.add(cat_atr)
                        session.commit()
                        print(f"    → Atributo actualizado en categoría: {atr_data['nivel_asignacion']}")

    return atributos_map


def crear_casas_comerciales(session: Session, casas_data: list) -> dict:
    """Crea casas comerciales."""
    casas_map = {}

    for casa_data in casas_data:
        stmt = select(CasaComercial).where(CasaComercial.nombre == casa_data["nombre"])
        casa = session.exec(stmt).first()

        if not casa:
            casa = CasaComercial(
                nombre=casa_data["nombre"],
                usuario_auditoria=AUDIT_USER
            )
            session.add(casa)
            session.commit()
            session.refresh(casa)
            print(f"  ✓ Casa comercial creada: {casa_data['nombre']}")
        else:
            print(f"  ✓ Casa comercial ya existe: {casa_data['nombre']}")

        casas_map[casa_data["nombre"]] = casa.id

    return casas_map


def crear_proveedores_persona(session: Session, proveedores_data: list) -> dict:
    """Crea proveedores persona."""
    proveedores_map = {}

    for prov_data in proveedores_data:
        persona = crear_persona(session, prov_data["persona"])

        stmt = select(ProveedorPersona).where(ProveedorPersona.persona_id == persona.id)
        proveedor = session.exec(stmt).first()

        if not proveedor:
            proveedor = ProveedorPersona(
                nombre_comercial=prov_data["proveedor"]["nombre_comercial"],
                tipo_contribuyente_id=prov_data["proveedor"]["tipo_contribuyente_id"],
                persona_id=persona.id,
                usuario_auditoria=AUDIT_USER
            )
            session.add(proveedor)
            session.commit()
            session.refresh(proveedor)
            print(f"  ✓ Proveedor persona creado: {prov_data['proveedor']['nombre_comercial']}")
        else:
            print(f"  ✓ Proveedor persona ya existe: {prov_data['proveedor']['nombre_comercial']}")

        proveedores_map[prov_data["persona"]["identificacion"]] = proveedor.id

    return proveedores_map


def crear_proveedores_sociedad(session: Session, proveedores_data: list, personas_cache: dict) -> dict:
    """Crea proveedores sociedad."""
    proveedores_map = {}

    for prov_data in proveedores_data:
        stmt = select(ProveedorSociedad).where(ProveedorSociedad.ruc == prov_data["ruc"])
        proveedor = session.exec(stmt).first()

        if not proveedor:
            # Buscar persona de contacto
            persona_contacto_stmt = select(Persona).where(
                Persona.identificacion == prov_data["persona_contacto"]
            )
            persona_contacto = session.exec(persona_contacto_stmt).first()

            if not persona_contacto:
                print(f"  ⚠ Persona de contacto no encontrada: {prov_data['persona_contacto']}")
                continue

            proveedor = ProveedorSociedad(
                ruc=prov_data["ruc"],
                razon_social=prov_data["razon_social"],
                nombre_comercial=prov_data["nombre_comercial"],
                direccion=prov_data["direccion"],
                telefono=prov_data["telefono"],
                email=prov_data["email"],
                tipo_contribuyente_id=prov_data["tipo_contribuyente_id"],
                persona_contacto_id=persona_contacto.id,
                usuario_auditoria=AUDIT_USER
            )
            session.add(proveedor)
            session.commit()
            session.refresh(proveedor)
            print(f"  ✓ Proveedor sociedad creado: {prov_data['nombre_comercial']}")
        else:
            print(f"  ✓ Proveedor sociedad ya existe: {prov_data['nombre_comercial']}")

        proveedores_map[prov_data["ruc"]] = proveedor.id

    return proveedores_map


def obtener_impuestos(session: Session) -> dict:
    """Obtiene los impuestos del catálogo por código_sri."""
    stmt = select(ImpuestoCatalogo).where(ImpuestoCatalogo.activo.is_(True))
    impuestos = session.exec(stmt).all()

    impuestos_map = {}
    for impuesto in impuestos:
        impuestos_map[impuesto.codigo_sri] = impuesto.id

    print(f"  ✓ Cargados {len(impuestos_map)} impuestos del catálogo")
    return impuestos_map


def crear_productos(session: Session, productos_data: list, categorias_map: dict, casas_map: dict,
                    proveedores_persona_map: dict, proveedores_sociedad_map: dict,
                    atributos_map: dict, impuestos_map: dict, bodegas_map: dict):
    """Crea productos con todas sus relaciones."""

    for prod_data in productos_data:
        # Verificar si el producto ya existe
        stmt = select(Producto).where(Producto.nombre == prod_data["nombre"])
        producto = session.exec(stmt).first()

        if producto:
            print(f"  ✓ Producto ya existe: {prod_data['nombre']}")
            continue

        # Obtener casa comercial
        casa_id = casas_map.get(prod_data.get("casa_comercial"))

        # Crear producto
        producto = Producto(
            nombre=prod_data["nombre"],
            descripcion=prod_data.get("descripcion"),
            codigo_barras=prod_data.get("codigo_barras"),
            tipo=prod_data.get("tipo", "BIEN"),
            pvp=Decimal(str(prod_data["precio"])),
            casa_comercial_id=casa_id,
            usuario_auditoria=AUDIT_USER
        )
        session.add(producto)
        session.commit()
        session.refresh(producto)
        print(f"  ✓ Producto creado: {prod_data['nombre']} (${prod_data['precio']})")

        # Asignar categoría (solo hojas)
        categoria_id = categorias_map.get(prod_data["categoria"])
        if categoria_id:
            prod_cat = ProductoCategoria(
                producto_id=producto.id,
                categoria_id=categoria_id
            )
            session.add(prod_cat)
            print(f"    → Categoría: {prod_data['categoria']}")

        # Asignar impuestos
        if "impuestos" in prod_data:
            for codigo_sri in prod_data["impuestos"]:
                impuesto_id = impuestos_map.get(codigo_sri)
                if impuesto_id:
                    prod_imp = ProductoImpuesto(
                        producto_id=producto.id,
                        impuesto_catalogo_id=impuesto_id,
                        usuario_auditoria=AUDIT_USER
                    )
                    session.add(prod_imp)
                    print(f"    → Impuesto: {codigo_sri}")

        # Asignar proveedores
        if "proveedores" in prod_data:
            for prov_ref in prod_data["proveedores"]:
                # Intentar como RUC de sociedad
                if prov_ref in proveedores_sociedad_map:
                    prod_prov = ProductoProveedorSociedad(
                        producto_id=producto.id,
                        proveedor_sociedad_id=proveedores_sociedad_map[prov_ref]
                    )
                    session.add(prod_prov)
                    print(f"    → Proveedor sociedad: {prov_ref}")
                # Intentar como identificación de persona
                elif prov_ref in proveedores_persona_map:
                    prod_prov = ProductoProveedorPersona(
                        producto_id=producto.id,
                        proveedor_persona_id=proveedores_persona_map[prov_ref]
                    )
                    session.add(prod_prov)
                    print(f"    → Proveedor persona: {prov_ref}")

        # Persistir atributos tipados del producto en tabla EAV.
        if "atributos" in prod_data:
            creados = 0
            for atributo_nombre, atributo_valor in prod_data["atributos"].items():
                atributo_id = atributos_map.get(atributo_nombre)
                if not atributo_id:
                    print(f"    ⚠ Atributo no definido en catalogo: {atributo_nombre}")
                    continue

                atributo_master = session.get(Atributo, atributo_id)
                if not atributo_master:
                    print(f"    ⚠ Atributo no encontrado en DB: {atributo_nombre}")
                    continue

                try:
                    typed_values = _build_eav_value_columns(atributo_master.tipo_dato, atributo_valor)
                except Exception as exc:
                    print(f"    ⚠ No se pudo convertir atributo '{atributo_nombre}' ({atributo_valor}): {exc}")
                    continue

                existing = session.exec(
                    select(ProductoAtributoValor).where(
                        ProductoAtributoValor.producto_id == producto.id,
                        ProductoAtributoValor.atributo_id == atributo_id,
                    )
                ).first()
                if existing:
                    existing.valor_string = typed_values["valor_string"]
                    existing.valor_integer = typed_values["valor_integer"]
                    existing.valor_decimal = typed_values["valor_decimal"]
                    existing.valor_boolean = typed_values["valor_boolean"]
                    existing.valor_date = typed_values["valor_date"]
                    existing.usuario_auditoria = AUDIT_USER
                    session.add(existing)
                else:
                    session.add(
                        ProductoAtributoValor(
                            producto_id=producto.id,
                            atributo_id=atributo_id,
                            usuario_auditoria=AUDIT_USER,
                            **typed_values,
                        )
                    )
                creados += 1
            print(f"    → Atributos EAV persistidos: {creados}")

        # Asignar a bodegas con cantidades
        if "bodegas" in prod_data:
            for bodega_codigo, cantidad in prod_data["bodegas"].items():
                bodega_id = bodegas_map.get(bodega_codigo)
                if bodega_id:
                    prod_bod = ProductoBodega(
                        producto_id=producto.id,
                        bodega_id=bodega_id,
                        cantidad=cantidad
                    )
                    session.add(prod_bod)
                    print(f"    → Bodega: {bodega_codigo} ({cantidad} unidades)")

        session.commit()


def crear_roles(session: Session, roles_data: list) -> dict:
    """Crea roles y retorna un mapa {nombre: id}."""
    roles_map = {}

    for rol_data in roles_data:
        stmt = select(Rol).where(Rol.nombre == rol_data["nombre"])
        rol = session.exec(stmt).first()

        if rol:
            print(f"  ✓ Rol ya existe: {rol_data['nombre']}")
            roles_map[rol_data["nombre"]] = rol.id
            continue

        rol = Rol(
            nombre=rol_data["nombre"],
            descripcion=rol_data.get("descripcion", ""),
            usuario_auditoria=AUDIT_USER
        )
        session.add(rol)
        session.commit()
        session.refresh(rol)
        roles_map[rol_data["nombre"]] = rol.id
        print(f"  ✓ Rol creado: {rol_data['nombre']}")

    return roles_map


def crear_modulos(session: Session, modulos_data: list) -> dict:
    """Crea módulos del sistema y retorna un mapa {codigo: id}."""

    modulos_map = {}

    for mod_data in modulos_data:
        stmt = select(Modulo).where(Modulo.codigo == mod_data["codigo"])
        modulo = session.exec(stmt).first()

        if modulo:
            print(f"  ✓ Módulo ya existe: {mod_data['codigo']}")
            modulos_map[mod_data["codigo"]] = modulo.id
            continue

        modulo = Modulo(
            codigo=mod_data["codigo"],
            nombre=mod_data["nombre"],
            descripcion=mod_data.get("descripcion"),
            orden=mod_data.get("orden"),
            icono=mod_data.get("icono"),
            usuario_auditoria=AUDIT_USER
        )
        session.add(modulo)
        session.commit()
        session.refresh(modulo)
        modulos_map[mod_data["codigo"]] = modulo.id
        print(f"  ✓ Módulo creado: {mod_data['codigo']} - {mod_data['nombre']}")

    return modulos_map


def crear_permisos(session: Session, permisos_data: list, roles_map: dict, modulos_map: dict):
    """Crea permisos asociando roles con módulos."""

    for perm_data in permisos_data:
        rol_nombre = perm_data["rol"]
        modulo_codigo = perm_data["modulo"]

        rol_id = roles_map.get(rol_nombre)
        modulo_id = modulos_map.get(modulo_codigo)

        if not rol_id or not modulo_id:
            print(f"  ⚠ Permiso omitido: rol '{rol_nombre}' o módulo '{modulo_codigo}' no encontrado")
            continue

        # Verificar si ya existe el permiso
        stmt = select(RolModuloPermiso).where(
            RolModuloPermiso.rol_id == rol_id,
            RolModuloPermiso.modulo_id == modulo_id
        )
        permiso = session.exec(stmt).first()

        if permiso:
            print(f"  ✓ Permiso ya existe: {rol_nombre} -> {modulo_codigo}")
            continue

        permiso = RolModuloPermiso(
            rol_id=rol_id,
            modulo_id=modulo_id,
            puede_leer=perm_data.get("puede_leer", False),
            puede_crear=perm_data.get("puede_crear", False),
            puede_actualizar=perm_data.get("puede_actualizar", False),
            puede_eliminar=perm_data.get("puede_eliminar", False),
            usuario_auditoria=AUDIT_USER
        )
        session.add(permiso)
        session.commit()
        print(f"  ✓ Permiso creado: {rol_nombre} -> {modulo_codigo}")


def crear_empleados(session: Session, empleados_data: list, empresa_id: UUID, roles_map: dict):
    """Crea empleados con sus usuarios."""
    for emp_data in empleados_data:
        # Crear o recuperar persona
        persona_data = emp_data["persona"]
        persona = crear_persona(session, persona_data)

        # Verificar si ya existe empleado para esta persona
        stmt = select(Empleado).where(Empleado.persona_id == persona.id)
        empleado = session.exec(stmt).first()

        if empleado:
            print(f"  ✓ Empleado ya existe: {persona.nombre} {persona.apellido}")
            continue

        # Obtener rol_id
        rol_nombre = emp_data["empleado"]["usuario"]["rol"]
        rol_id = roles_map.get(rol_nombre)
        if not rol_id:
            print(f"  ✗ Rol no encontrado: {rol_nombre}")
            continue

        # Crear usuario primero
        usuario_data = emp_data["empleado"]["usuario"]
        stmt = select(Usuario).where(Usuario.username == usuario_data["username"])
        usuario = session.exec(stmt).first()

        if not usuario:
            password_hash = hash_password(usuario_data["password"])
            usuario = Usuario(
                persona_id=persona.id,
                username=usuario_data["username"],
                password_hash=password_hash,
                rol_id=rol_id,
                activo=True,
                usuario_auditoria=AUDIT_USER
            )
            session.add(usuario)
            session.commit()
            session.refresh(usuario)
            print(f"    → Usuario creado: {usuario_data['username']}")

        # Crear empleado
        empleado = Empleado(
            persona_id=persona.id,
            empresa_id=empresa_id,
            salario=Decimal(str(emp_data["empleado"]["salario"])),
            fecha_ingreso=emp_data["empleado"]["fecha_ingreso"],
            fecha_nacimiento=emp_data["empleado"].get("fecha_nacimiento"),
            usuario_auditoria=AUDIT_USER
        )
        session.add(empleado)
        session.commit()
        session.refresh(empleado)
        print(f"  ✓ Empleado creado: {persona.nombre} {persona.apellido} - {rol_nombre}")


def main():
    """Función principal."""
    print("=" * 80)
    print("SEED DE DATOS COMPLETO - OSIRIS")
    print("=" * 80)

    # Cargar estructura
    print("\n1. Cargando estructura de datos desde YAML...")
    data = load_yaml_structure()
    print("  ✓ Estructura cargada")

    with Session(engine) as session:
        # 2. Persona empresa
        print("\n2. Creando persona base para empresa...")
        persona_empresa = crear_persona(session, data["persona_empresa"])

        # 3. Empresa
        print("\n3. Creando empresa...")
        empresa = crear_empresa(session, data["empresa"], persona_empresa.id)

        # 4. Sucursales
        print("\n4. Creando sucursales...")
        sucursales_map = crear_sucursales(session, data["sucursales"], empresa.id)

        # 5. Puntos de emisión
        print("\n5. Creando puntos de emisión...")
        crear_puntos_emision(session, data["puntos_emision"], empresa.id, sucursales_map)

        # 6. Bodegas
        print("\n6. Creando bodegas...")
        bodegas_map = crear_bodegas(session, data["bodegas"], empresa.id, sucursales_map)

        # 7. Categorías
        print("\n7. Creando jerarquía de categorías...")
        categorias_map = {}
        for categoria in data["categorias"]:
            crear_categorias_recursivo(session, categoria, None, categorias_map)

        # 8. Atributos
        print("\n8. Creando atributos...")
        atributos_map = crear_atributos(session, data["atributos"], categorias_map)

        # 9. Casas comerciales
        print("\n9. Creando casas comerciales...")
        casas_map = crear_casas_comerciales(session, data["casas_comerciales"])

        # 10. Proveedores persona
        print("\n10. Creando proveedores persona...")
        proveedores_persona_map = crear_proveedores_persona(session, data["proveedores_persona"])

        # 11. Proveedores sociedad
        print("\n11. Creando proveedores sociedad...")
        proveedores_sociedad_map = crear_proveedores_sociedad(session, data["proveedores_sociedad"], {})

        # 12. Obtener impuestos
        print("\n12. Cargando impuestos del catálogo...")
        impuestos_map = obtener_impuestos(session)

        # 13. Productos
        print("\n13. Creando productos con todas sus relaciones...")
        crear_productos(
            session,
            data["productos"],
            categorias_map,
            casas_map,
            proveedores_persona_map,
            proveedores_sociedad_map,
            atributos_map,
            impuestos_map,
            bodegas_map
        )

        # 14. Roles
        print("\n14. Creando roles...")
        roles_map = crear_roles(session, data.get("roles", []))

        # 15. Módulos
        print("\n15. Creando módulos del sistema...")
        modulos_map = crear_modulos(session, data.get("modulos", []))

        # 16. Permisos
        print("\n16. Creando permisos por rol y módulo...")
        crear_permisos(session, data.get("permisos", []), roles_map, modulos_map)

        # 17. Empleados
        if "empleados" in data and data["empleados"]:
            print("\n17. Creando empleados...")
            crear_empleados(session, data["empleados"], empresa.id, roles_map)

        print("\n" + "=" * 80)
        print("✓ SEED COMPLETADO EXITOSAMENTE")
        print("=" * 80)
        print("\nResumen:")
        print("  - Empresa: 1 (OpenLatina)")
        print(f"  - Sucursales: {len(sucursales_map)}")
        print(f"  - Puntos de emisión: {len(data['puntos_emision'])}")
        print(f"  - Bodegas: {len(bodegas_map)}")
        print(f"  - Categorías: {len(categorias_map)}")
        print(f"  - Atributos: {len(atributos_map)}")
        print(f"  - Casas comerciales: {len(casas_map)}")
        print(f"  - Proveedores persona: {len(proveedores_persona_map)}")
        print(f"  - Proveedores sociedad: {len(proveedores_sociedad_map)}")
        print(f"  - Productos: {len(data['productos'])}")
        print(f"  - Roles: {len(roles_map)}")
        print(f"  - Módulos: {len(modulos_map)}")
        print(f"  - Permisos: {len(data.get('permisos', []))}")
        print(f"  - Empleados: {len(data.get('empleados', []))}")
        print()


if __name__ == "__main__":
    main()

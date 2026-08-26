from __future__ import annotations

from datetime import date
from pathlib import Path
import json
from decimal import Decimal

from sqlmodel import Session, select

from osiris.core.db import engine
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.common.persona.entity import Persona
from osiris.modules.common.proveedor_persona.entity import ProveedorPersona
from osiris.modules.common.proveedor_sociedad.entity import ProveedorSociedad
from osiris.modules.inventario.atributo.entity import Atributo
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.inventario.producto.entity import (
    Producto,
    ProductoCategoria,
    ProductoProveedorPersona,
    ProductoProveedorSociedad,
)
from osiris.modules.sri.impuesto_catalogo.entity import (
    ImpuestoCatalogo,
    TipoImpuesto,
    AplicaA,
    ClasificacionIVA,
    ModoCalculoICE,
    UnidadBase,
)
from osiris.modules.sri.tipo_contribuyente.entity import TipoContribuyente
from osiris.modules.inventario.producto.service import ProductoService
from osiris.modules.inventario.producto.models import ProductoCreate

USUARIO = "seed"

# Datos de entrada (pueden personalizarse)
RUC_PERSONAS = [
    "0104815956001",
    "0103523908001",
]
RUC_PERSONAS_EXTRA = ["0102637063001", "0102522778001"]  # disponibles si se quieren más

RUC_SOCIEDADES = [
    "0990828237001",
    "0990005419001",
]
RUC_SOCIEDADES_EXTRA = ["1791148800001", "1792128218001"]


def get_or_create(session: Session, model, defaults: dict, **filters):
    obj = session.exec(select(model).filter_by(**filters)).first()
    if obj:
        return obj, False
    obj = model(**{**filters, **defaults})
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj, True


def seed():
    with Session(engine) as session:
        # Casa comercial
        casa, _ = get_or_create(session, CasaComercial, {"nombre": "Casa ACME", "usuario_auditoria": USUARIO}, nombre="Casa ACME")

        # Catálogo tipo contribuyente (01 Persona Natural, 02 Sociedad)
        get_or_create(session, TipoContribuyente, {"nombre": "Persona Natural", "descripcion": "Persona natural", "activo": True}, codigo="01")
        get_or_create(session, TipoContribuyente, {"nombre": "Sociedad", "descripcion": "Sociedad", "activo": True}, codigo="02")

        # Categorías (Tecnología > Computadoras > Laptop)
        tech, _ = get_or_create(session, Categoria, {"es_padre": True, "parent_id": None, "usuario_auditoria": USUARIO}, nombre="Tecnología")
        comp, _ = get_or_create(session, Categoria, {"es_padre": True, "parent_id": tech.id, "usuario_auditoria": USUARIO}, nombre="Computadoras")
        laptop, _ = get_or_create(session, Categoria, {"es_padre": False, "parent_id": comp.id, "usuario_auditoria": USUARIO}, nombre="Laptop")

        # Personas y proveedores persona
        proveedores_persona_ids = []
        persona_data = [
            (RUC_PERSONAS[0], "Juan", "Gómez", "Juan Gómez Importaciones"),
            (RUC_PERSONAS[1], "Pepe", "Pérez", "Tecnologías Pepe"),
        ]
        for identificacion, nombre, apellido, nombre_comercial in persona_data:
            persona, _ = get_or_create(
                session,
                Persona,
                {
                    "tipo_identificacion": "RUC",
                    "nombre": nombre,
                    "apellido": apellido,
                    "usuario_auditoria": USUARIO,
                },
                identificacion=identificacion,
            )
            proveedor, _ = get_or_create(
                session,
                ProveedorPersona,
                {
                    "tipo_contribuyente_id": "01",  # Persona natural
                    "persona_id": persona.id,
                    "nombre_comercial": nombre_comercial,
                    "usuario_auditoria": USUARIO,
                },
                persona_id=persona.id,
            )
            proveedores_persona_ids.append(proveedor.id)

        # Proveedores sociedad (usar la primera persona como contacto)
        contacto_persona = session.exec(select(Persona).filter(Persona.identificacion == RUC_PERSONAS[0])).first()
        proveedores_sociedad_ids = []
        sociedades_data = [
            (RUC_SOCIEDADES[0], "Tipti S.A.", "Tipti"),
            (RUC_SOCIEDADES[1], "ABC Comercial S.A.", "ABC Comercial"),
        ]
        for ruc, razon_social, nombre_comercial in sociedades_data:
            prov_soc, _ = get_or_create(
                session,
                ProveedorSociedad,
                {
                    "razon_social": razon_social,
                    "nombre_comercial": nombre_comercial,
                    "direccion": "Av. Principal 123",
                    "telefono": "0999999999",
                    "email": f"{nombre_comercial.lower().replace(' ', '_')}@example.com",
                    "tipo_contribuyente_id": "02",  # Sociedad
                    "persona_contacto_id": contacto_persona.id,
                    "usuario_auditoria": USUARIO,
                },
                ruc=ruc,
            )
            proveedores_sociedad_ids.append(prov_soc.id)

        # Atributos
        atributos_data = [
            ("color_principal", "string", "negro"),
            ("memoria_ram", "string", "32GB"),
            ("tamano_pantalla", "decimal", "15.6"),
        ]
        atributo_ids = []
        for nombre, tipo_dato, valor in atributos_data:
            atributo, _ = get_or_create(
                session,
                Atributo,
                {"tipo_dato": tipo_dato, "usuario_auditoria": USUARIO},
                nombre=nombre,
            )
            atributo_ids.append((atributo.id, valor))

        # Asignar atributos por categoría (herencia):
        # - Computadoras: color_principal, memoria_ram
        # - Laptop: tamano_pantalla
        # Evitar duplicados si ya existen
        def ensure_cat_attr(cat_id, attr_id):
            exists = session.exec(
                select(CategoriaAtributo).where(
                    CategoriaAtributo.categoria_id == cat_id,
                    CategoriaAtributo.atributo_id == attr_id,
                )
            ).first()
            if not exists:
                session.add(CategoriaAtributo(categoria_id=cat_id, atributo_id=attr_id, usuario_auditoria=USUARIO))

        # Mapear por nombre para legibilidad
        nombre_to_id = {session.get(Atributo, aid).nombre: aid for aid, _ in atributo_ids}
        if "color_principal" in nombre_to_id:
            ensure_cat_attr(comp.id, nombre_to_id["color_principal"])
        if "memoria_ram" in nombre_to_id:
            ensure_cat_attr(comp.id, nombre_to_id["memoria_ram"])
        if "tamano_pantalla" in nombre_to_id:
            ensure_cat_attr(laptop.id, nombre_to_id["tamano_pantalla"])
        session.commit()

        # Asegurar catálogo SRI cargado (si falta, cargar desde conf/aux_impuesto_catalogo.json)
        def ensure_impuesto_catalogo_loaded() -> None:
            iva_check = session.exec(
                select(ImpuestoCatalogo).where(
                    ImpuestoCatalogo.codigo_sri == "4",
                    ImpuestoCatalogo.tipo_impuesto == TipoImpuesto.IVA,
                )
            ).first()
            ice_check = session.exec(
                select(ImpuestoCatalogo).where(
                    ImpuestoCatalogo.codigo_sri == "3011",
                    ImpuestoCatalogo.tipo_impuesto == TipoImpuesto.ICE,
                )
            ).first()
            if iva_check and ice_check:
                return

            catalog_path = Path("conf/aux_impuesto_catalogo.json")
            if not catalog_path.exists():
                raise RuntimeError("No se encontró conf/aux_impuesto_catalogo.json para cargar el catálogo SRI.")

            # Normalizaciones conocidas
            modo_map = {"ESPECIFICA": "ESPECIFICO", "MIXTA": "MIXTO"}

            with catalog_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            for item in data:
                try:
                    tipo_impuesto = TipoImpuesto(item["tipo_impuesto"])  # IVA/ICE/IRBPNR
                except Exception:
                    # Saltar registros desconocidos
                    continue

                codigo_tipo_impuesto = str(item.get("codigo_tipo_impuesto", "")).strip()
                codigo_sri = str(item.get("codigo_sri", "")).strip()
                descripcion = str(item.get("descripcion", "")).strip()
                if not codigo_sri or not descripcion:
                    continue

                aplica_a_val = item.get("aplica_a") or "AMBOS"
                try:
                    aplica_a = AplicaA(aplica_a_val)
                except Exception:
                    aplica_a = AplicaA.AMBOS

                # Fechas por defecto: vigente_desde 2023-02-01 si falta
                vd_raw = item.get("vigente_desde")
                if vd_raw:
                    try:
                        yyyy, mm, dd = map(int, str(vd_raw).split("-")[:3])
                        vigente_desde = date(yyyy, mm, dd)
                    except Exception:
                        vigente_desde = date(2023, 2, 1)
                else:
                    vigente_desde = date(2023, 2, 1)

                vh_raw = item.get("vigente_hasta")
                vigente_hasta = None
                if vh_raw:
                    try:
                        yyyy, mm, dd = map(int, str(vh_raw).split("-")[:3])
                        vigente_hasta = date(yyyy, mm, dd)
                    except Exception:
                        vigente_hasta = None

                porcentaje_iva = item.get("porcentaje_iva")
                tarifa_ad_valorem = item.get("tarifa_ad_valorem")
                tarifa_especifica = item.get("tarifa_especifica")

                clasificacion_iva = item.get("clasificacion_iva")
                clasificacion_iva = clasificacion_iva if clasificacion_iva else None
                if clasificacion_iva:
                    try:
                        clasificacion_iva = ClasificacionIVA(clasificacion_iva)
                    except Exception:
                        clasificacion_iva = None

                modo_calculo_ice = item.get("modo_calculo_ice")
                if modo_calculo_ice:
                    modo_calculo_ice = modo_map.get(modo_calculo_ice, modo_calculo_ice)
                    try:
                        modo_calculo_ice = ModoCalculoICE(modo_calculo_ice)
                    except Exception:
                        modo_calculo_ice = None
                else:
                    modo_calculo_ice = None

                unidad_base = item.get("unidad_base")
                if not unidad_base or unidad_base == "VALOR":
                    unidad_base = "UNIDAD"
                try:
                    unidad_base_enum = UnidadBase(unidad_base)
                except Exception:
                    unidad_base_enum = None

                # Upsert por (codigo_sri, descripcion)
                existente = session.exec(
                    select(ImpuestoCatalogo).where(
                        ImpuestoCatalogo.codigo_sri == codigo_sri,
                        ImpuestoCatalogo.descripcion == descripcion,
                    )
                ).first()
                if existente:
                    existente.tipo_impuesto = tipo_impuesto
                    existente.codigo_tipo_impuesto = codigo_tipo_impuesto
                    existente.vigente_desde = vigente_desde
                    existente.vigente_hasta = vigente_hasta
                    existente.aplica_a = aplica_a
                    existente.porcentaje_iva = Decimal(str(porcentaje_iva)) if porcentaje_iva is not None else None
                    existente.clasificacion_iva = clasificacion_iva
                    existente.tarifa_ad_valorem = Decimal(str(tarifa_ad_valorem)) if tarifa_ad_valorem is not None else None
                    existente.tarifa_especifica = Decimal(str(tarifa_especifica)) if tarifa_especifica is not None else None
                    existente.modo_calculo_ice = modo_calculo_ice
                    existente.unidad_base = unidad_base_enum
                else:
                    session.add(
                        ImpuestoCatalogo(
                            tipo_impuesto=tipo_impuesto,
                            codigo_tipo_impuesto=codigo_tipo_impuesto,
                            codigo_sri=codigo_sri,
                            descripcion=descripcion,
                            vigente_desde=vigente_desde,
                            vigente_hasta=vigente_hasta,
                            aplica_a=aplica_a,
                            porcentaje_iva=Decimal(str(porcentaje_iva)) if porcentaje_iva is not None else None,
                            clasificacion_iva=clasificacion_iva,
                            tarifa_ad_valorem=Decimal(str(tarifa_ad_valorem)) if tarifa_ad_valorem is not None else None,
                            tarifa_especifica=Decimal(str(tarifa_especifica)) if tarifa_especifica is not None else None,
                            modo_calculo_ice=modo_calculo_ice,
                            unidad_base=unidad_base_enum,
                            usuario_auditoria=USUARIO,
                        )
                    )
            session.commit()

        ensure_impuesto_catalogo_loaded()

        # Obtener impuestos del catálogo SRI ya insertados
        # IVA 15% (codigo_sri="4")
        iva = session.exec(
            select(ImpuestoCatalogo).where(
                ImpuestoCatalogo.codigo_sri == "4",
                ImpuestoCatalogo.tipo_impuesto == TipoImpuesto.IVA
            )
        ).first()
        if not iva:
            raise RuntimeError("No se encontró IVA 15% (codigo_sri=4) en el catálogo incluso después de cargarlo.")

        # ICE ejemplo: Cigarrillos Rubios (codigo_sri="3011")
        ice = session.exec(
            select(ImpuestoCatalogo).where(
                ImpuestoCatalogo.codigo_sri == "3011",
                ImpuestoCatalogo.tipo_impuesto == TipoImpuesto.ICE
            )
        ).first()
        if not ice:
            raise RuntimeError("No se encontró ICE (codigo_sri=3011) en el catálogo incluso después de cargarlo.")

        session.commit()

        # Producto principal (verificar si existe o crearlo con servicio)
        producto = session.exec(select(Producto).where(Producto.nombre == "Laptop Gamer X Pro")).first()
        if not producto:
            prod_service = ProductoService()
            producto_data = ProductoCreate(
                nombre="Laptop Gamer X Pro",
                tipo="BIEN",
                pvp=Decimal("2999.00"),
                casa_comercial_id=casa.id,
                impuesto_catalogo_ids=[iva.id, ice.id],  # OBLIGATORIO: incluir impuestos
                usuario_auditoria=USUARIO,
            )
            producto = prod_service.create(session, producto_data)
        created = producto is not None

        # Asociaciones categorías (solo laptop hoja)
        if not session.exec(
            select(ProductoCategoria).where(
                ProductoCategoria.producto_id == producto.id,
                ProductoCategoria.categoria_id == laptop.id,
            )
        ).first():
            session.add(ProductoCategoria(producto_id=producto.id, categoria_id=laptop.id))

        # Asociaciones proveedores persona
        for pid in proveedores_persona_ids:
            if not session.exec(
                select(ProductoProveedorPersona).where(
                    ProductoProveedorPersona.producto_id == producto.id,
                    ProductoProveedorPersona.proveedor_persona_id == pid,
                )
            ).first():
                session.add(ProductoProveedorPersona(producto_id=producto.id, proveedor_persona_id=pid))

        # Asociaciones proveedores sociedad
        for sid in proveedores_sociedad_ids:
            if not session.exec(
                select(ProductoProveedorSociedad).where(
                    ProductoProveedorSociedad.producto_id == producto.id,
                    ProductoProveedorSociedad.proveedor_sociedad_id == sid,
                )
            ).first():
                session.add(ProductoProveedorSociedad(producto_id=producto.id, proveedor_sociedad_id=sid))

        session.commit()

        # Nota: la relación producto-atributo directa (tbl_tipo_producto) fue eliminada.
        # Los atributos efectivos del producto se determinan por herencia de categorías.
        # Si se requieren valores por producto, este seed ya no los persiste.

        # Construir salida usando el servicio principal
        if 'prod_service' not in locals():
            prod_service = ProductoService()
        resultado = prod_service.get_producto_completo(session, producto.id)

        print("=== Producto completo seed ===")
        from json import dumps
        # Serialización segura (UUIDs y Decimals) usando Pydantic v2
        try:
            payload = resultado.model_dump(mode="json")
        except Exception:
            # Fallback genérico convirtiendo cualquier objeto no serializable a str
            from fastapi.encoders import jsonable_encoder
            payload = jsonable_encoder(resultado)
        print(dumps(payload, indent=2, ensure_ascii=False))
        # Visibilidad explícita de la cantidad inicial
        try:
            print("Cantidad inicial:", payload.get("cantidad", "(no disponible)"))
        except Exception:
            pass
        print("ID del producto:", producto.id)
        print("Ejemplo de uso: GET /api/productos/", producto.id)


if __name__ == "__main__":
    seed()

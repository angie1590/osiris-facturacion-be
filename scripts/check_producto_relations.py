#!/usr/bin/env python3
"""Verifica relaciones de productos (categoria, categoria_atributo y EAV tipado)."""

import sys
from pathlib import Path
from decimal import Decimal

# Añadir src al path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from osiris.core.db import get_session
from osiris.modules.inventario.producto.entity import (
    Producto,
    ProductoCategoria,
    ProductoImpuesto,
    ProductoBodega,
)
from osiris.modules.inventario.producto.models_atributos import ProductoAtributoValor
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.inventario.categoria.service import CategoriaService
from osiris.modules.inventario.atributo.entity import Atributo
from osiris.modules.sri.impuesto_catalogo.entity import ImpuestoCatalogo
from sqlmodel import select


def _extract_eav_valor(row: ProductoAtributoValor):
    if row.valor_string is not None:
        return row.valor_string
    if row.valor_integer is not None:
        return row.valor_integer
    if row.valor_decimal is not None:
        if isinstance(row.valor_decimal, Decimal):
            return str(row.valor_decimal)
        return row.valor_decimal
    if row.valor_boolean is not None:
        return row.valor_boolean
    if row.valor_date is not None:
        return row.valor_date.isoformat()
    return None

def main():
    session_gen = get_session()
    session = next(session_gen)
    categoria_service = CategoriaService()

    print("=" * 70)
    print("VERIFICACIÓN DE RELACIONES DE PRODUCTOS")
    print("=" * 70)

    # Tomar primer producto
    producto = session.exec(select(Producto).limit(1)).first()

    if not producto:
        print("❌ No hay productos en la BD")
        return

    print(f"\n📦 Producto: {producto.nombre}")
    print(f"   PVP: ${float(producto.pvp):.2f}")
    print(f"   Código barras: {producto.codigo_barras or 'Sin código'}")
    print(f"   Descripción: {producto.descripcion[:60] if producto.descripcion else 'Sin descripción'}...")

    # Categorías
    cat_rels = session.exec(
        select(ProductoCategoria).where(ProductoCategoria.producto_id == producto.id)
    ).all()

    print(f"\n📁 Categorías asignadas: {len(cat_rels)}")
    categoria_ids = []
    for rel in cat_rels:
        cat = session.get(Categoria, rel.categoria_id)
        if cat:
            categoria_ids.append(cat.id)
            print(f"   • {cat.nombre} (es_padre={cat.es_padre})")

    # CategoriaAtributo (directo) por cada categoria del producto
    print("\n🧩 CategoriaAtributo directos por categoría:")
    for categoria_id in categoria_ids:
        categoria = session.get(Categoria, categoria_id)
        rows = session.exec(
            select(CategoriaAtributo).where(
                CategoriaAtributo.categoria_id == categoria_id,
                CategoriaAtributo.activo.is_(True),
            )
        ).all()
        print(f"   - {categoria.nombre if categoria else categoria_id}: {len(rows)} atributos activos")
        for row in rows:
            atributo = session.get(Atributo, row.atributo_id)
            atributo_nombre = atributo.nombre if atributo else str(row.atributo_id)
            print(
                f"     • {atributo_nombre} | obligatorio={row.obligatorio} | "
                f"orden={row.orden} | default={row.valor_default}"
            )

    # Esqueleto heredado via CTE (incluye ancestros y resuelve conflictos por cercania)
    esqueleto = categoria_service.get_atributos_heredados_por_categorias(session, categoria_ids)
    print(f"\n🧠 Atributos aplicables por CTE (heredados): {len(esqueleto)}")
    for item in esqueleto:
        tipo = item["tipo_dato"].value if hasattr(item["tipo_dato"], "value") else item["tipo_dato"]
        print(
            f"   • {item['atributo_nombre']} ({tipo}) | obligatorio={item['obligatorio']} "
            f"| orden={item['orden']} | categoria_origen={item['categoria_origen_id']}"
        )

    # Impuestos
    imp_rels = session.exec(
        select(ProductoImpuesto).where(ProductoImpuesto.producto_id == producto.id)
    ).all()

    print(f"\n💰 Impuestos aplicados: {len(imp_rels)}")
    for rel in imp_rels:
        imp = session.get(ImpuestoCatalogo, rel.impuesto_catalogo_id)
        if imp:
            tarifa = imp.porcentaje_iva or imp.tarifa_ad_valorem or "N/A"
            print(f"   • {imp.descripcion[:50]} ({imp.codigo_sri}) - Tarifa: {tarifa}%")

    # Bodegas
    bod_rels = session.exec(
        select(ProductoBodega).where(ProductoBodega.producto_id == producto.id)
    ).all()

    print(f"\n🏢 Stock en bodegas: {len(bod_rels)}")
    from osiris.modules.inventario.bodega.entity import Bodega
    for rel in bod_rels:
        bod = session.get(Bodega, rel.bodega_id)
        if bod:
            print(f"   • {bod.codigo_bodega:15s} - {bod.nombre_bodega:30s} | {rel.cantidad:3d} unidades")

    # Valores EAV persistidos
    pav_rows = session.exec(
        select(ProductoAtributoValor).where(ProductoAtributoValor.producto_id == producto.id)
    ).all()
    pav_by_attr = {row.atributo_id: row for row in pav_rows}
    print(f"\n🧾 Valores EAV persistidos: {len(pav_rows)}")
    for row in pav_rows:
        atributo = session.get(Atributo, row.atributo_id)
        atributo_nombre = atributo.nombre if atributo else str(row.atributo_id)
        print(f"   • {atributo_nombre}: {_extract_eav_valor(row)}")

    # Merge final esperado para GET /productos/{id}
    print("\n🔀 Merge esqueleto CTE + EAV persistido:")
    for item in esqueleto:
        row = pav_by_attr.get(item["atributo_id"])
        valor = _extract_eav_valor(row) if row else None
        print(f"   • {item['atributo_nombre']}: {valor} (obligatorio={item['obligatorio']})")

    hidden_attr_ids = set(pav_by_attr.keys()) - {item["atributo_id"] for item in esqueleto}
    if hidden_attr_ids:
        print("\n👁️  Valores EAV ocultos por reglas de aplicabilidad (p.ej. soft-delete en categoria_atributo):")
        for atributo_id in hidden_attr_ids:
            atributo = session.get(Atributo, atributo_id)
            atributo_nombre = atributo.nombre if atributo else str(atributo_id)
            print(f"   • {atributo_nombre}: {_extract_eav_valor(pav_by_attr[atributo_id])}")

    print("\n" + "=" * 70)
    print("✓ Verificación de relaciones completada")
    print("=" * 70)
    session.close()
    try:
        next(session_gen)
    except StopIteration:
        pass

if __name__ == "__main__":
    main()

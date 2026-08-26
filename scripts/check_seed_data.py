#!/usr/bin/env python3
"""Script rapido para verificar datos del seed (incluye EAV de productos)."""

import sys
from pathlib import Path

# Añadir src al path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from osiris.core.db import get_session
from osiris.modules.inventario.producto.entity import Producto
from osiris.modules.inventario.bodega.entity import Bodega
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.inventario.producto.entity import ProductoCategoria
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.inventario.producto.models_atributos import ProductoAtributoValor
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.atributo.entity import Atributo
from sqlmodel import select, func


def _valor_no_nulo_count(row: ProductoAtributoValor) -> int:
    return sum(
        value is not None
        for value in [
            row.valor_string,
            row.valor_integer,
            row.valor_decimal,
            row.valor_boolean,
            row.valor_date,
        ]
    )


def _valor_humano(row: ProductoAtributoValor):
    if row.valor_string is not None:
        return row.valor_string
    if row.valor_integer is not None:
        return row.valor_integer
    if row.valor_decimal is not None:
        return row.valor_decimal
    if row.valor_boolean is not None:
        return row.valor_boolean
    if row.valor_date is not None:
        return row.valor_date
    return None

def main():
    session_gen = get_session()
    session = next(session_gen)

    print("=" * 60)
    print("VERIFICACIÓN DE DATOS SEED")
    print("=" * 60)

    # Contar registros
    empresas = session.exec(select(func.count(Empresa.id))).first()
    sucursales = session.exec(select(func.count(Sucursal.id))).first()
    bodegas = session.exec(select(func.count(Bodega.id))).first()
    productos = session.exec(select(func.count(Producto.id))).first()
    producto_categorias = session.exec(select(func.count(ProductoCategoria.id))).first()
    categoria_atributos = session.exec(select(func.count(CategoriaAtributo.id))).first()
    categoria_atributos_activos = session.exec(
        select(func.count(CategoriaAtributo.id)).where(CategoriaAtributo.activo.is_(True))
    ).first()
    producto_atributo_valores = session.exec(select(func.count(ProductoAtributoValor.id))).first()

    print("\nResumen de tablas:")
    print(f"  - Empresas: {empresas}")
    print(f"  - Sucursales: {sucursales}")
    print(f"  - Bodegas: {bodegas}")
    print(f"  - Productos: {productos}")
    print(f"  - ProductoCategoria: {producto_categorias}")
    print(f"  - CategoriaAtributo: {categoria_atributos} (activos={categoria_atributos_activos})")
    print(f"  - ProductoAtributoValor: {producto_atributo_valores}")

    # Mostrar 5 productos
    print("\nPrimeros 5 productos:")
    prods = session.exec(select(Producto).limit(5)).all()
    for p in prods:
        desc = p.descripcion[:40] if p.descripcion else "Sin descripción"
        barcode = p.codigo_barras or "Sin código"
        print(f"  • {barcode:15s} | {p.nombre[:30]:30s} | ${float(p.pvp):8.2f} | {desc}...")

    # Mostrar bodegas
    print("\nBodegas:")
    bods = session.exec(select(Bodega)).all()
    for b in bods:
        print(f"  • {b.codigo_bodega} | {b.nombre_bodega}")

    # Muestra resumen de relaciones categoria-atributo activas
    print("\nCategoriaAtributo activos (top 10):")
    cat_atr_rows = session.exec(
        select(CategoriaAtributo).where(CategoriaAtributo.activo.is_(True)).limit(10)
    ).all()
    for rel in cat_atr_rows:
        categoria = session.get(Categoria, rel.categoria_id)
        atributo = session.get(Atributo, rel.atributo_id)
        categoria_nombre = categoria.nombre if categoria else str(rel.categoria_id)
        atributo_nombre = atributo.nombre if atributo else str(rel.atributo_id)
        print(
            f"  • {categoria_nombre:25s} | {atributo_nombre:25s} | "
            f"obligatorio={rel.obligatorio!s:5s} | default={rel.valor_default}"
        )

    # Verifica integridad logica de EAV
    print("\nVerificacion EAV (ProductoAtributoValor):")
    pav_rows = session.exec(select(ProductoAtributoValor)).all()
    invalid_rows = [row for row in pav_rows if _valor_no_nulo_count(row) != 1]
    print(f"  - Registros EAV revisados: {len(pav_rows)}")
    print(f"  - Registros con columna valor_* invalida: {len(invalid_rows)}")

    if invalid_rows:
        for row in invalid_rows[:10]:
            print(f"    ⚠ invalido id={row.id} producto={row.producto_id} atributo={row.atributo_id}")
    else:
        print("  - OK: todos los registros tienen exactamente una columna valor_* no nula")

    print("\nMuestra EAV (top 10):")
    for row in pav_rows[:10]:
        atributo = session.get(Atributo, row.atributo_id)
        atributo_nombre = atributo.nombre if atributo else str(row.atributo_id)
        print(
            f"  • producto={str(row.producto_id)[:8]}... "
            f"atributo={atributo_nombre:25s} valor={_valor_humano(row)}"
        )

    print("\n" + "=" * 60)
    print("Verificacion completada")
    print("=" * 60)
    session.close()
    try:
        next(session_gen)
    except StopIteration:
        pass

if __name__ == "__main__":
    main()

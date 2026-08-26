#!/usr/bin/env python3
"""
Script para eliminar (hard delete) todos los datos creados por tests.
Preserva los datos del seed (usuario_auditoria = 'seed').

Uso:
    python scripts/cleanup_test_data.py
"""
import sys
from pathlib import Path

# Añadir src al path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from osiris.core.db import engine
from sqlalchemy import text


def cleanup_test_data():
    """Elimina físicamente todos los registros creados por tests."""

    test_users = "('smoke_test', 'ci', 'test')"

    with engine.begin() as conn:
        print("🧹 Iniciando limpieza de datos de test...")
        print(f"   Usuarios de test: {test_users}\n")

        # 1. Contar registros antes
        result = conn.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE usuario_auditoria IN ('smoke_test', 'ci', 'test')) as test_count,
                COUNT(*) FILTER (WHERE usuario_auditoria = 'seed') as seed_count,
                COUNT(*) as total
            FROM tbl_producto
        """))
        before = result.fetchone()
        print("📊 Estado ANTES:")
        print(f"   - Productos test: {before[0]}")
        print(f"   - Productos seed: {before[1]}")
        print(f"   - Total: {before[2]}\n")

        # 2. Eliminar relaciones de productos (tablas bridge)
        print("🗑️  Eliminando relaciones de productos...")

        # Producto-Categoria
        result = conn.execute(text(f"""
            DELETE FROM tbl_producto_categoria
            WHERE producto_id IN (
                SELECT id FROM tbl_producto
                WHERE usuario_auditoria IN {test_users}
            )
        """))
        print(f"   - tbl_producto_categoria: {result.rowcount} registros")

        # Producto-Proveedor Persona
        result = conn.execute(text(f"""
            DELETE FROM tbl_producto_proveedor_persona
            WHERE producto_id IN (
                SELECT id FROM tbl_producto
                WHERE usuario_auditoria IN {test_users}
            )
        """))
        print(f"   - tbl_producto_proveedor_persona: {result.rowcount} registros")

        # Producto-Proveedor Sociedad
        result = conn.execute(text(f"""
            DELETE FROM tbl_producto_proveedor_sociedad
            WHERE producto_id IN (
                SELECT id FROM tbl_producto
                WHERE usuario_auditoria IN {test_users}
            )
        """))
        print(f"   - tbl_producto_proveedor_sociedad: {result.rowcount} registros")

        # Producto-Impuesto
        result = conn.execute(text(f"""
            DELETE FROM tbl_producto_impuesto
            WHERE producto_id IN (
                SELECT id FROM tbl_producto
                WHERE usuario_auditoria IN {test_users}
            )
        """))
        print(f"   - tbl_producto_impuesto: {result.rowcount} registros")

        # Producto-Bodega
        result = conn.execute(text(f"""
            DELETE FROM tbl_producto_bodega
            WHERE producto_id IN (
                SELECT id FROM tbl_producto
                WHERE usuario_auditoria IN {test_users}
            )
        """))
        print(f"   - tbl_producto_bodega: {result.rowcount} registros")

        # 3. Eliminar productos de test
        print("\n🗑️  Eliminando productos de test...")
        result = conn.execute(text(f"""
            DELETE FROM tbl_producto
            WHERE usuario_auditoria IN {test_users}
        """))
        print(f"   - tbl_producto: {result.rowcount} registros")

        # 4. Eliminar atributos de test
        print("\n🗑️  Eliminando atributos de test...")
        result = conn.execute(text(f"""
            DELETE FROM tbl_categoria_atributo
            WHERE atributo_id IN (
                SELECT id FROM tbl_atributo
                WHERE usuario_auditoria IN {test_users}
            )
        """))
        print(f"   - tbl_categoria_atributo: {result.rowcount} registros")

        result = conn.execute(text(f"""
            DELETE FROM tbl_atributo
            WHERE usuario_auditoria IN {test_users}
        """))
        print(f"   - tbl_atributo: {result.rowcount} registros")

        # 5. Eliminar proveedores de test
        print("\n🗑️  Eliminando proveedores de test...")
        result = conn.execute(text(f"""
            DELETE FROM tbl_producto_proveedor_persona
            WHERE proveedor_persona_id IN (
                SELECT id FROM tbl_proveedor_persona
                WHERE usuario_auditoria IN {test_users}
            )
        """))
        print(f"   - tbl_producto_proveedor_persona (por proveedor): {result.rowcount} registros")

        result = conn.execute(text(f"""
            DELETE FROM tbl_producto_proveedor_sociedad
            WHERE proveedor_sociedad_id IN (
                SELECT id FROM tbl_proveedor_sociedad
                WHERE usuario_auditoria IN {test_users}
            )
        """))
        print(f"   - tbl_producto_proveedor_sociedad (por proveedor): {result.rowcount} registros")

        result = conn.execute(text(f"""
            DELETE FROM tbl_proveedor_persona
            WHERE usuario_auditoria IN {test_users}
        """))
        print(f"   - tbl_proveedor_persona: {result.rowcount} registros")

        result = conn.execute(text(f"""
            DELETE FROM tbl_proveedor_sociedad
            WHERE usuario_auditoria IN {test_users}
        """))
        print(f"   - tbl_proveedor_sociedad: {result.rowcount} registros")

        # 6. Eliminar casas comerciales de test
        print("\n🗑️  Eliminando casas comerciales de test...")
        result = conn.execute(text(f"""
            DELETE FROM tbl_casa_comercial
            WHERE usuario_auditoria IN {test_users}
        """))
        print(f"   - tbl_casa_comercial: {result.rowcount} registros")

        # 7. Eliminar categorías de test
        print("\n🗑️  Eliminando categorías de test...")
        result = conn.execute(text(f"""
            DELETE FROM tbl_categoria_atributo
            WHERE categoria_id IN (
                SELECT id FROM tbl_categoria
                WHERE usuario_auditoria IN {test_users}
            )
        """))
        print(f"   - tbl_categoria_atributo (por categoría): {result.rowcount} registros")

        result = conn.execute(text(f"""
            DELETE FROM tbl_categoria
            WHERE usuario_auditoria IN {test_users}
        """))
        print(f"   - tbl_categoria: {result.rowcount} registros")

        # 8. NO eliminar impuestos del catálogo (son datos compartidos del sistema)
        # print("\n🗑️  Eliminando impuestos de test...")
        # result = conn.execute(text(f"""
        #     DELETE FROM aux_impuesto_catalogo
        #     WHERE usuario_auditoria IN {test_users}
        # """))
        # print(f"   - aux_impuesto_catalogo: {result.rowcount} registros")

        # 9. Otras entidades comunes (orden: dependientes primero)
        print("\n🗑️  Eliminando otras entidades de test...")

        # Clientes (referencia persona)
        result = conn.execute(text(f"""
            DELETE FROM tbl_cliente
            WHERE usuario_auditoria IN {test_users}
        """))
        print(f"   - tbl_cliente: {result.rowcount} registros")

        # Empleados (referencia persona y usuario)
        result = conn.execute(text(f"""
            DELETE FROM tbl_empleado
            WHERE usuario_auditoria IN {test_users}
        """))
        print(f"   - tbl_empleado: {result.rowcount} registros")

        # Usuarios (referencia persona)
        result = conn.execute(text(f"""
            DELETE FROM tbl_usuario
            WHERE usuario_auditoria IN {test_users}
        """))
        print(f"   - tbl_usuario: {result.rowcount} registros")

        # 10. Eliminar personas de test (después de eliminar referencias)
        print("\n🗑️  Eliminando personas de test...")
        result = conn.execute(text(f"""
            DELETE FROM tbl_persona
            WHERE usuario_auditoria IN {test_users}
        """))
        print(f"   - tbl_persona: {result.rowcount} registros")

        # Roles-Modulos-Permisos (antes de roles y modulos)
        print("\n🗑️  Eliminando permisos de test...")
        result = conn.execute(text(f"""
            DELETE FROM roles_modulos_permisos
            WHERE usuario_auditoria IN {test_users}
        """))
        print(f"   - roles_modulos_permisos: {result.rowcount} registros")

        # Modulos
        result = conn.execute(text(f"""
            DELETE FROM tbl_modulo
            WHERE usuario_auditoria IN {test_users}
        """))
        print(f"   - tbl_modulo: {result.rowcount} registros")

        # Roles
        result = conn.execute(text(f"""
            DELETE FROM tbl_rol
            WHERE usuario_auditoria IN {test_users}
        """))
        print(f"   - tbl_rol: {result.rowcount} registros")

        # Tipo Cliente
        result = conn.execute(text(f"""
            DELETE FROM tbl_tipo_cliente
            WHERE usuario_auditoria IN {test_users}
        """))
        print(f"   - tbl_tipo_cliente: {result.rowcount} registros")

        # Empresas, Sucursales, Puntos de Emisión, Bodegas
        result = conn.execute(text(f"""
            DELETE FROM tbl_punto_emision
            WHERE usuario_auditoria IN {test_users}
        """))
        print(f"   - tbl_punto_emision: {result.rowcount} registros")

        # Eliminar bodegas que referencian sucursales de test (incluso si son del seed)
        result = conn.execute(text(f"""
            DELETE FROM tbl_bodega
            WHERE sucursal_id IN (
                SELECT id FROM tbl_sucursal
                WHERE usuario_auditoria IN {test_users}
            )
        """))
        print(f"   - tbl_bodega (por sucursal de test): {result.rowcount} registros")

        result = conn.execute(text(f"""
            DELETE FROM tbl_bodega
            WHERE usuario_auditoria IN {test_users}
        """))
        print(f"   - tbl_bodega: {result.rowcount} registros")

        # Eliminar bodegas que referencian empresas de test (por FK empresa_id)
        result = conn.execute(text(f"""
            DELETE FROM tbl_bodega
            WHERE empresa_id IN (
                SELECT id FROM tbl_empresa
                WHERE usuario_auditoria IN {test_users}
            )
        """))
        print(f"   - tbl_bodega (por empresa de test): {result.rowcount} registros")

        result = conn.execute(text(f"""
            DELETE FROM tbl_sucursal
            WHERE usuario_auditoria IN {test_users}
        """))
        print(f"   - tbl_sucursal: {result.rowcount} registros")

        result = conn.execute(text(f"""
            DELETE FROM tbl_empresa
            WHERE usuario_auditoria IN {test_users}
        """))
        print(f"   - tbl_empresa: {result.rowcount} registros")

        # 11. Contar registros después
        result = conn.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE usuario_auditoria IN ('smoke_test', 'ci', 'test')) as test_count,
                COUNT(*) FILTER (WHERE usuario_auditoria = 'seed') as seed_count,
                COUNT(*) as total
            FROM tbl_producto
        """))
        after = result.fetchone()

        print("\n📊 Estado DESPUÉS:")
        print(f"   - Productos test: {after[0]}")
        print(f"   - Productos seed: {after[1]}")
        print(f"   - Total: {after[2]}")

        print("\n✅ Limpieza completada exitosamente!")
        print("   Los datos del seed han sido preservados.")


if __name__ == "__main__":
    try:
        cleanup_test_data()
    except Exception as e:
        print(f"\n❌ Error durante la limpieza: {e}")
        sys.exit(1)

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import func
from sqlmodel import Session, select

from osiris.core.company_scope import resolve_company_scope
from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.core.errors import NotFoundError
from osiris.domain.service import BaseService
from osiris.modules.inventario.categoria.entity import Categoria  # existente
from osiris.modules.inventario.categoria.service import CategoriaService
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.producto.models_atributos import ProductoAtributoValor
from osiris.modules.inventario.producto_impuesto.service import ProductoImpuestoService
from osiris.modules.sri.impuesto_catalogo.entity import ImpuestoCatalogo
from osiris.utils.pagination import build_pagination_meta
from fastapi import HTTPException
from .repository import ProductoRepository
from .entity import (
    Producto,
    ProductoCategoria,
    ProductoProveedorPersona,
    ProductoProveedorSociedad,
    ProductoBodega,
    ProductoImpuesto,
)
from osiris.modules.inventario.bodega.entity import Bodega

class ProductoService(BaseService):
    repo = ProductoRepository()

    # Validación de FKs estándar (existencia/activo) para casa comercial
    fk_models = {
        "casa_comercial_id": CasaComercial,
    }

    @staticmethod
    def _empresa_scope() -> UUID | None:
        return resolve_company_scope()

    def _asegurar_producto_en_scope(self, session: Session, producto_id: UUID) -> None:
        empresa_scope = self._empresa_scope()
        if empresa_scope is None:
            return

        asignado_alguna_bodega = session.exec(
            select(ProductoBodega.id)
            .join(Bodega, Bodega.id == ProductoBodega.bodega_id)
            .where(
                ProductoBodega.producto_id == producto_id,
                ProductoBodega.activo.is_(True),
                Bodega.activo.is_(True),
            )
            .limit(1)
        ).first()

        # Mantiene compatibilidad legacy para productos aún no asignados a bodegas.
        if asignado_alguna_bodega is None:
            return

        asignado_en_scope = session.exec(
            select(ProductoBodega.id)
            .join(Bodega, Bodega.id == ProductoBodega.bodega_id)
            .where(
                ProductoBodega.producto_id == producto_id,
                ProductoBodega.activo.is_(True),
                Bodega.activo.is_(True),
                Bodega.empresa_id == empresa_scope,
            )
            .limit(1)
        ).first()
        if asignado_en_scope is None:
            raise HTTPException(status_code=403, detail="No autorizado para acceder a productos de otra empresa.")

    def _validate_leaf_categories(self, session: Session, categoria_ids: Iterable[UUID]) -> None:
        if not categoria_ids:
            return
        for cid in categoria_ids:
            # una categoría es hoja si no tiene hijos
            has_children = session.exec(select(Categoria).where(Categoria.parent_id == cid)).first() is not None
            if has_children:
                raise HTTPException(status_code=400, detail="Solo se permiten categorías hoja (sin hijos) para el producto.")

    def _validate_impuestos(self, session: Session, impuesto_ids: Iterable[UUID], tipo_producto) -> None:
        """
        Valida que:
        1. Solo haya un impuesto de cada tipo (IVA, ICE, IRBPNR)
        2. Al menos un IVA esté presente (obligatorio según SRI)
        3. Los impuestos existan y estén activos
        4. Sean compatibles con el tipo de producto
        """
        if not impuesto_ids:
            raise HTTPException(status_code=400, detail="Debe incluir al menos un impuesto IVA.")

        tipos_vistos = set()
        tiene_iva = False

        for imp_id in impuesto_ids:
            # Verificar que el impuesto existe y está activo
            impuesto = session.get(ImpuestoCatalogo, imp_id)
            if not impuesto or not impuesto.activo:
                raise HTTPException(status_code=400, detail=f"El impuesto {imp_id} no existe o está inactivo.")

            # Validar que no se repita el tipo de impuesto
            tipo_impuesto = impuesto.tipo_impuesto
            if tipo_impuesto in tipos_vistos:
                raise HTTPException(
                    status_code=400,
                    detail=f"Solo se permite un impuesto de tipo {tipo_impuesto.value} por producto."
                )
            tipos_vistos.add(tipo_impuesto)

            # Verificar que hay al menos un IVA (comparar con el enum directamente)
            from osiris.modules.sri.impuesto_catalogo.entity import TipoImpuesto
            if tipo_impuesto == TipoImpuesto.IVA:
                tiene_iva = True

            # Validar compatibilidad con tipo de producto
            ProductoImpuestoService()._validar_compatibilidad_tipo(tipo_producto, impuesto.aplica_a)

        if not tiene_iva:
            raise HTTPException(
                status_code=400,
                detail="Debe incluir exactamente un impuesto de tipo IVA. Los productos siempre deben tener IVA."
            )

    def create(self, session: Session, data):
        try:
            def _val(obj, key):
                if obj is None:
                    return None
                if hasattr(obj, "get"):
                    try:
                        return obj.get(key)
                    except (AttributeError, TypeError, KeyError):
                        return None
                return getattr(obj, key, None)

            categoria_ids: Optional[Iterable[UUID]] = _val(data, "categoria_ids")
            self._validate_leaf_categories(session, categoria_ids or [])

            # Validar impuestos antes de crear el producto
            impuesto_ids: Optional[Iterable[UUID]] = _val(data, "impuesto_catalogo_ids")
            tipo_producto = _val(data, "tipo")
            if impuesto_ids:
                self._validate_impuestos(session, impuesto_ids, tipo_producto)

            prod = super().create(session, data, commit=False)
            pid = prod.id

            # asociaciones
            if categoria_ids:
                self.repo.set_categorias(session, pid, categoria_ids)
            usuario_auditoria = _val(data, "usuario_auditoria")

            # Asociar impuestos automáticamente
            if impuesto_ids:
                for imp_id in impuesto_ids:
                    impuesto = session.get(ImpuestoCatalogo, imp_id)
                    if not impuesto:
                        raise HTTPException(status_code=400, detail=f"Impuesto {imp_id} no existe.")

                    if impuesto.tipo_impuesto.value == "IVA":
                        tarifa = impuesto.porcentaje_iva or 0
                    elif impuesto.tipo_impuesto.value == "ICE":
                        tarifa = impuesto.tarifa_ad_valorem or 0
                    else:
                        tarifa = 0

                    producto_impuesto = ProductoImpuesto(
                        producto_id=pid,
                        impuesto_catalogo_id=imp_id,
                        codigo_impuesto_sri=impuesto.codigo_tipo_impuesto,
                        codigo_porcentaje_sri=impuesto.codigo_sri,
                        tarifa=tarifa,
                        usuario_auditoria=usuario_auditoria
                    )
                    session.add(producto_impuesto)

            session.commit()
            session.refresh(prod)
            return prod
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    def update(self, session: Session, item_id: UUID, data):
        try:
            self._asegurar_producto_en_scope(session, item_id)
            # validar categorías si vienen
            def _val(obj, key):
                if obj is None:
                    return None
                if hasattr(obj, "get"):
                    try:
                        return obj.get(key)
                    except (AttributeError, TypeError, KeyError):
                        return None
                return getattr(obj, key, None)

            categoria_ids = _val(data, "categoria_ids")
            if categoria_ids is not None:
                self._validate_leaf_categories(session, categoria_ids)
            prod = super().update(session, item_id, data, commit=False)
            if prod is None:
                return None
            # asociaciones
            if categoria_ids is not None:
                self.repo.set_categorias(session, item_id, categoria_ids)
            _val(data, "usuario_auditoria")
            session.commit()
            session.refresh(prod)
            return prod
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    def get(self, session: Session, item_id: UUID):
        prod = super().get(session, item_id)
        if prod is None:
            raise NotFoundError("Producto no encontrado")
        self._asegurar_producto_en_scope(session, item_id)
        return prod

    def delete(self, session: Session, item_id: UUID):
        self._asegurar_producto_en_scope(session, item_id)
        return super().delete(session, item_id)

    def get_with_impuestos(self, session: Session, item_id: UUID):
        """
        Obtiene un producto con su lista completa de impuestos incluida.
        Retorna tupla (producto, lista_impuestos).
        """
        prod = self.get(session, item_id)

        # Obtener impuestos del producto
        producto_impuesto_service = ProductoImpuestoService()
        impuestos = producto_impuesto_service.get_impuestos_completos(session, item_id)

        # Retornar tupla para que el router construya el response
        return prod, impuestos

    def _build_categoria_ruta(self, session: Session, categoria_id: UUID) -> str:
        """Construye la ruta completa de una categoría (ej: Tecnología > Computadoras > Laptop)"""
        from osiris.modules.inventario.categoria.entity import Categoria

        ruta_parts = []
        current_id = categoria_id

        while current_id:
            categoria = session.get(Categoria, current_id)
            if not categoria:
                break
            ruta_parts.insert(0, categoria.nombre)
            current_id = categoria.parent_id

        return " > ".join(ruta_parts)

    @staticmethod
    def _extract_valor_por_tipo(tipo_dato: object, registro: ProductoAtributoValor | None):
        if registro is None:
            return None

        tipo = tipo_dato.value if hasattr(tipo_dato, "value") else tipo_dato
        tipo_normalizado = str(tipo).lower() if tipo is not None else ""

        if tipo_normalizado == "string":
            return registro.valor_string
        if tipo_normalizado == "integer":
            return registro.valor_integer
        if tipo_normalizado == "decimal":
            return registro.valor_decimal
        if tipo_normalizado == "boolean":
            return registro.valor_boolean
        if tipo_normalizado == "date":
            return registro.valor_date
        return None

    @staticmethod
    def _merge_atributos_esqueleto_con_valores(
        esqueleto: list[dict],
        valores_por_atributo: dict[UUID, object],
    ) -> list[dict]:
        merged: list[dict] = []
        for item in esqueleto:
            atributo_id = item["atributo_id"]
            tipo_dato = item.get("tipo_dato")
            tipo_dato_val = tipo_dato.value if hasattr(tipo_dato, "value") else tipo_dato
            merged.append(
                {
                    "atributo": {
                        "id": atributo_id,
                        "nombre": item["atributo_nombre"],
                        "tipo_dato": tipo_dato_val,
                    },
                    "valor": valores_por_atributo.get(atributo_id),
                    "obligatorio": item.get("obligatorio"),
                    "orden": item.get("orden"),
                }
            )
        return merged

    def get_producto_completo(self, session: Session, producto_id: UUID) -> dict:
        """Obtiene un producto con todas sus relaciones completas según contrato"""
        from osiris.modules.inventario.casa_comercial.entity import CasaComercial
        from osiris.modules.inventario.categoria.entity import Categoria
        from osiris.modules.common.proveedor_persona.entity import ProveedorPersona
        from osiris.modules.common.proveedor_sociedad.entity import ProveedorSociedad
        from osiris.modules.common.persona.entity import Persona
        from osiris.modules.inventario.producto_impuesto.service import ProductoImpuestoService

        producto = self.get(session, producto_id)

        # Casa comercial
        casa_comercial = None
        if producto.casa_comercial_id:
            casa = session.get(CasaComercial, producto.casa_comercial_id)
            if casa:
                casa_comercial = {"nombre": casa.nombre}

        # Categorías con ruta
        categorias = []
        cat_ids = session.exec(
            select(ProductoCategoria.categoria_id)
            .where(ProductoCategoria.producto_id == producto_id)
        ).all()
        for cat_id in cat_ids:
            cat = session.get(Categoria, cat_id)
            if cat:
                categorias.append({
                    "id": cat.id,
                    "nombre": cat.nombre,
                })

        # Proveedores persona
        proveedores_persona = []
        prov_pers_ids = session.exec(
            select(ProductoProveedorPersona.proveedor_persona_id)
            .where(ProductoProveedorPersona.producto_id == producto_id)
        ).all()
        for prov_id in prov_pers_ids:
            prov = session.get(ProveedorPersona, prov_id)
            if prov:
                persona = session.get(Persona, prov.persona_id)
                if persona:
                    proveedores_persona.append({
                        "nombres": persona.nombre,
                        "apellidos": persona.apellido,
                        "nombre_comercial": getattr(prov, "nombre_comercial", None)
                    })

        # Proveedores sociedad
        proveedores_sociedad = []
        prov_soc_ids = session.exec(
            select(ProductoProveedorSociedad.proveedor_sociedad_id)
            .where(ProductoProveedorSociedad.producto_id == producto_id)
        ).all()
        for prov_id in prov_soc_ids:
            prov = session.get(ProveedorSociedad, prov_id)
            if prov:
                proveedores_sociedad.append({
                    "razon_social": prov.razon_social,
                    "nombre_comercial": getattr(prov, "nombre_comercial", None)
                })

        # Atributos efectivos por categoría (esqueleto heredado) + valores persistidos del producto
        atributos = []
        try:
            categoria_service = CategoriaService()
            esqueleto = categoria_service.get_atributos_heredados_por_categorias(session, list(cat_ids))

            # Valores persistidos
            valores_rows = session.exec(
                select(ProductoAtributoValor).where(ProductoAtributoValor.producto_id == producto_id)
            ).all()
            valores_rows_por_atributo = {row.atributo_id: row for row in valores_rows}
            valores_por_atributo = {
                item["atributo_id"]: self._extract_valor_por_tipo(
                    item.get("tipo_dato"),
                    valores_rows_por_atributo.get(item["atributo_id"]),
                )
                for item in esqueleto
            }

            atributos = self._merge_atributos_esqueleto_con_valores(esqueleto, valores_por_atributo)
        except Exception:
            atributos = []

        # Impuestos (resiliente: si algo falla, lista vacía)
        impuestos = []
        try:
            impuesto_service = ProductoImpuestoService()
            impuestos_raw = impuesto_service.get_impuestos_completos(session, producto_id)
            for imp in impuestos_raw:
                porcentaje_val = Decimal("0.00")
                try:
                    # IVA usa porcentaje_iva, ICE usa tarifa_ad_valorem
                    raw_porcentaje = imp.porcentaje_iva or imp.tarifa_ad_valorem or Decimal("0.00")
                    porcentaje_val = (
                        raw_porcentaje
                        if isinstance(raw_porcentaje, Decimal)
                        else Decimal(str(raw_porcentaje))
                    )
                except Exception:
                    porcentaje_val = Decimal("0.00")
                impuestos.append({
                    "nombre": imp.descripcion,
                    "codigo": imp.codigo_sri,
                    "porcentaje": porcentaje_val,
                })
        except Exception:
            impuestos = []

        # Bodegas (relación producto-bodega)
        from osiris.modules.inventario.bodega.entity import Bodega

        bodegas = []
        try:
            bodega_ids = session.exec(
                select(ProductoBodega.bodega_id)
                .where(ProductoBodega.producto_id == producto_id)
            ).all()
            for bodega_id in bodega_ids:
                bodega = session.get(Bodega, bodega_id)
                if bodega:
                    bodegas.append({
                        "codigo_bodega": bodega.codigo_bodega,
                        "nombre_bodega": bodega.nombre_bodega,
                    })
        except Exception:
            bodegas = []

        return {
            "id": producto.id,
            "nombre": producto.nombre,
            "tipo": producto.tipo,
            "pvp": producto.pvp,
            "cantidad": producto.cantidad,
            "permite_fracciones": producto.permite_fracciones,
            "casa_comercial": casa_comercial,
            "categorias": categorias,
            "proveedores_persona": proveedores_persona,
            "proveedores_sociedad": proveedores_sociedad,
            "atributos": atributos,
            "impuestos": impuestos,
            "bodegas": bodegas,
        }

    def list_paginated_completo(self, session: Session, only_active: bool = True, limit: int = 50, offset: int = 0):
        """
        Lista paginada liviana de productos (metadata básica).
        La resolución de jerarquía de atributos se reserva para GET /productos/{id}.
        """
        stmt_base = select(Producto)
        empresa_scope = self._empresa_scope()
        if empresa_scope is not None:
            stmt_base = (
                stmt_base
                .join(ProductoBodega, ProductoBodega.producto_id == Producto.id)
                .join(Bodega, Bodega.id == ProductoBodega.bodega_id)
                .where(
                    ProductoBodega.activo.is_(True),
                    Bodega.activo.is_(True),
                    Bodega.empresa_id == empresa_scope,
                )
                .distinct()
            )
        if only_active is not None and hasattr(Producto, "activo"):
            stmt_base = stmt_base.where(Producto.activo == only_active)
        if hasattr(Producto, "activo") and only_active in {None, False}:
            stmt_base = stmt_base.execution_options(
                **{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True}
            )

        count_stmt = select(func.count()).select_from(stmt_base.subquery())
        if hasattr(Producto, "activo") and only_active in {None, False}:
            count_stmt = count_stmt.execution_options(
                **{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True}
            )
        total: int = int(session.exec(count_stmt).one())
        meta = build_pagination_meta(total=total, limit=limit, offset=offset)

        productos = list(session.exec(stmt_base.offset(offset).limit(limit)).all())
        items = [
            {
                "id": producto.id,
                "nombre": producto.nombre,
                "tipo": producto.tipo,
                "pvp": producto.pvp,
                "cantidad": producto.cantidad,
            }
            for producto in productos
        ]
        return items, meta

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Iterable, Optional
from uuid import UUID

from sqlalchemy import func, inspect as sqlalchemy_inspect, update
from sqlmodel import Session, col, select

from osiris.core.company_scope import resolve_company_scope
from osiris.core.audit import record_domain_change
from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.core.errors import NotFoundError
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.inventario.atributo.entity import TipoDato
from osiris.domain.service import BaseService
from osiris.modules.inventario.categoria.entity import Categoria  # existente
from osiris.modules.inventario.categoria.service import CategoriaService
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.producto.models_atributos import ProductoAtributoValor
from osiris.modules.inventario.producto_impuesto.service import ProductoImpuestoService
from osiris.modules.inventario.producto_impuesto.scope import resolve_product_tax_company
from osiris.modules.sri.impuesto_catalogo.entity import ImpuestoCatalogo, TipoImpuesto
from osiris.utils.pagination import PaginationMeta, build_pagination_meta
from fastapi import HTTPException
from .repository import ProductoRepository
from .entity import (
    Producto,
    ProductoCategoria,
    ProductoProveedorPersona,
    ProductoProveedorSociedad,
    ProductoBodega,
    ProductoImpuesto,
    TipoProducto,
)
from osiris.modules.inventario.bodega.entity import Bodega

class ProductoService(BaseService[Producto]):
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
            .join(Bodega, col(Bodega.id) == col(ProductoBodega.bodega_id))
            .where(
                col(ProductoBodega.producto_id) == producto_id,
                col(ProductoBodega.activo).is_(True),
                col(Bodega.activo).is_(True),
            )
            .limit(1)
        ).first()

        # Mantiene compatibilidad legacy para productos aún no asignados a bodegas.
        if asignado_alguna_bodega is None:
            return

        asignado_en_scope = session.exec(
            select(ProductoBodega.id)
            .join(Bodega, col(Bodega.id) == col(ProductoBodega.bodega_id))
            .where(
                col(ProductoBodega.producto_id) == producto_id,
                col(ProductoBodega.activo).is_(True),
                col(Bodega.activo).is_(True),
                col(Bodega.empresa_id) == empresa_scope,
            )
            .limit(1)
        ).first()
        if asignado_en_scope is None:
            raise HTTPException(status_code=403, detail="No autorizado para acceder a productos de otra empresa.")

    def _validate_leaf_categories(self, session: Session, categoria_ids: Iterable[UUID]) -> None:
        if not categoria_ids:
            return
        for cid in categoria_ids:
            categoria = session.exec(
                select(Categoria).where(
                    col(Categoria.id) == cid,
                    col(Categoria.activo).is_(True),
                )
            ).first()
            if not categoria or not categoria.activo:
                raise HTTPException(status_code=400, detail="La categoría no existe o está inactiva.")
            if categoria.is_default:
                raise HTTPException(
                    status_code=400,
                    detail="No se pueden asignar productos a la categoría temporal Sin clasificar.",
                )

            has_children = session.exec(
                select(Categoria.id).where(
                    col(Categoria.parent_id) == cid,
                    col(Categoria.activo).is_(True),
                )
            ).first() is not None
            if has_children:
                raise HTTPException(status_code=400, detail="Solo se permiten categorías hoja (sin hijos) para el producto.")

    def _validate_impuestos(
        self,
        session: Session,
        impuesto_ids: Iterable[UUID],
        tipo_producto: TipoProducto,
        empresa: Empresa | None = None,
    ) -> None:
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

            if empresa is not None:
                configured_ids = {str(item) for item in (empresa.impuesto_catalogo_ids or [])}
                if str(impuesto.id) not in configured_ids:
                    raise HTTPException(
                        status_code=400,
                        detail="El impuesto no está configurado para la empresa seleccionada.",
                    )
                if not ProductoImpuestoService().impuesto_repo.es_vigente(impuesto):
                    raise HTTPException(status_code=400, detail=f"El impuesto {imp_id} no está vigente.")

            # Validar que no se repita el tipo de impuesto
            tipo_impuesto = impuesto.tipo_impuesto
            if tipo_impuesto in tipos_vistos:
                raise HTTPException(
                    status_code=400,
                    detail=f"Solo se permite un impuesto de tipo {tipo_impuesto.value} por producto."
                )
            tipos_vistos.add(tipo_impuesto)

            if tipo_impuesto not in {TipoImpuesto.IVA, TipoImpuesto.ICE}:
                raise HTTPException(
                    status_code=400,
                    detail="Solo se permiten impuestos IVA e ICE en productos.",
                )

            # Verificar que hay al menos un IVA
            if tipo_impuesto == TipoImpuesto.IVA:
                tiene_iva = True

            # Validar compatibilidad con tipo de producto
            ProductoImpuestoService()._validar_compatibilidad_tipo(tipo_producto, impuesto.aplica_a)

        if not tiene_iva:
            raise HTTPException(
                status_code=400,
                detail="Debe incluir exactamente un impuesto de tipo IVA. Los productos siempre deben tener IVA."
            )

    def create(
        self,
        session: Session,
        data: dict[str, Any],
        *,
        commit: bool = True,
    ) -> Producto:
        try:
            def _val(obj: dict[str, Any] | None, key: str) -> Any:
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
            tipo_producto = _val(data, "tipo") or TipoProducto.BIEN
            empresa_perfil = None
            if impuesto_ids:
                empresa_perfil = resolve_product_tax_company(session)
                self._validate_impuestos(session, impuesto_ids, tipo_producto, empresa_perfil)

            prod = super().create(session, data, commit=False)
            pid = prod.id
            if isinstance(session, Session):
                record_domain_change(
                    session,
                    entity="tbl_producto",
                    entity_id=pid,
                    action="CREATE_PRODUCT",
                    before={},
                    after={
                        "nombre": prod.nombre,
                        "tipo": prod.tipo.value if hasattr(prod.tipo, "value") else str(prod.tipo),
                        "pvp": str(prod.pvp),
                        "categoria_ids": [str(category_id) for category_id in categoria_ids or []],
                    },
                )

            # asociaciones
            if categoria_ids:
                self.repo.set_categorias(session, pid, categoria_ids)
                if isinstance(session, Session):
                    from osiris.modules.inventario.producto.service_atributos import ProductoAtributoValorService

                    ProductoAtributoValorService().upsert_valores_producto_validando_aplicabilidad(
                        session,
                        pid,
                        [],
                        commit=False,
                    )
            usuario_auditoria = _val(data, "usuario_auditoria")

            # Asociar impuestos automáticamente
            if impuesto_ids:
                assert empresa_perfil is not None
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
                        empresa_id=empresa_perfil.id,
                        impuesto_catalogo_id=imp_id,
                        codigo_impuesto_sri=impuesto.codigo_tipo_impuesto,
                        codigo_porcentaje_sri=impuesto.codigo_sri,
                        tarifa=tarifa,
                        usuario_auditoria=usuario_auditoria
                    )
                    session.add(producto_impuesto)

                if isinstance(session, Session):
                    record_domain_change(
                        session,
                        entity="tbl_producto_impuesto",
                        entity_id=pid,
                        action="CREATE_PRODUCT_TAX_PROFILE",
                        before={"impuesto_catalogo_ids": []},
                        after={
                            "empresa_id": str(empresa_perfil.id),
                            "impuesto_catalogo_ids": [str(tax_id) for tax_id in impuesto_ids],
                        },
                    )

            if commit:
                session.commit()
                session.refresh(prod)
            return prod
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    def update(
        self,
        session: Session,
        item_id: UUID,
        data: dict[str, Any],
        *,
        commit: bool = True,
    ) -> Producto | None:
        try:
            self._asegurar_producto_en_scope(session, item_id)
            product_before = session.get(Producto, item_id) if isinstance(session, Session) else None
            before_state = (
                {
                    "nombre": product_before.nombre,
                    "tipo": product_before.tipo.value if hasattr(product_before.tipo, "value") else str(product_before.tipo),
                    "pvp": str(product_before.pvp),
                    "activo": product_before.activo,
                }
                if product_before is not None
                else {}
            )
            # validar categorías si vienen
            def _val(obj: dict[str, Any] | None, key: str) -> Any:
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

            tipo_producto = _val(data, "tipo")
            impuesto_ids = _val(data, "impuesto_catalogo_ids")
            existing_tax_rows = None
            empresa_perfil = None
            if tipo_producto is not None or impuesto_ids is not None:
                empresa_perfil = resolve_product_tax_company(session, item_id)
                existing_tax_rows = list(
                    session.exec(
                        select(ProductoImpuesto).where(
                            col(ProductoImpuesto.producto_id) == item_id,
                            col(ProductoImpuesto.empresa_id) == empresa_perfil.id,
                            col(ProductoImpuesto.activo).is_(True),
                        )
                    ).all()
                )
                if impuesto_ids is None:
                    impuesto_ids = [row.impuesto_catalogo_id for row in existing_tax_rows]
                if not impuesto_ids:
                    raise HTTPException(
                        status_code=400,
                        detail="El perfil fiscal no puede quedar vacío; asigne un IVA.",
                    )
                if len(set(impuesto_ids)) != len(impuesto_ids):
                    raise HTTPException(status_code=400, detail="El perfil fiscal contiene impuestos duplicados.")
                tipo_validacion = tipo_producto or self.repo.get(session, item_id).tipo
                self._validate_impuestos(session, impuesto_ids, tipo_validacion, empresa_perfil)

            prod: Producto | None = super().update(session, item_id, data, commit=False)
            if prod is None:
                return None
            # asociaciones
            if categoria_ids is not None:
                previous_category_ids = set(
                    session.exec(
                        select(ProductoCategoria.categoria_id).where(
                            ProductoCategoria.producto_id == item_id
                        )
                    ).all()
                )
                self.repo.set_categorias(session, item_id, categoria_ids)
                if isinstance(session, Session):
                    from osiris.modules.inventario.producto.service_atributos import ProductoAtributoValorService

                    ProductoAtributoValorService().upsert_valores_producto_validando_aplicabilidad(
                        session,
                        item_id,
                        [],
                        commit=False,
                    )
                CategoriaService().desactivar_defaults_vacios(session, previous_category_ids)
            if _val(data, "impuesto_catalogo_ids") is not None:
                assert empresa_perfil is not None
                assert existing_tax_rows is not None
                for row in existing_tax_rows:
                    row.activo = False
                    session.add(row)
                session.flush()
                for impuesto_id in impuesto_ids:
                    impuesto = session.get(ImpuestoCatalogo, impuesto_id)
                    if impuesto is None:
                        raise HTTPException(status_code=400, detail=f"Impuesto {impuesto_id} no existe.")
                    session.add(
                        ProductoImpuesto(
                            producto_id=item_id,
                            empresa_id=empresa_perfil.id,
                            impuesto_catalogo_id=impuesto_id,
                            codigo_impuesto_sri=impuesto.codigo_tipo_impuesto,
                            codigo_porcentaje_sri=impuesto.codigo_sri,
                            tarifa=ProductoImpuestoService._resolver_tarifa_principal(impuesto),
                            usuario_auditoria=_val(data, "usuario_auditoria"),
                        )
                    )
                if isinstance(session, Session):
                    record_domain_change(
                        session,
                        entity="tbl_producto_impuesto",
                        entity_id=item_id,
                        action="UPDATE_PRODUCT_TAX_PROFILE",
                        before={
                            "empresa_id": str(empresa_perfil.id),
                            "impuesto_catalogo_ids": [str(row.impuesto_catalogo_id) for row in existing_tax_rows],
                        },
                        after={
                            "empresa_id": str(empresa_perfil.id),
                            "impuesto_catalogo_ids": [str(tax_id) for tax_id in impuesto_ids],
                        },
                    )
            _val(data, "usuario_auditoria")
            if product_before is not None:
                record_domain_change(
                    session,
                    entity="tbl_producto",
                    entity_id=item_id,
                    action="UPDATE_PRODUCT",
                    before=before_state,
                    after={
                        "nombre": prod.nombre,
                        "tipo": prod.tipo.value if hasattr(prod.tipo, "value") else str(prod.tipo),
                        "pvp": str(prod.pvp),
                        "activo": prod.activo,
                    },
                )
            if commit:
                session.commit()
                session.refresh(prod)
            return prod
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    def get(self, session: Session, item_id: UUID) -> Producto:
        prod = super().get(session, item_id)
        if not isinstance(prod, Producto):
            raise NotFoundError("Producto no encontrado")
        self._asegurar_producto_en_scope(session, item_id)
        return prod

    def delete(self, session: Session, item_id: UUID, *, commit: bool = True) -> bool | None:
        from osiris.modules.inventario.movimientos.models import InventarioStock

        try:
            self._asegurar_producto_en_scope(session, item_id)
            product = session.get(Producto, item_id)
            if not product or not product.activo:
                return None

            positive_stock = session.exec(
                select(InventarioStock.id).where(
                    col(InventarioStock.producto_id) == item_id,
                    col(InventarioStock.activo).is_(True),
                    col(InventarioStock.cantidad_actual) > 0,
                ).limit(1)
            ).first()
            if positive_stock is not None or product.cantidad > 0:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "PRODUCT_HAS_STOCK",
                        "message": "No se puede dar de baja un producto con stock positivo.",
                    },
                )

            category_ids = set(
                session.exec(
                    select(ProductoCategoria.categoria_id).where(
                        col(ProductoCategoria.producto_id) == item_id
                    )
                ).all()
            )
            tax_ids = list(
                session.exec(
                    select(ProductoImpuesto.impuesto_catalogo_id).where(
                        col(ProductoImpuesto.producto_id) == item_id,
                        col(ProductoImpuesto.activo).is_(True),
                    )
                ).all()
            )
            for relation_model in (ProductoAtributoValor, ProductoBodega, ProductoImpuesto):
                session.execute(
                    update(relation_model)
                    .where(
                        col(relation_model.producto_id) == item_id,
                        col(relation_model.activo).is_(True),
                    )
                    .values(activo=False, actualizado_en=func.now())
                )

            deleted = super().delete(session, item_id, commit=False)
            record_domain_change(
                session,
                entity="tbl_producto",
                entity_id=item_id,
                action="DELETE_PRODUCT",
                before={
                    "nombre": product.nombre,
                    "activo": True,
                    "impuesto_catalogo_ids": [str(tax_id) for tax_id in tax_ids],
                    "categoria_ids": [str(category_id) for category_id in category_ids],
                },
                after={"activo": False},
            )
            category_columns = {
                column["name"]
                for column in sqlalchemy_inspect(session.connection()).get_columns(
                    Categoria.__tablename__
                )
            }
            if "is_default" in category_columns:
                CategoriaService().desactivar_defaults_vacios(session, category_ids)
            if commit:
                session.commit()
            return deleted
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    def get_with_impuestos(
        self,
        session: Session,
        item_id: UUID,
    ) -> tuple[Producto, list[ImpuestoCatalogo]]:
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

        ruta_parts: list[str] = []
        current_id: UUID | None = categoria_id

        while current_id:
            categoria = session.get(Categoria, current_id)
            if not categoria:
                break
            ruta_parts.insert(0, categoria.nombre)
            current_id = categoria.parent_id

        return " > ".join(ruta_parts)

    @staticmethod
    def _extract_valor_por_tipo(
        tipo_dato: TipoDato | str | None,
        registro: ProductoAtributoValor | None,
    ) -> str | int | Decimal | bool | date | None:
        if registro is None:
            return None

        tipo = tipo_dato.value if isinstance(tipo_dato, TipoDato) else tipo_dato
        tipo_normalizado = str(tipo).lower() if tipo is not None else ""

        if tipo_normalizado in {"string", "select", "catalog"}:
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
        esqueleto: list[dict[str, Any]],
        valores_por_atributo: dict[UUID, Any],
    ) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        for item in esqueleto:
            atributo_id = item["atributo_id"]
            tipo_dato = item.get("tipo_dato")
            tipo_dato_val = tipo_dato.value if isinstance(tipo_dato, TipoDato) else tipo_dato
            merged.append(
                {
                    "atributo": {
                        "id": atributo_id,
                        "nombre": item["atributo_nombre"],
                        "tipo_dato": tipo_dato_val,
                        "select_options": item.get("select_options"),
                        "catalog_id": item.get("catalog_id"),
                        "allow_negative": item.get("allow_negative", False),
                        "min_value": item.get("min_value"),
                        "max_value": item.get("max_value"),
                    },
                    "valor": valores_por_atributo.get(atributo_id),
                    "obligatorio": item.get("obligatorio"),
                    "orden": item.get("orden"),
                }
            )
        return merged

    def get_producto_completo(self, session: Session, producto_id: UUID) -> dict[str, Any]:
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
                        "id": prov.id,
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
            proveedor_sociedad = session.get(ProveedorSociedad, prov_id)
            if proveedor_sociedad:
                proveedores_sociedad.append({
                    "id": proveedor_sociedad.id,
                    "razon_social": proveedor_sociedad.razon_social,
                    "nombre_comercial": getattr(proveedor_sociedad, "nombre_comercial", None)
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

        # Impuestos deben pertenecer al perfil de la empresa resuelta.
        impuestos = []
        impuesto_service = ProductoImpuestoService()
        impuestos_raw = impuesto_service.get_impuestos_completos(session, producto_id)
        for imp in impuestos_raw:
            raw_porcentaje = imp.porcentaje_iva or imp.tarifa_ad_valorem or Decimal("0.00")
            porcentaje_val = raw_porcentaje if isinstance(raw_porcentaje, Decimal) else Decimal(str(raw_porcentaje))
            impuestos.append({
                "id": imp.id,
                "tipo_impuesto": imp.tipo_impuesto.value,
                "nombre": imp.descripcion,
                "codigo": imp.codigo_sri,
                "porcentaje": porcentaje_val,
            })

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

    def list_paginated_completo(
        self,
        session: Session,
        only_active: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], PaginationMeta]:
        """
        Lista paginada liviana de productos (metadata básica).
        La resolución de jerarquía de atributos se reserva para GET /productos/{id}.
        """
        stmt_base = select(Producto)
        empresa_scope = self._empresa_scope()
        if empresa_scope is not None:
            stmt_base = (
                stmt_base
                .join(
                    ProductoBodega,
                    col(ProductoBodega.producto_id) == col(Producto.id),
                )
                .join(Bodega, col(Bodega.id) == col(ProductoBodega.bodega_id))
                .where(
                    col(ProductoBodega.activo).is_(True),
                    col(Bodega.activo).is_(True),
                    col(Bodega.empresa_id) == empresa_scope,
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
        product_ids = [producto.id for producto in productos]
        categorias_por_producto: dict[UUID, list[dict[str, object]]] = {}
        if product_ids:
            categoria_rows = session.exec(
                select(ProductoCategoria.producto_id, Categoria.id, Categoria.nombre)
                .join(Categoria, col(Categoria.id) == col(ProductoCategoria.categoria_id))
                .where(
                    col(ProductoCategoria.producto_id).in_(product_ids),
                    col(Categoria.activo).is_(True),
                )
                .order_by(col(Categoria.nombre).asc())
            ).all()
            for producto_id, categoria_id, categoria_nombre in categoria_rows:
                categorias_por_producto.setdefault(producto_id, []).append(
                    {"id": categoria_id, "nombre": categoria_nombre}
                )

        items = [
            {
                "id": producto.id,
                "nombre": producto.nombre,
                "tipo": producto.tipo,
                "pvp": producto.pvp,
                "cantidad": producto.cantidad,
                "categorias": categorias_por_producto.get(producto.id, []),
            }
            for producto in productos
        ]
        return items, meta

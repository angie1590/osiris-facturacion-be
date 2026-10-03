from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, col, select

from osiris.core.audit import record_domain_change
from osiris.modules.inventario.atributo.entity import Atributo
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.inventario.producto.entity import Producto
from osiris.modules.inventario.producto.models_atributos import (
    ProductoAtributoRemapeo,
    ProductoAtributoRemapeoResolve,
    ProductoAtributoValorUpsert,
)
from osiris.modules.inventario.producto.service_atributos import ProductoAtributoValorService


class AtributoRemapeoService:
    def listar_pendientes(self, session: Session) -> dict[str, Any]:
        rows = session.exec(
            select(ProductoAtributoRemapeo, Producto, Atributo)
            .join(Producto, col(Producto.id) == col(ProductoAtributoRemapeo.producto_id))
            .join(Atributo, col(Atributo.id) == col(ProductoAtributoRemapeo.atributo_id))
            .where(
                col(ProductoAtributoRemapeo.activo).is_(True),
                col(Producto.activo).is_(True),
                col(Atributo.activo).is_(True),
            )
            .order_by(Atributo.nombre, Producto.nombre)
        ).all()
        groups: dict[UUID, dict[str, Any]] = {}
        for remap, product, attribute in rows:
            group = groups.setdefault(
                attribute.id,
                {
                    "attribute_id": attribute.id,
                    "attribute_name": attribute.nombre,
                    "target_type": attribute.tipo_dato.value,
                    "is_required": False,
                    "catalog_id": attribute.catalog_id,
                    "allowed_values": attribute.select_options,
                    "items": [],
                },
            )
            mappings = session.exec(
                select(CategoriaAtributo.obligatorio).where(
                    col(CategoriaAtributo.atributo_id) == attribute.id,
                    col(CategoriaAtributo.activo).is_(True),
                )
            ).all()
            group["is_required"] = any(value is True for value in mappings)
            group["items"].append(
                {
                    "id": remap.id,
                    "product_id": product.id,
                    "product_name": product.nombre,
                    "old_value": remap.valor_anterior.get("value"),
                    "reason": remap.motivo,
                }
            )
        return {"total": sum(len(group["items"]) for group in groups.values()), "groups": list(groups.values())}

    def resolver(self, session: Session, assignments: list[ProductoAtributoRemapeoResolve]) -> dict[str, int]:
        if not assignments:
            raise HTTPException(status_code=400, detail="Asigne un valor a al menos un remapeo.")
        remap_ids = [assignment.id for assignment in assignments]
        if len(remap_ids) != len(set(remap_ids)):
            raise HTTPException(status_code=400, detail="La solicitud contiene remapeos duplicados.")

        value_service = ProductoAtributoValorService()
        try:
            for assignment in assignments:
                remap = session.get(ProductoAtributoRemapeo, assignment.id)
                if not remap or not remap.activo:
                    raise HTTPException(status_code=404, detail=f"Remapeo {assignment.id} no encontrado o resuelto.")
                attribute = session.get(Atributo, remap.atributo_id)
                product = session.get(Producto, remap.producto_id)
                if not attribute or not attribute.activo or attribute.tipo_dato.value != remap.tipo_nuevo:
                    raise HTTPException(status_code=409, detail="El tipo de atributo cambió desde que se generó el remapeo.")
                if not product or not product.activo:
                    raise HTTPException(status_code=404, detail="Producto del remapeo no encontrado o inactivo.")

                value_service.upsert_valores_producto_validando_aplicabilidad(
                    session,
                    product.id,
                    [ProductoAtributoValorUpsert(atributo_id=attribute.id, valor=assignment.valor)],
                    commit=False,
                )
                before = {
                    "valor_anterior": remap.valor_anterior,
                    "tipo_anterior": remap.tipo_anterior,
                    "tipo_nuevo": remap.tipo_nuevo,
                }
                remap.activo = False
                session.add(remap)
                record_domain_change(
                    session,
                    entity="tbl_producto_atributo_remapeo",
                    entity_id=remap.id,
                    action="RESOLVE_ATTRIBUTE_REMAP",
                    before=before,
                    after={
                        "producto_id": str(product.id),
                        "atributo_id": str(attribute.id),
                        "valor": assignment.valor,
                        "activo": False,
                    },
                )
            session.commit()
            return {"resolved": len(assignments)}
        except Exception as exc:
            session.rollback()
            raise exc
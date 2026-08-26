# src/osiris/modules/inventario/producto_bodega/service.py
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from uuid import UUID
from sqlmodel import Session, select
from fastapi import HTTPException

from osiris.domain.service import BaseService
from osiris.modules.inventario.movimientos.models import InventarioStock
from osiris.modules.inventario.producto.entity import Producto, ProductoBodega
from osiris.modules.inventario.bodega.entity import Bodega
from .repository import ProductoBodegaRepository


class ProductoBodegaService(BaseService):
    repo = ProductoBodegaRepository()

    # FKs a validar: producto y bodega deben existir y estar activos
    fk_models = {
        "producto_id": Producto,
        "bodega_id": Bodega,
    }
    Q4 = Decimal("0.0001")

    @classmethod
    def _to_q4(cls, value: Decimal | int | float | str) -> Decimal:
        try:
            result = Decimal(str(value)).quantize(cls.Q4)
        except (InvalidOperation, ValueError):
            raise HTTPException(status_code=400, detail="Cantidad inválida.")
        if result < Decimal("0.0000"):
            raise HTTPException(status_code=400, detail="La cantidad no puede ser negativa.")
        return result

    @staticmethod
    def _validar_producto_y_bodega_activos(session: Session, producto_id: UUID, bodega_id: UUID) -> tuple[Producto, Bodega]:
        producto = session.get(Producto, producto_id)
        if not producto or not producto.activo:
            raise HTTPException(status_code=404, detail="Producto no encontrado o inactivo.")

        bodega = session.get(Bodega, bodega_id)
        if not bodega or not bodega.activo:
            raise HTTPException(status_code=409, detail="No se puede operar con una bodega inactiva.")

        return producto, bodega

    @classmethod
    def _validar_fracciones_producto(cls, producto: Producto, cantidad: Decimal) -> None:
        if not producto.permite_fracciones and cantidad != cantidad.to_integral_value():
            raise HTTPException(
                status_code=400,
                detail=(
                    "El producto no permite fracciones. "
                    "La cantidad debe ser un valor entero."
                ),
            )

    @staticmethod
    def _is_service_product(producto: Producto | None) -> bool:
        if producto is None:
            return False

        tipo = getattr(producto, "tipo", None)
        if tipo is None:
            return False

        # Soporta enums (TipoProducto.SERVICIO) y strings ("SERVICIO")
        return getattr(tipo, "value", tipo) == "SERVICIO"

    def create(self, session: Session, data):
        """
        Crea una relación producto-bodega.
        Valida que no exista duplicado (constraint único en BD).
        """
        producto_id = data.get("producto_id")
        bodega_id = data.get("bodega_id")
        cantidad = self._to_q4(data.get("cantidad", Decimal("0.0000")))
        data["cantidad"] = cantidad

        # Validar si ya existe la relación
        existing = session.exec(
            select(ProductoBodega)
            .where(ProductoBodega.producto_id == producto_id)
            .where(ProductoBodega.bodega_id == bodega_id)
        ).first()

        if existing:
            raise HTTPException(
                status_code=409,
                detail="El producto ya está asignado a la bodega especificada."
            )

        producto, _ = self._validar_producto_y_bodega_activos(session, producto_id, bodega_id)
        self._validar_fracciones_producto(producto, cantidad)

        # Regla de negocio: Productos de tipo SERVICIO no pueden tener stock (> 0) ni asignaciones a bodegas con cantidad positiva
        if self._is_service_product(producto) and cantidad > 0:
            raise HTTPException(
                status_code=400,
                detail="Los servicios no pueden tener stock en bodegas.",
            )

        # Alternativamente, si el producto existe y es SERVICIO, forzar cantidad = 0
        if self._is_service_product(producto):
            data["cantidad"] = Decimal("0.0000")

        return super().create(session, data)

    def update_cantidad(
        self,
        session: Session,
        producto_id: UUID,
        bodega_id: UUID,
        cantidad: Decimal | int | float | str,
        *,
        usuario_auditoria: str | None = None,
    ):
        """
        Actualiza la cantidad de un producto en una bodega específica.
        Si no existe la relación, la crea.
        """
        cantidad_q4 = self._to_q4(cantidad)
        producto, _ = self._validar_producto_y_bodega_activos(session, producto_id, bodega_id)
        self._validar_fracciones_producto(producto, cantidad_q4)

        # Regla de negocio: Productos de tipo SERVICIO no pueden tener stock (> 0)
        if self._is_service_product(producto) and cantidad_q4 > 0:
            raise HTTPException(status_code=400, detail="Los servicios no pueden tener stock.")

        relacion = session.exec(
            select(ProductoBodega)
            .where(ProductoBodega.producto_id == producto_id)
            .where(ProductoBodega.bodega_id == bodega_id)
        ).first()

        if not relacion:
            # Crear nueva relación
            relacion = ProductoBodega(
                producto_id=producto_id,
                bodega_id=bodega_id,
                cantidad=cantidad_q4,
                usuario_auditoria=usuario_auditoria,
            )
            session.add(relacion)
        else:
            # Actualizar cantidad existente
            relacion.cantidad = cantidad_q4
            if usuario_auditoria:
                relacion.usuario_auditoria = usuario_auditoria
            session.add(relacion)

        session.commit()
        session.refresh(relacion)
        return relacion

    def get_stock_disponible(
        self,
        session: Session,
        *,
        producto_id: UUID | None = None,
        bodega_id: UUID | None = None,
    ) -> list[dict]:
        if producto_id is None and bodega_id is None:
            raise HTTPException(
                status_code=400,
                detail="Debe enviar al menos producto_id o bodega_id para consultar stock disponible.",
            )

        stmt = (
            select(InventarioStock, Producto, Bodega)
            .join(Producto, Producto.id == InventarioStock.producto_id)
            .join(Bodega, Bodega.id == InventarioStock.bodega_id)
            .where(
                InventarioStock.activo.is_(True),
                Producto.activo.is_(True),
                Bodega.activo.is_(True),
            )
        )
        if producto_id is not None:
            stmt = stmt.where(InventarioStock.producto_id == producto_id)
        if bodega_id is not None:
            stmt = stmt.where(InventarioStock.bodega_id == bodega_id)

        relaciones = session.exec(stmt).all()
        return [
            {
                "producto_id": producto.id,
                "producto_nombre": producto.nombre,
                "bodega_id": bodega.id,
                "codigo_bodega": bodega.codigo_bodega,
                "nombre_bodega": bodega.nombre_bodega,
                "cantidad_disponible": rel.cantidad_actual,
            }
            for rel, producto, bodega in relaciones
        ]

    def get_bodegas_by_producto(self, session: Session, producto_id: UUID):
        """Obtiene todas las bodegas donde está un producto"""
        relaciones = session.exec(
            select(ProductoBodega, Bodega)
            .join(Bodega, Bodega.id == ProductoBodega.bodega_id)
            .where(
                ProductoBodega.producto_id == producto_id,
                ProductoBodega.activo.is_(True),
                Bodega.activo.is_(True),
            )
        ).all()

        return [
            {
                "id": rel.id,
                "bodega_id": bodega.id,
                "codigo_bodega": bodega.codigo_bodega,
                "nombre_bodega": bodega.nombre_bodega,
                "cantidad": rel.cantidad,
            }
            for rel, bodega in relaciones
        ]

    def get_productos_by_bodega(self, session: Session, bodega_id: UUID):
        """Obtiene todos los productos en una bodega"""
        relaciones = session.exec(
            select(ProductoBodega, Producto)
            .join(Producto, Producto.id == ProductoBodega.producto_id)
            .where(
                ProductoBodega.bodega_id == bodega_id,
                ProductoBodega.activo.is_(True),
                Producto.activo.is_(True),
            )
        ).all()

        return [
            {
                "id": rel.id,
                "producto_id": producto.id,
                "nombre": producto.nombre,
                "cantidad": rel.cantidad,
            }
            for rel, producto in relaciones
        ]

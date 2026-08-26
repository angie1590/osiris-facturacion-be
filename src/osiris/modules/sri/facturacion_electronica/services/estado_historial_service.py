from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session

from osiris.modules.sri.core_sri.models import (
    Compra,
    CompraEstadoHistorial,
    EstadoCompra,
    EstadoVenta,
    Venta,
    VentaEstadoHistorial,
)


class EstadoHistorialService:
    def actualizar_estado_compra(
        self,
        session: Session,
        compra_id: UUID,
        estado_nuevo: EstadoCompra | str,
        *,
        usuario_id: str | None = None,
        motivo_cambio: str | None = None,
    ) -> Compra:
        compra = session.get(Compra, compra_id)
        if not compra or not compra.activo:
            raise HTTPException(status_code=404, detail="Compra no encontrada")

        destino = estado_nuevo if isinstance(estado_nuevo, EstadoCompra) else EstadoCompra(estado_nuevo)
        anterior = compra.estado.value if isinstance(compra.estado, EstadoCompra) else str(compra.estado)
        motivo = (motivo_cambio or "").strip() or f"Transicion de estado {anterior} -> {destino.value}"

        compra.estado = destino
        session.add(compra)
        session.add(
            CompraEstadoHistorial(
                entidad_id=compra.id,
                estado_anterior=anterior,
                estado_nuevo=destino.value,
                motivo_cambio=motivo,
                usuario_id=usuario_id,
            )
        )
        session.commit()
        session.refresh(compra)
        return compra

    def anular_venta(
        self,
        session: Session,
        venta_id: UUID,
        *,
        usuario_id: str | None = None,
        motivo_cambio: str,
    ) -> Venta:
        motivo = (motivo_cambio or "").strip()
        if not motivo:
            raise ValueError("motivo_cambio es obligatorio para anular una venta ante el SRI")

        venta = session.get(Venta, venta_id)
        if not venta or not venta.activo:
            raise HTTPException(status_code=404, detail="Venta no encontrada")

        anterior = venta.estado.value if isinstance(venta.estado, EstadoVenta) else str(venta.estado)
        venta.estado = EstadoVenta.ANULADA
        venta.activo = False
        session.add(venta)
        session.add(
            VentaEstadoHistorial(
                entidad_id=venta.id,
                estado_anterior=anterior,
                estado_nuevo=EstadoVenta.ANULADA.value,
                motivo_cambio=motivo,
                usuario_id=usuario_id,
            )
        )
        session.commit()
        session.refresh(venta)
        return venta

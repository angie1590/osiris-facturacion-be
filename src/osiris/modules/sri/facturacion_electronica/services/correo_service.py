from __future__ import annotations

import threading
from typing import Callable
from uuid import UUID
from sqlalchemy.engine import Engine


class CorreoFacturaService:
    """Worker simple de correo para adjuntar XML/RIDE (mock en MVP)."""

    def __init__(self, db_engine: Engine | None = None) -> None:
        self.db_engine = db_engine

    def encolar_envio_factura(
        self,
        venta_id: UUID,
        *,
        scheduler: Callable[[UUID], None] | None = None,
    ) -> None:
        if scheduler is not None:
            scheduler(venta_id)
            return

        timer = threading.Timer(
            0,
            self.enviar_correo_factura,
            kwargs={"venta_id": venta_id},
        )
        timer.daemon = True
        timer.start()

    def enviar_correo_factura(self, venta_id: UUID) -> dict[str, str | bool | list[str]]:
        # MVP: envío mockeado. En etapas futuras se integra SMTP/provider real.
        return {
            "venta_id": str(venta_id),
            "enviado": True,
            "adjuntos": ["ride.pdf", "factura.xml"],
        }

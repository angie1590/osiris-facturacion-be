from __future__ import annotations

from pydantic import ValidationError

from osiris.modules.sri.core_sri.all_schemas import RetencionRecibidaCreate, q2
from osiris.modules.sri.core_sri.models import Venta


class ValidacionImpuestosSRIStrategy:
    """
    Encapsula la validación tributaria SRI para retenciones recibidas
    usando el contexto de la factura de venta.
    """

    @staticmethod
    def validar_retencion_recibida(payload: RetencionRecibidaCreate, venta: Venta) -> RetencionRecibidaCreate:
        subtotal_general = q2(
            venta.subtotal_12 + venta.subtotal_15 + venta.subtotal_0 + venta.subtotal_no_objeto
        )
        try:
            return RetencionRecibidaCreate.model_validate(
                payload.model_dump(),
                context={
                    "venta_subtotal_general": subtotal_general,
                    "venta_monto_iva": q2(venta.monto_iva),
                },
            )
        except ValidationError as exc:
            first_error = exc.errors()[0]["msg"] if exc.errors() else str(exc)
            raise ValueError(first_error) from exc

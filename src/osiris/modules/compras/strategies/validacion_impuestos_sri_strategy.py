from __future__ import annotations

from decimal import Decimal

from osiris.modules.sri.core_sri.models import Compra
from osiris.modules.sri.core_sri.all_schemas import q2


class ValidacionImpuestosSRIStrategy:
    """
    Strategy de soporte para reglas tributarias de compras/retenciones emitidas.
    Mantiene el mismo cálculo vigente del sistema.
    """

    @staticmethod
    def base_retencion_iva(compra: Compra) -> Decimal:
        return q2(compra.monto_iva)

    @staticmethod
    def base_retencion_renta(compra: Compra) -> Decimal:
        return q2(compra.subtotal_sin_impuestos)

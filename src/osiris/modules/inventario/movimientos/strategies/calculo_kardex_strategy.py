from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


Q4 = Decimal("0.0001")


def q4(value: Decimal | int | str) -> Decimal:
    return Decimal(str(value)).quantize(Q4, rounding=ROUND_HALF_UP)


class CalculoKardexStrategy:
    """
    Aísla la valoración NIIF por promedio ponderado y el congelamiento
    de costo en egresos.
    """

    @staticmethod
    def calcular_nuevo_costo_promedio(
        *,
        cantidad_actual: Decimal,
        costo_promedio_actual: Decimal,
        cantidad_ingresada: Decimal,
        costo_nuevo: Decimal,
    ) -> Decimal:
        denominador = q4(cantidad_actual + cantidad_ingresada)
        if denominador <= Decimal("0"):
            raise ValueError("Cantidad resultante invalida para ingreso.")
        return q4(
            ((q4(cantidad_actual) * q4(costo_promedio_actual)) + (q4(cantidad_ingresada) * q4(costo_nuevo)))
            / denominador
        )

    @staticmethod
    def congelar_costo_egreso(costo_promedio_vigente: Decimal) -> Decimal:
        return q4(costo_promedio_vigente)

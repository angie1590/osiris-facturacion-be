from typing import NamedTuple
from uuid import NAMESPACE_URL, UUID, uuid5

from osiris.modules.common.unidad.entity import Unidad


def unidad_seed_id(codigo: str) -> UUID:
    return uuid5(NAMESPACE_URL, "osiris:unidad:" + codigo)


class UnidadSeed(NamedTuple):
    codigo: str
    nombre: str
    simbolo: str
    magnitud_codigo: str

    @property
    def id(self) -> UUID:
        return unidad_seed_id(self.codigo)


UNIDADES_SISTEMA: tuple[UnidadSeed, ...] = (
    UnidadSeed("UNIDAD", "Unidad", "u", "COUNT"),
    UnidadSeed("GRAMO", "Gramo", "g", "MASS"),
    UnidadSeed("KILOGRAMO", "Kilogramo", "kg", "MASS"),
    UnidadSeed("LIBRA", "Libra", "lb", "MASS"),
    UnidadSeed("MILILITRO", "Mililitro", "mL", "VOLUME"),
    UnidadSeed("LITRO", "Litro", "L", "VOLUME"),
    UnidadSeed("MILIMETRO", "Mil\u00edmetro", "mm", "LENGTH"),
    UnidadSeed("CENTIMETRO", "Cent\u00edmetro", "cm", "LENGTH"),
    UnidadSeed("METRO", "Metro", "m", "LENGTH"),
    UnidadSeed("PULGADA", "Pulgada", "in", "LENGTH"),
    UnidadSeed("SEGUNDO", "Segundo", "s", "TIME"),
    UnidadSeed("MINUTO", "Minuto", "min", "TIME"),
    UnidadSeed("HORA", "Hora", "h", "TIME"),
    UnidadSeed("MEGABYTE", "Megabyte", "MB", "DATA_STORAGE"),
    UnidadSeed("GIGABYTE", "Gigabyte", "GB", "DATA_STORAGE"),
    UnidadSeed("TERABYTE", "Terabyte", "TB", "DATA_STORAGE"),
    UnidadSeed("MEBIBYTE", "Mebibyte", "MiB", "DATA_STORAGE"),
    UnidadSeed("GIBIBYTE", "Gibibyte", "GiB", "DATA_STORAGE"),
    UnidadSeed("MEGAHERCIO", "Megahercio", "MHz", "FREQUENCY"),
    UnidadSeed("GIGAHERCIO", "Gigahercio", "GHz", "FREQUENCY"),
    UnidadSeed("PUNTOS_POR_PULGADA", "Puntos por pulgada", "dpi", "RESOLUTION_DENSITY"),
    UnidadSeed("PORCENTAJE", "Porcentaje", "%", "PERCENTAGE"),
)


def crear_unidades_sistema() -> tuple[Unidad, ...]:
    return tuple(
        Unidad(id=seed.id, **seed._asdict(), es_sistema=True, activo=True)
        for seed in UNIDADES_SISTEMA
    )

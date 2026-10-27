import json
from collections.abc import Iterator
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
from pydantic import ValidationError
from sqlalchemy import Connection, create_engine, insert, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateIndex, CreateTable
from sqlmodel import Session

from osiris.modules.common.unidad.entity import Unidad
from osiris.modules.common.unidad.models import UnidadCreate, UnidadRead, UnidadUpdate
from osiris.modules.common.unidad.seeds import (
    UNIDADES_SISTEMA,
    crear_unidades_sistema,
    unidad_seed_id,
)


@pytest.fixture
def conexion() -> Iterator[Connection]:
    engine = create_engine("sqlite://")
    Unidad.__table__.create(engine)
    with engine.begin() as connection:
        yield connection
    engine.dispose()


def datos_unidad() -> dict[str, str]:
    return {
        "codigo": "MEGABYTE",
        "nombre": "Megabyte",
        "simbolo": "MB",
        "magnitud_codigo": "DATA_STORAGE",
    }


def test_simbolos_exactos_y_codigo_normalizado_global(conexion: Connection) -> None:
    tabla = Unidad.__table__
    conexion.execute(insert(tabla).values(**datos_unidad(), activo=False))
    conexion.execute(
        insert(tabla).values(**{**datos_unidad(), "codigo": "MEGABIT", "simbolo": "Mb"})
    )
    assert conexion.execute(select(tabla.c.simbolo).order_by(tabla.c.simbolo)).scalars().all() == [
        "MB",
        "Mb",
    ]
    for codigo in ("megabyte", " Megabyte ", "MEGABYTE"):
        with pytest.raises(IntegrityError, match="uq_tbl_unidad_codigo_normalizado"):
            conexion.execute(
                insert(tabla).values(**{**datos_unidad(), "codigo": codigo, "simbolo": "otro"})
            )
    with pytest.raises(IntegrityError, match="simbolo"):
        conexion.execute(insert(tabla).values(**{**datos_unidad(), "codigo": "OTRO"}))


@pytest.mark.parametrize("campo", ["codigo", "nombre", "simbolo", "magnitud_codigo"])
@pytest.mark.parametrize("valor", ["", " ", "\t\n\r", None, 123, True])
@pytest.mark.parametrize("modelo", [UnidadCreate, UnidadUpdate])
def test_dto_rechaza_campos_invalidos(
    campo: str, valor: object, modelo: type[UnidadCreate] | type[UnidadUpdate]
) -> None:
    datos: dict[str, object] = dict(datos_unidad()) if modelo is UnidadCreate else {}
    datos[campo] = valor
    with pytest.raises(ValidationError):
        modelo.model_validate(datos)


@pytest.mark.parametrize(
    "campo,limite", [("codigo", 64), ("nombre", 120), ("simbolo", 32), ("magnitud_codigo", 64)]
)
@pytest.mark.parametrize("modelo", [UnidadCreate, UnidadUpdate])
def test_dto_limites(
    campo: str, limite: int, modelo: type[UnidadCreate] | type[UnidadUpdate]
) -> None:
    datos: dict[str, object] = dict(datos_unidad()) if modelo is UnidadCreate else {}
    datos[campo] = "x" * (limite + 1)
    with pytest.raises(ValidationError):
        modelo.model_validate(datos)


@pytest.mark.parametrize(
    "campo,limite", [("codigo", 64), ("nombre", 120), ("simbolo", 32), ("magnitud_codigo", 64)]
)
@pytest.mark.parametrize("valor", ["", " ", "\t\n\r", None, "demasiado_largo"])
def test_db_not_null_blancos_y_longitud(
    conexion: Connection, campo: str, limite: int, valor: str | None
) -> None:
    datos: dict[str, object] = dict(datos_unidad())
    datos[campo] = "x" * (limite + 1) if valor == "demasiado_largo" else valor
    with pytest.raises(IntegrityError):
        conexion.execute(insert(Unidad.__table__).values(**datos))


@pytest.mark.parametrize(
    "campo",
    [
        "es_sistema",
        "activo",
        "usuario_auditoria",
        "created_by",
        "updated_by",
        "id",
        "empresa_id",
        "desconocido",
    ],
)
@pytest.mark.parametrize("modelo", [UnidadCreate, UnidadUpdate])
def test_dto_no_admite_bypass(campo: str, modelo: type[UnidadCreate] | type[UnidadUpdate]) -> None:
    datos: dict[str, object] = dict(datos_unidad()) if modelo is UnidadCreate else {}
    datos[campo] = True
    with pytest.raises(ValidationError) as error:
        modelo.model_validate(datos)
    assert error.value.errors()[0]["type"] == "extra_forbidden"


def test_normalizacion_idempotente_sin_forzar_case() -> None:
    datos = {campo: f"  {valor}  " for campo, valor in datos_unidad().items()}
    datos["codigo"] = "  MegaByte  "
    dto = UnidadCreate.model_validate(datos)
    assert dto.codigo == "MegaByte"
    assert dto.simbolo == "MB"
    assert UnidadCreate.model_validate(dto.model_dump()) == dto
    assert UnidadCreate.model_validate({**datos_unidad(), "simbolo": "Mb"}).simbolo == "Mb"
    for codigo in ("MEGA BYTE", "MEGA\tBYTE", "MEGA\nBYTE"):
        with pytest.raises(ValidationError):
            UnidadCreate.model_validate({**datos_unidad(), "codigo": codigo})
    assert UnidadUpdate().model_dump(exclude_unset=True) == {}
    assert UnidadUpdate(nombre="  Memoria  ").model_dump(exclude_unset=True) == {
        "nombre": "Memoria"
    }


def test_read_orm_y_json_uuid_real(conexion: Connection) -> None:
    with Session(bind=conexion) as session:
        unidad = Unidad(**datos_unidad())
        assert unidad.es_sistema is False
        session.add(unidad)
        session.flush()
        session.expire_all()
        almacenada = session.get(Unidad, unidad.id)
        assert almacenada is not None
        dto = UnidadRead.model_validate(almacenada)
        assert isinstance(dto.id, UUID)
        assert isinstance(dto.creado_en, datetime)
        payload = json.loads(dto.model_dump_json())
        assert payload["id"] == str(unidad.id)
        assert payload["simbolo"] == "MB"
        assert payload["es_sistema"] is False
        assert payload["activo"] is True
        assert UnidadRead.model_validate_json(dto.model_dump_json()) == dto
        with pytest.raises(ValidationError):
            UnidadRead.model_validate({**dto.model_dump(), "inesperado": 1})


def test_seed_v2_completo_inmutable_ids_estables() -> None:
    esperado = (
        ("UNIDAD", "Unidad", "u", "COUNT"),
        ("GRAMO", "Gramo", "g", "MASS"),
        ("KILOGRAMO", "Kilogramo", "kg", "MASS"),
        ("LIBRA", "Libra", "lb", "MASS"),
        ("MILILITRO", "Mililitro", "mL", "VOLUME"),
        ("LITRO", "Litro", "L", "VOLUME"),
        ("MILIMETRO", "Mil\u00edmetro", "mm", "LENGTH"),
        ("CENTIMETRO", "Cent\u00edmetro", "cm", "LENGTH"),
        ("METRO", "Metro", "m", "LENGTH"),
        ("PULGADA", "Pulgada", "in", "LENGTH"),
        ("SEGUNDO", "Segundo", "s", "TIME"),
        ("MINUTO", "Minuto", "min", "TIME"),
        ("HORA", "Hora", "h", "TIME"),
        ("MEGABYTE", "Megabyte", "MB", "DATA_STORAGE"),
        ("GIGABYTE", "Gigabyte", "GB", "DATA_STORAGE"),
        ("TERABYTE", "Terabyte", "TB", "DATA_STORAGE"),
        ("MEBIBYTE", "Mebibyte", "MiB", "DATA_STORAGE"),
        ("GIBIBYTE", "Gibibyte", "GiB", "DATA_STORAGE"),
        ("MEGAHERCIO", "Megahercio", "MHz", "FREQUENCY"),
        ("GIGAHERCIO", "Gigahercio", "GHz", "FREQUENCY"),
        ("PUNTOS_POR_PULGADA", "Puntos por pulgada", "dpi", "RESOLUTION_DENSITY"),
        ("PORCENTAJE", "Porcentaje", "%", "PERCENTAGE"),
    )
    assert isinstance(UNIDADES_SISTEMA, tuple)
    assert UNIDADES_SISTEMA == esperado
    primera = crear_unidades_sistema()
    segunda = crear_unidades_sistema()
    assert len({unidad.id for unidad in primera}) == 22
    for seed, unidad, repetida in zip(UNIDADES_SISTEMA, primera, segunda):
        assert isinstance(seed, tuple)
        assert unidad.id == repetida.id == uuid5(NAMESPACE_URL, "osiris:unidad:" + seed.codigo)
        assert unidad.id == unidad_seed_id(seed.codigo)
        assert unidad is not repetida
        assert unidad.es_sistema is True and unidad.activo is True
        assert UnidadCreate.model_validate(seed._asdict()).codigo == seed.codigo
    primera[0].nombre = "Otra etiqueta"
    assert segunda[0].nombre == UNIDADES_SISTEMA[0].nombre == "Unidad"


@pytest.mark.parametrize("nombre,colacion", [("sqlite", "BINARY"), ("postgresql", "C")])
def test_ddl_portable_indices_y_simbolo_binario(nombre: str, colacion: str) -> None:
    dialecto = make_url(f"{nombre}://").get_dialect()()
    tabla = Unidad.__table__
    ddl = str(CreateTable(tabla).compile(dialect=dialecto))
    assert f'COLLATE "{colacion}"' in ddl
    indices = {
        str(indice.name): str(CreateIndex(indice).compile(dialect=dialecto))
        for indice in tabla.indexes
    }
    normalized_code = (
        "lower(trim(codigo))"
        if nombre == "sqlite"
        else "lower(TRIM(BOTH FROM codigo))"
    )
    assert normalized_code in indices["uq_tbl_unidad_codigo_normalizado"]
    assert "UNIQUE INDEX" in indices["uq_tbl_unidad_codigo_normalizado"]
    assert "UNIQUE INDEX" in indices["uq_tbl_unidad_simbolo_exacto"]
    assert "WHERE" not in indices["uq_tbl_unidad_codigo_normalizado"]

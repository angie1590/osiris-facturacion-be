import pytest
from osiris.utils.validacion_identificacion import ValidacionCedulaRucService

@pytest.mark.parametrize("identificacion, esperado", [
    ("0104815956", True),               # Cédula válida
    ("0104815956001", True),            # RUC válido de persona natural
    ("0104915956001", False),           # RUC inválido
    ("", False),                        # Vacío
    ("abcdefghij", False),              # No numérico
    ("010203040", False),               # Muy corto
    ("010203040000000", False),            # Largo no válido
])
def test_es_identificacion_valida(identificacion, esperado):
    assert ValidacionCedulaRucService.es_identificacion_valida(identificacion) == esperado


@pytest.mark.parametrize("cedula, esperado", [
    ("0104815956", True),
    ("0102030401", False),
    ("", False),
    ("123", False),
    ("abcdefghij", False)
])
def test_es_cedula_valida(cedula, esperado):
    assert ValidacionCedulaRucService.es_cedula_valida(cedula) == esperado


@pytest.mark.parametrize("ruc, esperado", [
    ("0104815956001", True),   # RUC persona natural válido
    ("0102030400002", False),  # Inválido
])
def test_es_ruc_persona_natural_valido(ruc, esperado):
    assert ValidacionCedulaRucService.es_ruc_persona_natural_valido(ruc) == esperado


@pytest.mark.parametrize("ruc, esperado", [
    ("0190363902001", True),   # RUC sociedad privada válido
    ("1790012345002", False),  # Inválido
])
def test_es_ruc_sociedad_privada_valido(ruc, esperado):
    assert ValidacionCedulaRucService.es_ruc_sociedad_privada_valido(ruc) == esperado


@pytest.mark.parametrize("ruc, esperado", [
    ("0160000270001", True),   # RUC sociedad pública válido
    ("1760001550002", False),  # Inválido
])
def test_es_ruc_sociedad_publica_valido(ruc, esperado):
    assert ValidacionCedulaRucService.es_ruc_sociedad_publica_valido(ruc) == esperado

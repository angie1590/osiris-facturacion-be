"""
Tests unitarios para ImpuestoCatalogo (repository, service)
"""
import pytest
from datetime import date, timedelta
from uuid import uuid4
from unittest.mock import MagicMock
from fastapi import HTTPException

from osiris.modules.sri.impuesto_catalogo.entity import (
    ImpuestoCatalogo,
    TipoImpuesto,
    ClasificacionIVA,
    AplicaA
)
from osiris.modules.sri.impuesto_catalogo.models import ImpuestoCatalogoCreate
from osiris.modules.sri.impuesto_catalogo.repository import ImpuestoCatalogoRepository
from osiris.modules.sri.impuesto_catalogo.service import ImpuestoCatalogoService


# ==================== REPOSITORY TESTS ====================

def test_repo_es_vigente_con_vigente_hasta_null():
    """Un impuesto con vigente_hasta=NULL debe ser vigente"""
    repo = ImpuestoCatalogoRepository()

    # Impuesto vigente (sin fecha de fin)
    impuesto = ImpuestoCatalogo(
        id=uuid4(),
        tipo_impuesto=TipoImpuesto.IVA,
        codigo_tipo_impuesto="2",
        codigo_sri="2",
        descripcion="IVA 15%",
        vigente_desde=date.today() - timedelta(days=365),
        vigente_hasta=None,
        aplica_a=AplicaA.AMBOS,
        porcentaje_iva=15.0,
        clasificacion_iva=ClasificacionIVA.GRAVADO,
        activo=True,
        usuario_auditoria="test_user"
    )

    es_vigente = repo.es_vigente(impuesto, date.today())
    assert es_vigente is True


def test_repo_es_vigente_expirado():
    """Un impuesto con vigente_hasta pasada debe ser NO vigente"""
    repo = ImpuestoCatalogoRepository()

    # Impuesto expirado
    impuesto = ImpuestoCatalogo(
        id=uuid4(),
        tipo_impuesto=TipoImpuesto.IVA,
        codigo_tipo_impuesto="2",
        codigo_sri="2_OLD",
        descripcion="IVA 12% (expirado)",
        vigente_desde=date.today() - timedelta(days=730),
        vigente_hasta=date.today() - timedelta(days=365),
        aplica_a=AplicaA.AMBOS,
        porcentaje_iva=12.0,
        clasificacion_iva=ClasificacionIVA.GRAVADO,
        activo=True,
        usuario_auditoria="test_user"
    )

    es_vigente = repo.es_vigente(impuesto, date.today())
    assert es_vigente is False


def test_repo_validar_duplicado_codigo_sri_detecta_duplicado():
    """Debe lanzar HTTPException cuando la combinación codigo_sri + descripcion ya existe"""
    repo = ImpuestoCatalogoRepository()
    session = MagicMock()

    # Mock que simula que existe un registro con ese codigo_sri + descripcion
    mock_exec = MagicMock()
    mock_exec.first.return_value = ImpuestoCatalogo(
        id=uuid4(),
        tipo_impuesto=TipoImpuesto.IVA,
        codigo_tipo_impuesto="2",
        codigo_sri="2",
        descripcion="IVA 15%",
        vigente_desde=date.today(),
        aplica_a=AplicaA.AMBOS,
        porcentaje_iva=15.0,
        clasificacion_iva=ClasificacionIVA.GRAVADO,
        activo=True,
        usuario_auditoria="test_user"
    )
    session.exec.return_value = mock_exec

    with pytest.raises(HTTPException) as exc_info:
        repo.validar_duplicado_codigo_descripcion(session, codigo_sri="2", descripcion="IVA 15%")
    assert exc_info.value.status_code == 409


def test_repo_validar_duplicado_codigo_sri_no_duplicado():
    """No debe lanzar excepción cuando la combinación codigo_sri + descripcion no existe"""
    repo = ImpuestoCatalogoRepository()
    session = MagicMock()

    # Mock que simula que NO existe
    mock_exec = MagicMock()
    mock_exec.first.return_value = None
    session.exec.return_value = mock_exec

    # No debe lanzar excepción (mismo código pero distinta descripción)
    repo.validar_duplicado_codigo_descripcion(session, codigo_sri="2", descripcion="IVA 0%")


# ==================== SERVICE TESTS ====================

def test_service_create_iva_sin_porcentaje_falla():
    """Crear IVA sin porcentaje_iva debe fallar en validación de modelo"""
    with pytest.raises(ValueError) as exc_info:
        ImpuestoCatalogoCreate(
            tipo_impuesto=TipoImpuesto.IVA,
            codigo_tipo_impuesto="2",
            codigo_sri="IVA_INVALID",
            descripcion="IVA sin porcentaje",
            vigente_desde=date.today(),
            aplica_a=AplicaA.AMBOS,
            usuario_auditoria="test_user"
            # falta porcentaje_iva y clasificacion_iva
        )
    assert "porcentaje_iva es obligatorio" in str(exc_info.value)


def test_service_create_codigo_sri_duplicado_falla():
    """Crear impuesto con codigo_sri + descripcion duplicados debe fallar"""
    service = ImpuestoCatalogoService()
    session = MagicMock()

    # Mock repo que lanza HTTPException para duplicado
    service.repo = MagicMock()
    service.repo.validar_duplicado_codigo_descripcion.side_effect = HTTPException(
        status_code=409,
        detail="La combinación codigo_sri + descripcion ya existe"
    )

    dto = ImpuestoCatalogoCreate(
        tipo_impuesto=TipoImpuesto.IVA,
        codigo_tipo_impuesto="2",
        codigo_sri="2",
        descripcion="IVA duplicado",
        vigente_desde=date.today(),
        aplica_a=AplicaA.AMBOS,
        porcentaje_iva=15.0,
        clasificacion_iva=ClasificacionIVA.GRAVADO,
        usuario_auditoria="test_user"
    )

    with pytest.raises(HTTPException) as exc_info:
        service.create(session, dto)
    assert exc_info.value.status_code == 409


def test_service_validar_vigencia_expirado_falla():
    """validar_vigencia debe lanzar HTTPException para impuesto expirado"""
    service = ImpuestoCatalogoService()

    # Impuesto expirado
    impuesto = ImpuestoCatalogo(
        id=uuid4(),
        tipo_impuesto=TipoImpuesto.IVA,
        codigo_tipo_impuesto="2",
        codigo_sri="2_OLD",
        descripcion="IVA 12% (expirado)",
        vigente_desde=date.today() - timedelta(days=730),
        vigente_hasta=date.today() - timedelta(days=365),
        aplica_a=AplicaA.AMBOS,
        porcentaje_iva=12.0,
        clasificacion_iva=ClasificacionIVA.GRAVADO,
        activo=True,
        usuario_auditoria="test_user"
    )

    with pytest.raises(HTTPException) as exc_info:
        service.validar_vigencia(impuesto, date.today())
    assert exc_info.value.status_code == 400
    assert "no está vigente" in exc_info.value.detail.lower()


def test_service_validar_vigencia_vigente_ok():
    """validar_vigencia no debe lanzar excepción para impuesto vigente"""
    service = ImpuestoCatalogoService()

    # Impuesto vigente
    impuesto = ImpuestoCatalogo(
        id=uuid4(),
        tipo_impuesto=TipoImpuesto.IVA,
        codigo_tipo_impuesto="2",
        codigo_sri="2",
        descripcion="IVA 15%",
        vigente_desde=date.today() - timedelta(days=365),
        vigente_hasta=None,
        aplica_a=AplicaA.AMBOS,
        porcentaje_iva=15.0,
        clasificacion_iva=ClasificacionIVA.GRAVADO,
        activo=True,
        usuario_auditoria="test_user"
    )

    # No debe lanzar excepción
    service.validar_vigencia(impuesto, date.today())

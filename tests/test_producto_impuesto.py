"""
Tests unitarios para ProductoImpuesto (repository, service, asignación)
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4
from unittest.mock import MagicMock
from fastapi import HTTPException
from pydantic import ValidationError

from osiris.modules.inventario.producto.entity import Producto, TipoProducto
from osiris.modules.sri.impuesto_catalogo.entity import (
    ImpuestoCatalogo,
    TipoImpuesto,
    AplicaA
)
from osiris.modules.inventario.producto.entity import ProductoImpuesto
from osiris.modules.inventario.producto.service import ProductoService
from osiris.modules.inventario.producto.models import ProductoCreate, ProductoUpdate
from osiris.modules.inventario.producto_impuesto.repository import ProductoImpuestoRepository
from osiris.modules.inventario.producto_impuesto.service import ProductoImpuestoService
from osiris.modules.inventario.producto_impuesto.scope import resolve_product_tax_company


# ==================== REPOSITORY TESTS ====================

def test_repo_validar_maximo_por_tipo_cuando_ya_existe():
    """Debe lanzar HTTPException cuando ya existe 1 impuesto del mismo tipo"""
    repo = ProductoImpuestoRepository()
    session = MagicMock()

    producto_id = uuid4()

    # Mock count_by_tipo_impuesto para que devuelva 1
    repo.count_by_tipo_impuesto = MagicMock(return_value=1)

    with pytest.raises(HTTPException) as exc_info:
        repo.validar_maximo_por_tipo(session, producto_id, TipoImpuesto.IVA)
    assert exc_info.value.status_code == 400
    assert "máximo" in exc_info.value.detail.lower()


def test_repo_validar_maximo_por_tipo_cuando_no_existe():
    """No debe lanzar excepción cuando no hay impuestos del tipo"""
    repo = ProductoImpuestoRepository()
    session = MagicMock()

    producto_id = uuid4()

    # Mock count_by_tipo_impuesto para que devuelva 0
    repo.count_by_tipo_impuesto = MagicMock(return_value=0)

    # No debe lanzar excepción
    repo.validar_maximo_por_tipo(session, producto_id, TipoImpuesto.IVA)


def test_repo_validar_duplicado_cuando_existe():
    """Debe lanzar HTTPException cuando ya existe la combinación producto-impuesto"""
    repo = ProductoImpuestoRepository()
    session = MagicMock()

    producto_id = uuid4()
    impuesto_id = uuid4()

    # Mock get_by_producto_impuesto para que devuelva un registro
    repo.get_by_producto_impuesto = MagicMock(return_value=ProductoImpuesto(
        id=uuid4(),
        producto_id=producto_id,
        impuesto_catalogo_id=impuesto_id,
        activo=True,
        usuario_auditoria="test_user"
    ))

    with pytest.raises(HTTPException) as exc_info:
        repo.validar_duplicado(session, producto_id, impuesto_id)
    assert exc_info.value.status_code == 409


# ==================== SERVICE TESTS ====================

def test_service_asignar_impuesto_producto_no_existe():
    """No se puede asignar impuesto a producto inexistente"""
    service = ProductoImpuestoService()
    session = MagicMock()

    producto_id = uuid4()
    impuesto_id = uuid4()

    # Mock session.get para que devuelva None (producto no existe)
    session.get.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        service.asignar_impuesto(session, producto_id, impuesto_id, "test_user")
    assert exc_info.value.status_code == 404


def test_service_asignar_impuesto_producto_inactivo_falla():
    """No se puede asignar impuesto a producto inactivo"""
    service = ProductoImpuestoService()
    session = MagicMock()

    producto_id = uuid4()
    impuesto_id = uuid4()

    producto_inactivo = Producto(
        id=producto_id,
        nombre="Producto Test",
        tipo=TipoProducto.BIEN,
        pvp=100.0,
        activo=False,  # INACTIVO
        usuario_auditoria="test_user"
    )

    # Mock session.get para devolver producto inactivo
    session.get.return_value = producto_inactivo

    with pytest.raises(HTTPException) as exc_info:
        service.asignar_impuesto(session, producto_id, impuesto_id, "test_user")
    assert exc_info.value.status_code == 404
    assert "inactivo" in exc_info.value.detail.lower()


def test_service_validar_compatibilidad_tipo_bien_con_impuesto_solo_servicio():
    """Producto BIEN no puede tener impuesto solo para SERVICIO"""
    service = ProductoImpuestoService()

    with pytest.raises(HTTPException) as exc_info:
        service._validar_compatibilidad_tipo(TipoProducto.BIEN, AplicaA.SERVICIO)
    assert exc_info.value.status_code == 400
    assert "no aplica" in exc_info.value.detail.lower()


def test_service_validar_compatibilidad_tipo_bien_con_impuesto_ambos():
    """Producto BIEN puede tener impuesto para AMBOS"""
    service = ProductoImpuestoService()

    # No debe lanzar excepción
    service._validar_compatibilidad_tipo(TipoProducto.BIEN, AplicaA.AMBOS)


def test_service_validar_compatibilidad_tipo_servicio_con_impuesto_solo_bien():
    """Producto SERVICIO no puede tener impuesto solo para BIEN"""
    service = ProductoImpuestoService()

    with pytest.raises(HTTPException) as exc_info:
        service._validar_compatibilidad_tipo(TipoProducto.SERVICIO, AplicaA.BIEN)
    assert exc_info.value.status_code == 400
    assert "no aplica" in exc_info.value.detail.lower()


def test_producto_rechaza_irbpnr_en_perfil_de_impuestos():
    service = ProductoService()
    session = MagicMock()
    impuesto = ImpuestoCatalogo(
        id=uuid4(),
        tipo_impuesto=TipoImpuesto.IRBPNR,
        codigo_tipo_impuesto="5",
        codigo_sri="500",
        descripcion="IRBPNR de prueba",
        vigente_desde=date.today(),
        aplica_a=AplicaA.BIEN,
        activo=True,
        usuario_auditoria="tester",
    )
    session.get.return_value = impuesto

    with pytest.raises(HTTPException, match="Solo se permiten impuestos IVA e ICE"):
        service._validate_impuestos(session, [impuesto.id], TipoProducto.BIEN)


@pytest.mark.parametrize(
    ("tax_type", "applies_to", "valid_until", "error_text"),
    [
        (TipoImpuesto.IVA, AplicaA.AMBOS, date.today() - timedelta(days=1), "no está vigente"),
        (TipoImpuesto.IVA, AplicaA.SERVICIO, None, "no aplica para productos de tipo BIEN"),
    ],
)
def test_producto_rechaza_impuesto_expirado_o_incompatible(tax_type, applies_to, valid_until, error_text):
    tax = ImpuestoCatalogo(
        id=uuid4(),
        tipo_impuesto=tax_type,
        codigo_tipo_impuesto="2",
        codigo_sri="4",
        descripcion="IVA de prueba",
        vigente_desde=date.today() - timedelta(days=10),
        vigente_hasta=valid_until,
        aplica_a=applies_to,
        porcentaje_iva=Decimal("15.00"),
        activo=True,
        usuario_auditoria="tester",
    )
    session = MagicMock()
    session.get.return_value = tax
    company = type("Company", (), {"impuesto_catalogo_ids": [str(tax.id)]})()

    with pytest.raises(HTTPException, match=error_text):
        ProductoService()._validate_impuestos(session, [tax.id], TipoProducto.BIEN, company)


def test_producto_rechaza_dos_impuestos_del_mismo_tipo():
    taxes = [
        ImpuestoCatalogo(
            id=uuid4(),
            tipo_impuesto=TipoImpuesto.IVA,
            codigo_tipo_impuesto="2",
            codigo_sri=code,
            descripcion=f"IVA {code}",
            vigente_desde=date.today(),
            aplica_a=AplicaA.BIEN,
            porcentaje_iva=Decimal("0.00"),
            activo=True,
            usuario_auditoria="tester",
        )
        for code in ("0", "4")
    ]
    session = MagicMock()
    session.get.side_effect = taxes

    with pytest.raises(HTTPException, match="Solo se permite un impuesto de tipo IVA"):
        ProductoService()._validate_impuestos(session, [tax.id for tax in taxes], TipoProducto.BIEN)


def test_producto_create_acepta_servicio_y_lista_multiimpuesto():
    tax_ids = [uuid4(), uuid4()]

    payload = ProductoCreate(
        nombre="Servicio de instalación",
        tipo=TipoProducto.SERVICIO,
        pvp=Decimal("25.00"),
        impuesto_catalogo_ids=tax_ids,
        usuario_auditoria="tester",
    )

    assert payload.tipo == TipoProducto.SERVICIO
    assert payload.impuesto_catalogo_ids == tax_ids


def test_producto_create_rechaza_lista_de_impuestos_vacia():
    with pytest.raises(ValidationError, match="al menos un impuesto IVA"):
        ProductoCreate(
            nombre="Producto sin impuesto",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            impuesto_catalogo_ids=[],
        )


def test_producto_update_rechaza_lista_de_impuestos_vacia():
    with pytest.raises(ValidationError, match="no puede quedar vacío"):
        ProductoUpdate(impuesto_catalogo_ids=[])


def test_producto_update_reemplaza_impuestos_en_scope_empresa(monkeypatch):
    service = ProductoService()
    service.repo = MagicMock()
    session = MagicMock()
    product_id, company_id, old_tax_id, new_tax_id = uuid4(), uuid4(), uuid4(), uuid4()
    product = Producto(
        id=product_id,
        nombre="Producto existente",
        tipo=TipoProducto.BIEN,
        pvp=Decimal("10.00"),
        usuario_auditoria="tester",
        activo=True,
    )
    previous_assignment = ProductoImpuesto(
        producto_id=product_id,
        empresa_id=company_id,
        impuesto_catalogo_id=old_tax_id,
        codigo_impuesto_sri="2",
        codigo_porcentaje_sri="0",
        tarifa=Decimal("0.00"),
        usuario_auditoria="tester",
        activo=True,
    )
    new_tax = ImpuestoCatalogo(
        id=new_tax_id,
        tipo_impuesto=TipoImpuesto.IVA,
        codigo_tipo_impuesto="2",
        codigo_sri="4",
        descripcion="IVA 15%",
        vigente_desde=date.today(),
        aplica_a=AplicaA.BIEN,
        porcentaje_iva=Decimal("15.00"),
        activo=True,
        usuario_auditoria="tester",
    )
    company = type(
        "Company",
        (),
        {"id": company_id, "impuesto_catalogo_ids": [str(new_tax_id)]},
    )()
    service.repo.get.return_value = product
    service.repo.update.return_value = product
    session.exec.return_value.all.return_value = [previous_assignment]
    session.get.return_value = new_tax
    monkeypatch.setattr(
        "osiris.modules.inventario.producto.service.resolve_product_tax_company",
        lambda *_args: company,
    )

    updated = service.update(
        session,
        product_id,
        {"impuesto_catalogo_ids": [new_tax_id], "usuario_auditoria": "tester"},
    )

    assert updated is product
    assert previous_assignment.activo is False
    active_assignments = [
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], ProductoImpuesto) and call.args[0].activo
    ]
    assert len(active_assignments) == 1
    assert active_assignments[0].empresa_id == company_id
    assert active_assignments[0].impuesto_catalogo_id == new_tax_id
    session.commit.assert_called_once()


def test_producto_update_rechaza_cambio_tipo_incompatible_con_impuesto_asignado(monkeypatch):
    service = ProductoService()
    service.repo = MagicMock()
    session = MagicMock()
    product_id = uuid4()
    product = Producto(
        id=product_id,
        nombre="Bien con IVA",
        tipo=TipoProducto.BIEN,
        pvp=Decimal("10.00"),
        usuario_auditoria="tester",
        activo=True,
    )
    assigned = ProductoImpuesto(
        producto_id=product_id,
        empresa_id=uuid4(),
        impuesto_catalogo_id=uuid4(),
        codigo_impuesto_sri="2",
        codigo_porcentaje_sri="0",
        tarifa=Decimal("0.00"),
        usuario_auditoria="tester",
        activo=True,
    )
    service.repo.get.return_value = product
    monkeypatch.setattr(
        "osiris.modules.inventario.producto.service.resolve_product_tax_company",
        lambda *_args: type(
            "Company",
            (),
            {"id": assigned.empresa_id, "impuesto_catalogo_ids": [str(assigned.impuesto_catalogo_id)]},
        )(),
    )
    taxes_query = MagicMock()
    taxes_query.all.return_value = [assigned]
    session.exec.return_value = taxes_query
    session.get.return_value = ImpuestoCatalogo(
        id=assigned.impuesto_catalogo_id,
        tipo_impuesto=TipoImpuesto.IVA,
        codigo_tipo_impuesto="2",
        codigo_sri="0",
        descripcion="IVA 0% exclusivo para bienes",
        vigente_desde=date.today(),
        aplica_a=AplicaA.BIEN,
        porcentaje_iva=Decimal("0.00"),
        usuario_auditoria="tester",
        activo=True,
    )

    with pytest.raises(HTTPException, match="no aplica para productos de tipo SERVICIO"):
        service.update(session, product_id, {"tipo": TipoProducto.SERVICIO})

    service.repo.update.assert_not_called()


def test_resolver_empresa_usa_scope_autenticado(monkeypatch):
    empresa_id = uuid4()
    empresa = type("Company", (), {"id": empresa_id, "activo": True})()
    session = MagicMock()
    session.get.return_value = empresa
    monkeypatch.setattr(
        "osiris.modules.inventario.producto_impuesto.scope.resolve_company_scope",
        lambda: empresa_id,
    )

    assert resolve_product_tax_company(session) is empresa
    session.exec.assert_not_called()


def test_resolver_empresa_solo_infiere_scope_univoco(monkeypatch):
    empresa_id = uuid4()
    empresa = type("Company", (), {"id": empresa_id, "activo": True})()
    session = MagicMock()
    session.exec.return_value.all.return_value = [empresa_id]
    session.get.return_value = empresa
    monkeypatch.setattr(
        "osiris.modules.inventario.producto_impuesto.scope.resolve_company_scope",
        lambda: None,
    )

    assert resolve_product_tax_company(session, uuid4()) is empresa


def test_resolver_empresa_rechaza_scope_ambiguo(monkeypatch):
    session = MagicMock()
    session.exec.return_value.all.return_value = [uuid4(), uuid4()]
    monkeypatch.setattr(
        "osiris.modules.inventario.producto_impuesto.scope.resolve_company_scope",
        lambda: None,
    )

    with pytest.raises(HTTPException, match="empresa única") as exc_info:
        resolve_product_tax_company(session, uuid4())

    assert exc_info.value.status_code == 409


def test_lista_impuestos_permitidos_filtra_irbpnr_vigencia_y_aplicabilidad(monkeypatch):
    iva_bien = ImpuestoCatalogo(
        id=uuid4(),
        tipo_impuesto=TipoImpuesto.IVA,
        codigo_tipo_impuesto="2",
        codigo_sri="0",
        descripcion="IVA 0% bienes",
        vigente_desde=date.today(),
        aplica_a=AplicaA.BIEN,
        activo=True,
        usuario_auditoria="tester",
    )
    iva_servicio = ImpuestoCatalogo(
        id=uuid4(),
        tipo_impuesto=TipoImpuesto.IVA,
        codigo_tipo_impuesto="2",
        codigo_sri="0S",
        descripcion="IVA 0% servicios",
        vigente_desde=date.today(),
        aplica_a=AplicaA.SERVICIO,
        activo=True,
        usuario_auditoria="tester",
    )
    irbpnr = ImpuestoCatalogo(
        id=uuid4(),
        tipo_impuesto=TipoImpuesto.IRBPNR,
        codigo_tipo_impuesto="5",
        codigo_sri="500",
        descripcion="IRBPNR",
        vigente_desde=date.today(),
        aplica_a=AplicaA.BIEN,
        activo=True,
        usuario_auditoria="tester",
    )
    company = type(
        "Company",
        (),
        {"id": uuid4(), "impuesto_catalogo_ids": [str(iva_bien.id), str(iva_servicio.id), str(irbpnr.id)]},
    )()
    session = MagicMock()
    session.exec.return_value.all.return_value = [iva_bien, iva_servicio, irbpnr]
    service = ProductoImpuestoService()
    monkeypatch.setattr(
        "osiris.modules.inventario.producto_impuesto.service.resolve_product_tax_company",
        lambda *_args: company,
    )

    result = service.listar_impuestos_permitidos(session, TipoProducto.BIEN)

    assert result == [iva_bien]


def test_service_eliminar_iva_siempre_rechazado(monkeypatch):
    """No se puede eliminar IVA - es obligatorio (requerimiento SRI)"""
    service = ProductoImpuestoService()
    session = MagicMock()

    producto_id = uuid4()
    impuesto_id = uuid4()
    producto_impuesto_id = uuid4()
    empresa_id = uuid4()

    # Mock: ProductoImpuesto existe y es IVA
    producto_impuesto = ProductoImpuesto(
        id=producto_impuesto_id,
        producto_id=producto_id,
        empresa_id=empresa_id,
        impuesto_catalogo_id=impuesto_id,
        activo=True,
        usuario_auditoria="test"
    )

    impuesto_iva = ImpuestoCatalogo(
        id=impuesto_id,
        tipo_impuesto=TipoImpuesto.IVA,
        codigo_tipo_impuesto="2",
        codigo_sri="2",
        descripcion="IVA 0%",
        vigente_desde=date.today(),
        aplica_a=AplicaA.AMBOS,
        activo=True,
        usuario_auditoria="test"
    )

    # Mock session.get para devolver producto_impuesto e impuesto
    def mock_get(model, id):
        if id == producto_impuesto_id:
            return producto_impuesto
        if id == impuesto_id:
            return impuesto_iva
        return None

    session.get = mock_get
    monkeypatch.setattr(
        "osiris.modules.inventario.producto_impuesto.service.resolve_product_tax_company",
        lambda *_args: type("Company", (), {"id": empresa_id})(),
    )

    # Intentar eliminar IVA debe fallar siempre
    with pytest.raises(HTTPException) as exc_info:
        service.eliminar_impuesto(session, producto_impuesto_id)

    assert exc_info.value.status_code == 400
    assert "obligatorio" in exc_info.value.detail.lower()
    assert "iva" in exc_info.value.detail.lower()


def test_service_eliminar_ice_ok(monkeypatch):
    """Se puede eliminar ICE u otros impuestos que no sean IVA"""
    service = ProductoImpuestoService()
    session = MagicMock()

    producto_id = uuid4()
    impuesto_id = uuid4()
    producto_impuesto_id = uuid4()
    empresa_id = uuid4()

    # Mock: ProductoImpuesto con ICE
    producto_impuesto = ProductoImpuesto(
        id=producto_impuesto_id,
        producto_id=producto_id,
        empresa_id=empresa_id,
        impuesto_catalogo_id=impuesto_id,
        activo=True,
        usuario_auditoria="test"
    )

    impuesto_ice = ImpuestoCatalogo(
        id=impuesto_id,
        tipo_impuesto=TipoImpuesto.ICE,
        codigo_tipo_impuesto="3",
        codigo_sri="3",
        descripcion="ICE 10%",
        vigente_desde=date.today(),
        aplica_a=AplicaA.BIEN,
        activo=True,
        usuario_auditoria="test"
    )

    # Mock session.get
    def mock_get(model, id):
        if id == producto_impuesto_id:
            return producto_impuesto
        if id == impuesto_id:
            return impuesto_ice
        return None

    session.get = mock_get
    monkeypatch.setattr(
        "osiris.modules.inventario.producto_impuesto.service.resolve_product_tax_company",
        lambda *_args: type("Company", (), {"id": empresa_id})(),
    )

    # Mock delete_by_id
    service.repo.delete_by_id = MagicMock(return_value=True)

    # Eliminar ICE debe ser exitoso
    result = service.eliminar_impuesto(session, producto_impuesto_id)
    assert result is True
    service.repo.delete_by_id.assert_called_once_with(session, producto_impuesto_id)


def test_service_asignar_impuesto_guarda_codigos_sri_y_tarifa_snapshot(monkeypatch):
    service = ProductoImpuestoService()
    session = MagicMock()

    producto_id = uuid4()
    impuesto_id = uuid4()
    empresa_id = uuid4()
    producto = Producto(
        id=producto_id,
        nombre="Producto Test",
        tipo=TipoProducto.BIEN,
        pvp=100.0,
        activo=True,
        usuario_auditoria="test_user",
    )
    impuesto = ImpuestoCatalogo(
        id=impuesto_id,
        tipo_impuesto=TipoImpuesto.IVA,
        codigo_tipo_impuesto="2",
        codigo_sri="4",
        descripcion="IVA 15%",
        vigente_desde=date.today() - timedelta(days=10),
        aplica_a=AplicaA.AMBOS,
        porcentaje_iva=15,
        activo=True,
        usuario_auditoria="test",
    )

    def mock_get(model, obj_id):
        if model is Producto and obj_id == producto_id:
            return producto
        if model is ImpuestoCatalogo and obj_id == impuesto_id:
            return impuesto
        return None

    session.get = mock_get
    monkeypatch.setattr(
        "osiris.modules.inventario.producto_impuesto.service.resolve_product_tax_company",
        lambda *_args: type(
            "Company", (), {"id": empresa_id, "impuesto_catalogo_ids": [str(impuesto_id)]}
        )(),
    )
    service.repo.validar_duplicado = MagicMock()
    service.list_by_producto = MagicMock(return_value=[])
    service.impuesto_repo.es_vigente = MagicMock(return_value=True)
    service.repo.create = MagicMock(side_effect=lambda _session, obj: obj)

    result = service.asignar_impuesto(session, producto_id, impuesto_id, "tester")
    assert result.codigo_impuesto_sri == "2"
    assert result.codigo_porcentaje_sri == "4"
    assert str(result.tarifa) == "15"

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlmodel import select

from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.persona.entity import Persona, TipoIdentificacion
from osiris.modules.common.punto_emision.entity import PuntoEmision
from osiris.modules.common.rol.entity import Rol
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.common.usuario.entity import Usuario
from osiris.modules.sri.core_sri.models import (
    DocumentoElectronico,
    EstadoDocumentoElectronico,
    EstadoVenta,
    FormaPagoSRI,
    TipoDocumentoElectronico,
    TipoEmisionVenta,
    TipoIdentificacionSRI,
    Venta,
    VentaDetalle,
)
from osiris.modules.inventario.producto.entity import Producto, TipoProducto


pytestmark = pytest.mark.smoke


def _crear_usuario_cajero(db_session) -> UUID:
    existing = db_session.exec(
        select(Usuario, Rol)
        .join(Rol, Rol.id == Usuario.rol_id)
        .where(
            Usuario.activo.is_(True),
            Rol.activo.is_(True),
            Rol.nombre.in_(["CAJERO", "ADMIN", "ADMINISTRADOR"]),
        )
    ).first()
    if existing:
        usuario, _ = existing
        return usuario.id

    rol = db_session.exec(select(Rol).where(Rol.nombre == "CAJERO")).first()
    if rol is None:
        rol = Rol(
            nombre="CAJERO",
            descripcion="Rol para pruebas smoke de impresion",
            usuario_auditoria="smoke",
            activo=True,
        )
        db_session.add(rol)
        db_session.flush()

    persona = Persona(
        tipo_identificacion=TipoIdentificacion.CEDULA,
        identificacion=f"{(uuid4().int % 10**10):010d}",
        nombre="Smoke",
        apellido="Cajero",
        email=f"smoke-cajero-{uuid4().hex[:8]}@test.local",
        usuario_auditoria="smoke",
        activo=True,
    )
    db_session.add(persona)
    db_session.flush()

    usuario = Usuario(
        persona_id=persona.id,
        rol_id=rol.id,
        username=f"smoke_cajero_{uuid4().hex[:8]}",
        password_hash="hash",
        requiere_cambio_password=False,
        usuario_auditoria="smoke",
        activo=True,
    )
    db_session.add(usuario)
    db_session.commit()
    return usuario.id


def _crear_documentos_para_impresion(db_session) -> tuple[UUID, UUID]:
    empresa = Empresa(
        razon_social=f"SMOKE IMPRESION {uuid4().hex[:6]}",
        nombre_comercial=f"SMOKE IMP {uuid4().hex[:6]}",
        ruc=f"179{uuid4().int % 10**10:010d}001",
        direccion_matriz="Av. Smoke 123",
        telefono="022345678",
        obligado_contabilidad=False,
        regimen="GENERAL",
        modo_emision="ELECTRONICO",
        tipo_contribuyente_id="01",
        usuario_auditoria="smoke",
        activo=True,
    )
    db_session.add(empresa)
    db_session.flush()

    sucursal = Sucursal(
        codigo="001",
        nombre="Matriz",
        direccion="Av. Matriz 001",
        telefono="022000000",
        es_matriz=True,
        empresa_id=empresa.id,
        usuario_auditoria="smoke",
        activo=True,
    )
    db_session.add(sucursal)
    db_session.flush()

    punto = PuntoEmision(
        codigo="001",
        descripcion="Punto Smoke",
        secuencial_actual=1,
        config_impresion={"margen_superior_cm": 6, "max_items_por_pagina": 15},
        sucursal_id=sucursal.id,
        usuario_auditoria="smoke",
        activo=True,
    )
    db_session.add(punto)
    db_session.flush()

    producto = Producto(
        nombre=f"SMOKE-IMP-PROD-{uuid4().hex[:6]}",
        tipo=TipoProducto.BIEN,
        pvp=Decimal("25.00"),
        cantidad=0,
        usuario_auditoria="smoke",
        activo=True,
    )
    db_session.add(producto)
    db_session.flush()

    venta_e = Venta(
        empresa_id=empresa.id,
        punto_emision_id=punto.id,
        fecha_emision=date.today(),
        tipo_identificacion_comprador=TipoIdentificacionSRI.RUC,
        identificacion_comprador="1790012345001",
        forma_pago=FormaPagoSRI.EFECTIVO,
        tipo_emision=TipoEmisionVenta.ELECTRONICA,
        subtotal_sin_impuestos=Decimal("50.00"),
        subtotal_12=Decimal("0.00"),
        subtotal_15=Decimal("0.00"),
        subtotal_0=Decimal("50.00"),
        subtotal_no_objeto=Decimal("0.00"),
        monto_iva=Decimal("0.00"),
        monto_ice=Decimal("0.00"),
        valor_total=Decimal("50.00"),
        estado=EstadoVenta.EMITIDA,
        usuario_auditoria="smoke",
        activo=True,
    )
    db_session.add(venta_e)
    db_session.flush()

    db_session.add(
        VentaDetalle(
            venta_id=venta_e.id,
            producto_id=producto.id,
            descripcion="Detalle smoke electronico",
            cantidad=Decimal("2.0000"),
            precio_unitario=Decimal("25.0000"),
            descuento=Decimal("0.00"),
            subtotal_sin_impuesto=Decimal("50.00"),
            es_actividad_excluida=False,
            usuario_auditoria="smoke",
            activo=True,
        )
    )

    venta_f = Venta(
        empresa_id=empresa.id,
        punto_emision_id=punto.id,
        fecha_emision=date.today(),
        tipo_identificacion_comprador=TipoIdentificacionSRI.CEDULA,
        identificacion_comprador=f"{(uuid4().int % 10**10):010d}",
        forma_pago=FormaPagoSRI.EFECTIVO,
        tipo_emision=TipoEmisionVenta.NOTA_VENTA_FISICA,
        subtotal_sin_impuestos=Decimal("25.00"),
        subtotal_12=Decimal("0.00"),
        subtotal_15=Decimal("0.00"),
        subtotal_0=Decimal("25.00"),
        subtotal_no_objeto=Decimal("0.00"),
        monto_iva=Decimal("0.00"),
        monto_ice=Decimal("0.00"),
        valor_total=Decimal("25.00"),
        estado=EstadoVenta.EMITIDA,
        usuario_auditoria="smoke",
        activo=True,
    )
    db_session.add(venta_f)
    db_session.flush()

    db_session.add(
        VentaDetalle(
            venta_id=venta_f.id,
            producto_id=producto.id,
            descripcion="Detalle smoke fisico",
            cantidad=Decimal("1.0000"),
            precio_unitario=Decimal("25.0000"),
            descuento=Decimal("0.00"),
            subtotal_sin_impuesto=Decimal("25.00"),
            es_actividad_excluida=False,
            usuario_auditoria="smoke",
            activo=True,
        )
    )

    doc_e = DocumentoElectronico(
        tipo_documento=TipoDocumentoElectronico.FACTURA,
        referencia_id=venta_e.id,
        venta_id=venta_e.id,
        clave_acceso=f"{uuid4().int:049d}"[-49:],
        estado_sri=EstadoDocumentoElectronico.AUTORIZADO,
        estado=EstadoDocumentoElectronico.AUTORIZADO,
        xml_autorizado="<factura/>",
        usuario_auditoria="smoke",
        activo=True,
    )
    db_session.add(doc_e)

    doc_f = DocumentoElectronico(
        tipo_documento=TipoDocumentoElectronico.FACTURA,
        referencia_id=venta_f.id,
        venta_id=venta_f.id,
        clave_acceso=f"{uuid4().int:049d}"[-49:],
        estado_sri=EstadoDocumentoElectronico.AUTORIZADO,
        estado=EstadoDocumentoElectronico.AUTORIZADO,
        xml_autorizado="<nota_venta/>",
        usuario_auditoria="smoke",
        activo=True,
    )
    db_session.add(doc_f)
    db_session.commit()

    return doc_e.id, doc_f.id


@pytest.mark.smoke
def test_smoke_impresion_ride_ticket_matricial_reimpresion(client, db_session):
    doc_e = db_session.exec(
        select(DocumentoElectronico)
        .where(
            DocumentoElectronico.activo.is_(True),
            DocumentoElectronico.tipo_documento == TipoDocumentoElectronico.FACTURA,
            DocumentoElectronico.estado_sri == EstadoDocumentoElectronico.AUTORIZADO,
        )
        .order_by(DocumentoElectronico.creado_en.desc())
    ).first()

    doc_f = None
    if doc_e is not None:
        for candidate in db_session.exec(
            select(DocumentoElectronico)
            .where(
                DocumentoElectronico.activo.is_(True),
                DocumentoElectronico.tipo_documento == TipoDocumentoElectronico.FACTURA,
                DocumentoElectronico.estado_sri == EstadoDocumentoElectronico.AUTORIZADO,
            )
            .order_by(DocumentoElectronico.creado_en.desc())
        ).all():
            venta_id = candidate.venta_id or candidate.referencia_id
            if not venta_id:
                continue
            venta = db_session.get(Venta, venta_id)
            if venta and venta.tipo_emision == TipoEmisionVenta.NOTA_VENTA_FISICA:
                doc_f = candidate
                break

    if doc_e is None or doc_f is None:
        doc_e_id, doc_f_id = _crear_documentos_para_impresion(db_session)
    else:
        doc_e_id = doc_e.id
        doc_f_id = doc_f.id

    usuario_id = _crear_usuario_cajero(db_session)

    ride = client.get(f"/api/v1/impresion/documento/{doc_e_id}/a4")
    assert ride.status_code == 200, ride.text
    assert ride.headers.get("content-type", "").startswith("application/pdf")

    ticket = client.get(f"/api/v1/impresion/documento/{doc_e_id}/ticket", params={"ancho": "80mm"})
    assert ticket.status_code == 200, ticket.text

    matricial = client.get(f"/api/v1/impresion/documento/{doc_f_id}/preimpresa")
    assert matricial.status_code == 200, matricial.text
    assert "padding-top" in matricial.text

    reimpresion = client.post(
        f"/api/v1/impresion/documento/{doc_e_id}/reimprimir",
        json={"motivo": "Smoke test", "formato": "A4"},
        headers={"X-User-Id": str(usuario_id)},
    )
    assert reimpresion.status_code == 200, reimpresion.text

    db_session.expire_all()
    audit = db_session.exec(
        select(AuditLog)
        .where(
            AuditLog.accion == "REIMPRESION_DOCUMENTO",
            AuditLog.registro_id == str(doc_e_id),
            AuditLog.usuario_id == str(usuario_id),
        )
        .order_by(AuditLog.fecha.desc())
    ).first()
    assert audit is not None
    assert (audit.estado_nuevo or {}).get("motivo") == "Smoke test"

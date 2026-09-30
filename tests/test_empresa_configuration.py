from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.empresa.service import EmpresaService
from osiris.modules.common.empresa.signature_service import EmpresaSignatureService
from osiris.modules.sri.impuesto_catalogo.entity import AplicaA, ImpuestoCatalogo, TipoImpuesto


def _engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(
        engine,
        tables=[Empresa.__table__, ImpuestoCatalogo.__table__, AuditLog.__table__],
    )
    return engine


def _empresa() -> Empresa:
    return Empresa(
        razon_social="Empresa Configuración",
        ruc="1790012345001",
        direccion_matriz="Av. Principal",
        tipo_contribuyente_juridico="SOCIEDAD",
        regimen="GENERAL",
        modo_emision="ELECTRONICO",
        tipo_contribuyente_id="01",
        usuario_auditoria="tester",
        activo=True,
    )


def _p12(password: str, *, expired: bool = False) -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Empresa de prueba")])
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=30))
        .not_valid_after(now - timedelta(days=1) if expired else now + timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    return pkcs12.serialize_key_and_certificates(
        b"empresa",
        key,
        certificate,
        None,
        serialization.BestAvailableEncryption(password.encode()),
    )


def test_firma_electronica_se_valida_y_almacena_cifrada():
    engine = _engine()
    content = _p12("secreto")

    with Session(engine) as session:
        empresa = _empresa()
        session.add(empresa)
        session.commit()
        service = EmpresaSignatureService()

        saved = service.save(
            session,
            empresa.id,
            filename="firma.p12",
            content=content,
            password="secreto",
        )

        assert saved.firma_electronica_configurada is True
        assert saved.firma_electronica_cifrada != content
        assert saved.firma_nombre_archivo == "firma.p12"
        assert saved.firma_caduca_en is not None
        assert service.credentials(saved) == (content, "secreto")


@pytest.mark.parametrize(
    ("password", "expired", "message"),
    [
        ("incorrecta", False, "inválidos"),
        ("secreto", True, "caducada"),
    ],
)
def test_firma_electronica_rechaza_password_incorrecto_o_certificado_caducado(
    password: str,
    expired: bool,
    message: str,
):
    engine = _engine()

    with Session(engine) as session:
        empresa = _empresa()
        session.add(empresa)
        session.commit()

        with pytest.raises(HTTPException, match=message):
            EmpresaSignatureService().save(
                session,
                empresa.id,
                filename="firma.p12",
                content=_p12("secreto", expired=expired),
                password=password,
            )


def test_impuestos_empresariales_requieren_catalogo_activo():
    engine = _engine()

    with Session(engine) as session:
        active_tax = ImpuestoCatalogo(
            tipo_impuesto=TipoImpuesto.IVA,
            codigo_tipo_impuesto="2",
            codigo_sri="4",
            descripcion="IVA 15%",
            vigente_desde=date(2024, 4, 1),
            aplica_a=AplicaA.AMBOS,
            usuario_auditoria="tester",
            activo=True,
        )
        inactive_tax = ImpuestoCatalogo(
            tipo_impuesto=TipoImpuesto.IVA,
            codigo_tipo_impuesto="2",
            codigo_sri="2",
            descripcion="IVA 12% histórico",
            vigente_desde=date(2020, 1, 1),
            aplica_a=AplicaA.AMBOS,
            usuario_auditoria="tester",
            activo=False,
        )
        session.add(active_tax)
        session.add(inactive_tax)
        session.commit()

        payload = {"impuesto_catalogo_ids": [active_tax.id, active_tax.id]}
        EmpresaService._validate_company_taxes(session, payload)
        assert payload["impuesto_catalogo_ids"] == [str(active_tax.id)]

        with pytest.raises(HTTPException, match="inactivos"):
            EmpresaService._validate_company_taxes(
                session,
                {"impuesto_catalogo_ids": [inactive_tax.id]},
            )
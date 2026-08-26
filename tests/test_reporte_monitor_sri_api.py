from __future__ import annotations


from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from osiris.core.db import get_session
from osiris.main import app
from osiris.modules.sri.core_sri.types import EstadoDocumentoElectronico, TipoDocumentoElectronico
from osiris.modules.sri.facturacion_electronica.models import DocumentoElectronico


def _build_test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(
        engine,
        tables=[
            DocumentoElectronico.__table__,
        ],
    )
    return engine


def test_monitor_sri_agrupacion_estados():
    engine = _build_test_engine()
    with Session(engine) as session:
        session.add(
            DocumentoElectronico(
                tipo_documento=TipoDocumentoElectronico.FACTURA,
                estado_sri=EstadoDocumentoElectronico.AUTORIZADO,
                estado=EstadoDocumentoElectronico.AUTORIZADO,
                usuario_auditoria="seed",
                activo=True,
            )
        )
        session.add(
            DocumentoElectronico(
                tipo_documento=TipoDocumentoElectronico.FACTURA,
                estado_sri=EstadoDocumentoElectronico.AUTORIZADO,
                estado=EstadoDocumentoElectronico.AUTORIZADO,
                usuario_auditoria="seed",
                activo=True,
            )
        )
        session.add(
            DocumentoElectronico(
                tipo_documento=TipoDocumentoElectronico.RETENCION,
                estado_sri=EstadoDocumentoElectronico.RECHAZADO,
                estado=EstadoDocumentoElectronico.RECHAZADO,
                usuario_auditoria="seed",
                activo=True,
            )
        )
        session.commit()

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/reportes/sri/monitor-estados",
                params={
                    "fecha_inicio": "2000-01-01",
                    "fecha_fin": "2100-12-31",
                },
            )
        assert response.status_code == 200, response.text
        data = response.json()
        conteos = {
            (item["estado"], item["tipo_documento"]): int(item["cantidad"])
            for item in data
        }
        assert conteos[("AUTORIZADO", "FACTURA")] == 2
        assert conteos[("RECHAZADO", "RETENCION")] == 1
    finally:
        app.dependency_overrides.pop(get_session, None)

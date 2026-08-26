from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from osiris.core.db import get_session
import osiris.main as main_module
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.modulo.entity import Modulo
from osiris.modules.common.rol.entity import Rol
from osiris.modules.common.rol_modulo_permiso.entity import RolModuloPermiso
from osiris.modules.common.usuario.entity import Usuario
from osiris.modules.sri.tipo_contribuyente.entity import TipoContribuyente


def _build_test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(
        engine,
        tables=[
            TipoContribuyente.__table__,
            Empresa.__table__,
            Rol.__table__,
            Usuario.__table__,
            Modulo.__table__,
            RolModuloPermiso.__table__,
            AuditLog.__table__,
        ],
    )
    return engine


def test_log_unauthorized_access():
    engine = _build_test_engine()

    with Session(engine) as session:
        tipo = TipoContribuyente(codigo="01", nombre="Sociedad", descripcion="Test", activo=True)
        session.add(tipo)

        empresa = Empresa(
            razon_social="Empresa Test",
            nombre_comercial="Empresa Test",
            ruc="1790012345001",
            direccion_matriz="Av. Principal",
            telefono="022345678",
            obligado_contabilidad=True,
            regimen="GENERAL",
            modo_emision="ELECTRONICO",
            tipo_contribuyente_id="01",
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(empresa)

        rol_cajero = Rol(
            nombre="CAJERO",
            descripcion="Rol cajero",
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(rol_cajero)
        session.flush()

        usuario_cajero = Usuario(
            persona_id=uuid4(),
            rol_id=rol_cajero.id,
            username="cajero.test",
            password_hash="hash",
            requiere_cambio_password=False,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(usuario_cajero)

        modulo_empresa = Modulo(
            codigo="EMPRESA",
            nombre="Empresas",
            descripcion="Modulo empresa",
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(modulo_empresa)
        session.flush()

        permiso_cajero = RolModuloPermiso(
            rol_id=rol_cajero.id,
            modulo_id=modulo_empresa.id,
            puede_leer=True,
            puede_crear=False,
            puede_actualizar=False,
            puede_eliminar=False,
            usuario_auditoria="seed",
            activo=True,
        )
        session.add(permiso_cajero)
        session.commit()
        session.refresh(empresa)
        session.refresh(usuario_cajero)

    def override_get_session():
        with Session(engine) as session:
            yield session

    original_security_engine = getattr(main_module.app.state, "security_audit_engine", None)
    main_module.app.state.security_audit_engine = engine
    main_module.app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(main_module.app) as client:
            response = client.put(
                f"/api/v1/empresas/{empresa.id}",
                json={
                    "regimen": "RIMPE_EMPRENDEDOR",
                    "modo_emision": "ELECTRONICO",
                    "usuario_auditoria": "cajero.test",
                },
                headers={"Authorization": f"Bearer {usuario_cajero.id}"},
            )

        assert response.status_code == 403
        assert response.json()["detail"] == "No tiene permisos para esta operación."

        with Session(engine) as session:
            log = session.exec(
                select(AuditLog)
                .where(
                    AuditLog.accion == "UNAUTHORIZED_ACCESS",
                    AuditLog.usuario_id == str(usuario_cajero.id),
                )
                .order_by(AuditLog.fecha.desc())
            ).first()

        assert log is not None
        assert log.tabla_afectada == "SECURITY"
        assert log.estado_nuevo["endpoint"] == f"/api/v1/empresas/{empresa.id}"
        assert log.estado_nuevo["metodo"] == "PUT"
        assert log.estado_nuevo["modulo"] == "EMPRESA"
        assert log.estado_nuevo["accion_requerida"] == "actualizar"
        assert log.estado_nuevo["payload_intentado"]["regimen"] == "RIMPE_EMPRENDEDOR"
        assert log.estado_nuevo["ip"] is not None
    finally:
        main_module.app.dependency_overrides.pop(get_session, None)
        main_module.app.state.security_audit_engine = original_security_engine


def test_unauthorized_access_keeps_403_when_security_audit_fails(monkeypatch):
    def _raise_on_security_log(**_kwargs):
        raise RuntimeError("db unavailable during security audit")

    monkeypatch.setattr(
        main_module,
        "_log_unauthorized_access_sync",
        _raise_on_security_log,
    )

    with TestClient(main_module.app) as client:
        response = client.put(
            f"/api/v1/empresas/{uuid4()}",
            json={"regimen": "GENERAL", "modo_emision": "ELECTRONICO"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Acceso denegado a endpoint sensible."

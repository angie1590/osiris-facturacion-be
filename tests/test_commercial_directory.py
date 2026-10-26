import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import MetaData, event
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlmodel import Session, create_engine, select

from osiris.core.audit_context import reset_current_user_id, set_current_user_id
from osiris.core.db import get_session
from osiris.modules.common.cliente.entity import Cliente
from osiris.modules.common.cliente.models import ClienteCreate, ClienteUpdate
from osiris.modules.common.cliente.router import router as customer_router
from osiris.modules.common.cliente.service import ClienteService
from osiris.modules.common.persona.entity import Persona
from osiris.modules.common.persona.repository import PersonaRepository
from osiris.modules.common.persona.service import PersonaService
from osiris.modules.common.empleado.entity import Empleado
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.rol.entity import Rol
from osiris.modules.common.usuario.entity import Usuario
from osiris.modules.common.proveedor_persona.entity import ProveedorPersona
from osiris.modules.common.proveedor_persona.models import (
    ProveedorPersonaCreate,
    ProveedorPersonaUpdate,
)
from osiris.modules.common.proveedor_persona.router import router as supplier_router
from osiris.modules.common.proveedor_persona.service import ProveedorPersonaService
from osiris.modules.common.proveedor_sociedad.entity import ProveedorSociedad
from osiris.modules.common.proveedor_sociedad.models import (
    ProveedorSociedadCreate,
    ProveedorSociedadUpdate,
)
from osiris.modules.common.proveedor_sociedad.router import router as society_router
from osiris.modules.common.proveedor_sociedad.service import ProveedorSociedadService
from osiris.modules.common.tipo_cliente.entity import TipoCliente
from osiris.modules.common.tipo_cliente.models import (
    TipoClienteCreate,
    TipoClienteUpdate,
)
from osiris.modules.common.tipo_cliente.router import router as type_router
from osiris.modules.common.tipo_cliente.service import TipoClienteService
from osiris.modules.sri.tipo_contribuyente.entity import TipoContribuyente

COMMERCIAL_MODELS = (
    Persona,
    TipoCliente,
    Cliente,
    TipoContribuyente,
    ProveedorPersona,
    ProveedorSociedad,
    Empresa,
    Rol,
    Empleado,
    Usuario,
)
COMMERCIAL_ROUTERS = (customer_router, type_router, supplier_router, society_router)


def commercial_metadata():
    metadata = MetaData()
    for model in COMMERCIAL_MODELS:
        model.__table__.to_metadata(metadata)
    return metadata


@pytest.fixture
def commercial_engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def explicit_transactions(connection, record):
        connection.isolation_level = None
        connection.execute("PRAGMA foreign_keys=ON")

    @event.listens_for(engine, "begin")
    def begin_transaction(connection):
        connection.exec_driver_sql("BEGIN")

    commercial_metadata().create_all(engine)
    yield engine
    engine.dispose()


def person_draft(identification="ABC123"):
    return {
        "tipo_identificacion": "PASAPORTE",
        "identificacion": identification,
        "nombre": "Ana",
        "apellido": "Perez",
    }


def test_customer_composite_rolls_back_invalid_type(commercial_engine):
    with Session(commercial_engine) as session:
        with pytest.raises(HTTPException) as error:
            ClienteService().create(
                session,
                ClienteCreate(persona_nueva=person_draft(), tipo_cliente_id=uuid4()),
            )
        assert error.value.status_code == 404
    with Session(commercial_engine) as session:
        assert session.exec(select(Persona)).all() == []
        assert session.exec(select(Cliente)).all() == []


def test_customer_identity_and_history(commercial_engine):
    service = ClienteService()
    with Session(commercial_engine) as session:
        catalog = TipoCliente(nombre="Regular", descuento=Decimal("5"))
        session.add(catalog)
        session.commit()
        customer = service.create(
            session,
            ClienteCreate(persona_nueva=person_draft(), tipo_cliente_id=catalog.id),
        )
        with pytest.raises(HTTPException) as error:
            service.update(session, customer.id, {"persona_id": uuid4()})
        assert error.value.status_code == 409
        service.delete(session, customer.id)
        assert service.get(session, customer.id).activo is False
        with pytest.raises(HTTPException) as error:
            service.create(
                session,
                ClienteCreate(persona_nueva=person_draft(), tipo_cliente_id=catalog.id),
            )
        assert error.value.status_code == 409
        assert error.value.detail["accion"] == "reactivar"
        assert service.reactivate(session, customer.id).id == customer.id
        read = service.to_read(session, customer)
        assert read.persona.nombre == "Ana"
        assert read.tipo_cliente_nombre == "Regular"


def supplier_draft():
    return {**person_draft("1710034065001"), "tipo_identificacion": "RUC"}


def society_payload(**changes):
    return {
        "ruc": "0190363902001",
        "razon_social": "  Empresa SA  ",
        "direccion": "  Quito  ",
        "email": "contacto@example.com",
        "tipo_contribuyente_id": "02",
        "persona_contacto_nueva": person_draft(),
        **changes,
    }


def seed_catalogs(session):
    catalog = TipoClienteService().create(
        session, {"nombre": "Regular", "descuento": "5.25"}
    )
    session.add_all(
        [
            TipoContribuyente(
                codigo="01", nombre="Natural", aplica_persona_natural=True
            ),
            TipoContribuyente(codigo="02", nombre="Sociedad", aplica_sociedad=True),
            TipoContribuyente(
                codigo="99", nombre="Natural y sociedad por etiqueta solamente"
            ),
        ]
    )
    session.commit()
    return catalog


def all_records(session, model):
    return session.exec(select(model).execution_options(include_inactive=True)).all()


@pytest.mark.parametrize(
    "create_model,fields,id_field,new_field",
    [
        (ClienteCreate, {"tipo_cliente_id": uuid4()}, "persona_id", "persona_nueva"),
        (
            ProveedorPersonaCreate,
            {"tipo_contribuyente_id": "01"},
            "persona_id",
            "persona_nueva",
        ),
        (
            ProveedorSociedadCreate,
            {
                key: value
                for key, value in society_payload().items()
                if key != "persona_contacto_nueva"
            },
            "persona_contacto_id",
            "persona_contacto_nueva",
        ),
    ],
)
def test_commercial_create_union(create_model, fields, id_field, new_field):
    for alternatives in (
        {},
        {id_field: None},
        {id_field: uuid4(), new_field: person_draft()},
    ):
        with pytest.raises(ValidationError):
            create_model.model_validate({**fields, **alternatives})
    assert (
        getattr(create_model.model_validate({**fields, id_field: uuid4()}), id_field)
        is not None
    )
    assert (
        getattr(
            create_model.model_validate({**fields, new_field: person_draft()}),
            new_field,
        )
        is not None
    )


@pytest.mark.parametrize(
    "model",
    [ClienteUpdate, ProveedorPersonaUpdate, ProveedorSociedadUpdate, TipoClienteUpdate],
)
def test_commercial_update_forbids_internal_fields(model):
    for field in (
        "activo",
        "created_by",
        "updated_by",
        "creado_en",
        "actualizado_en",
        "desconocido",
    ):
        with pytest.raises(ValidationError):
            model.model_validate({field: True})


def test_type_normalization_dependencies_and_reactivation(commercial_engine):
    with Session(commercial_engine) as session:
        service = TipoClienteService()
        catalog = service.create(
            session, TipoClienteCreate(nombre="  Preferente  ", descuento="12.50")
        )
        assert catalog.nombre == "Preferente"
        assert catalog.descuento == Decimal("12.50")
        with pytest.raises(HTTPException) as error:
            service.create(session, {"nombre": " preferente ", "descuento": 0})
        assert error.value.status_code == 409
        customer = ClienteService().create(
            session,
            ClienteCreate(persona_nueva=person_draft(), tipo_cliente_id=catalog.id),
        )
        with pytest.raises(HTTPException) as error:
            service.delete(session, catalog.id)
        assert error.value.status_code == 409
        assert error.value.detail["dependencias"] == [
            {"tipo": "cliente", "id": str(customer.id)}
        ]
        assert service.get(session, catalog.id).activo
        ClienteService().delete(session, customer.id)
        service.delete(session, catalog.id)
        with pytest.raises(HTTPException) as error:
            service.create(session, {"nombre": "PREFERENTE", "descuento": 0})
        assert error.value.detail["id"] == str(catalog.id)
        assert error.value.detail["accion"] == "reactivar"
        actor = str(uuid4())
        token = set_current_user_id(actor)
        try:
            revived = service.reactivate(session, catalog.id)
        finally:
            reset_current_user_id(token)
        assert revived.id == catalog.id and revived.activo
        assert revived.usuario_auditoria == actor and revived.updated_by == actor


@pytest.mark.parametrize("discount", ["-0.01", "100.01", "NaN", "Infinity"])
def test_type_service_rejects_invalid_discount(commercial_engine, discount):
    with Session(commercial_engine) as session:
        with pytest.raises(HTTPException) as error:
            TipoClienteService().create(
                session, {"nombre": "Regular", "descuento": discount}
            )
        assert error.value.status_code == 400
        assert all_records(session, TipoCliente) == []


def test_customer_type_change_and_inactive_references(commercial_engine):
    with Session(commercial_engine) as session:
        service = ClienteService()
        catalog = seed_catalogs(session)
        replacement = TipoClienteService().create(
            session, {"nombre": "Otro", "descuento": 0}
        )
        customer = service.create(
            session,
            ClienteCreate(persona_nueva=person_draft(), tipo_cliente_id=catalog.id),
        )
        person_id = customer.persona_id
        changed = service.update(
            session,
            customer.id,
            {"persona_id": person_id, "tipo_cliente_id": replacement.id},
        )
        assert (
            changed.persona_id == person_id
            and changed.tipo_cliente_id == replacement.id
        )
        service.delete(session, customer.id)
        TipoClienteService().delete(session, replacement.id)
        with pytest.raises(HTTPException) as error:
            service.reactivate(session, customer.id)
        assert error.value.status_code == 409
        assert service.get(session, customer.id).activo is False
        TipoClienteService().reactivate(session, replacement.id)
        person = session.get(Persona, person_id)
        person.activo = False
        session.add(person)
        session.commit()
        with pytest.raises(HTTPException) as error:
            service.reactivate(session, customer.id)
        assert error.value.status_code == 409
        assert error.value.detail["persona_id"] == str(person_id)


def test_supplier_composition_history_and_independent_deletion(commercial_engine):
    with Session(commercial_engine) as session:
        catalog = seed_catalogs(session)
        supplier_service = ProveedorPersonaService()
        supplier = supplier_service.create(
            session,
            ProveedorPersonaCreate(
                persona_nueva=supplier_draft(), tipo_contribuyente_id="01"
            ),
        )
        customer = ClienteService().create(
            session,
            ClienteCreate(persona_id=supplier.persona_id, tipo_cliente_id=catalog.id),
        )
        person = session.get(Persona, supplier.persona_id)
        supplier_service.delete(session, supplier.id)
        assert person.activo and customer.activo
        with pytest.raises(HTTPException) as error:
            supplier_service.create(
                session,
                ProveedorPersonaCreate(
                    persona_nueva=supplier_draft(), tipo_contribuyente_id="01"
                ),
            )
        assert error.value.detail["accion"] == "reactivar"
        revived = supplier_service.reactivate(session, supplier.id)
        assert revived.id == supplier.id and revived.activo
        read = supplier_service.to_read(session, revived)
        assert read.persona.identificacion == "1710034065001"
        assert read.tipo_contribuyente_nombre == "Natural"
        with pytest.raises(HTTPException) as error:
            supplier_service.update(session, supplier.id, {"persona_id": uuid4()})
        assert error.value.status_code == 409


@pytest.mark.parametrize("tax_code,expected", [("02", 400), ("99", 400), ("XX", 404)])
def test_supplier_metadata_rule_rolls_back_person(
    commercial_engine, tax_code, expected
):
    with Session(commercial_engine) as session:
        seed_catalogs(session)
        with pytest.raises(HTTPException) as error:
            ProveedorPersonaService().create(
                session,
                ProveedorPersonaCreate(
                    persona_nueva=supplier_draft(), tipo_contribuyente_id=tax_code
                ),
            )
        assert error.value.status_code == expected
    with Session(commercial_engine) as session:
        assert all_records(session, Persona) == []
        assert all_records(session, ProveedorPersona) == []


def test_supplier_cedula_and_inactive_taxpayer_rejected(commercial_engine):
    with Session(commercial_engine) as session:
        seed_catalogs(session)
        with pytest.raises(HTTPException) as error:
            ProveedorPersonaService().create(
                session,
                {
                    "persona_nueva": {
                        **person_draft("1710034065"),
                        "tipo_identificacion": "CEDULA",
                    },
                    "tipo_contribuyente_id": "01",
                },
            )
        assert error.value.status_code == 400
        assert all_records(session, Persona) == []
        taxpayer = session.get(TipoContribuyente, "01")
        taxpayer.activo = False
        session.add(taxpayer)
        session.commit()
        with pytest.raises(HTTPException) as error:
            ProveedorPersonaService().create(
                session,
                {"persona_nueva": supplier_draft(), "tipo_contribuyente_id": "01"},
            )
        assert error.value.status_code == 409
        assert all_records(session, Persona) == []


def test_society_optional_phone_mutable_contact_and_history(commercial_engine):
    with Session(commercial_engine) as session:
        seed_catalogs(session)
        service = ProveedorSociedadService()
        society = service.create(session, ProveedorSociedadCreate(**society_payload()))
        assert society.telefono is None
        assert society.razon_social == "Empresa SA" and society.direccion == "Quito"
        previous = session.get(Persona, society.persona_contacto_id)
        snapshot = previous.model_dump()
        changed = service.update(
            session,
            society.id,
            ProveedorSociedadUpdate(persona_contacto_nueva=person_draft("SECOND123")),
        )
        assert changed.persona_contacto_id != previous.id
        assert session.get(Persona, previous.id).model_dump() == snapshot
        current_id = changed.persona_contacto_id
        changed = service.update(
            session, society.id, {"persona_contacto_id": previous.id}
        )
        assert changed.persona_contacto_id == previous.id
        assert session.get(Persona, current_id).activo
        service.delete(session, society.id)
        assert previous.activo
        with pytest.raises(HTTPException) as error:
            service.create(session, society_payload())
        assert (
            error.value.detail["id"] == str(society.id)
            and error.value.detail["accion"] == "reactivar"
        )
        assert service.reactivate(session, society.id).id == society.id


@pytest.mark.parametrize(
    "change",
    [
        {"ruc": "1710034065001"},
        {"tipo_contribuyente_id": "01"},
        {"email": "invalido"},
        {"razon_social": "  "},
        {"direccion": None},
    ],
)
def test_society_contact_update_rule_failure_rolls_back(commercial_engine, change):
    with Session(commercial_engine) as session:
        seed_catalogs(session)
        service = ProveedorSociedadService()
        society = service.create(session, society_payload())
        society_id, contact_id = society.id, society.persona_contacto_id
        with pytest.raises(HTTPException) as error:
            service.update(
                session,
                society_id,
                {"persona_contacto_nueva": person_draft("ROLLBACK123"), **change},
            )
        assert error.value.status_code in {400, 422}
    with Session(commercial_engine) as session:
        assert len(all_records(session, Persona)) == 1
        assert (
            session.get(ProveedorSociedad, society_id).persona_contacto_id == contact_id
        )


@pytest.mark.parametrize(
    "service_class,model,payload",
    [
        (ClienteService, Cliente, {"persona_nueva": person_draft()}),
        (
            ProveedorPersonaService,
            ProveedorPersona,
            {"persona_nueva": supplier_draft(), "tipo_contribuyente_id": "01"},
        ),
        (ProveedorSociedadService, ProveedorSociedad, society_payload()),
    ],
)
@pytest.mark.parametrize("failure", ["flush", "commit"])
def test_commercial_persistence_failure_rolls_back_all(
    commercial_engine, monkeypatch, service_class, model, payload, failure
):
    with Session(commercial_engine) as session:
        catalog = seed_catalogs(session)
        service = service_class()
        incoming = {
            **payload,
            **({"tipo_cliente_id": catalog.id} if model is Cliente else {}),
        }
        if failure == "commit":
            monkeypatch.setattr(
                session,
                "commit",
                lambda: (_ for _ in ()).throw(RuntimeError("commit failure")),
            )
        else:
            original = service.repo.create

            def fail_after_flush(session, data):
                original(session, data)
                raise RuntimeError("flush failure")

            monkeypatch.setattr(service.repo, "create", fail_after_flush)
        with pytest.raises(RuntimeError, match="failure"):
            service.create(session, incoming)
    with Session(commercial_engine) as session:
        assert all_records(session, Persona) == []
        assert all_records(session, model) == []


@pytest.mark.parametrize("failure", ["flush", "commit"])
def test_society_contact_persistence_failure_rolls_back(
    commercial_engine, monkeypatch, failure
):
    with Session(commercial_engine) as session:
        seed_catalogs(session)
        service = ProveedorSociedadService()
        society = service.create(session, society_payload())
        society_id, contact_id = society.id, society.persona_contacto_id
        if failure == "commit":
            monkeypatch.setattr(
                session,
                "commit",
                lambda: (_ for _ in ()).throw(RuntimeError("commit failure")),
            )
        else:
            original = service.repo.update

            def fail_after_flush(session, obj, data):
                original(session, obj, data)
                raise RuntimeError("flush failure")

            monkeypatch.setattr(service.repo, "update", fail_after_flush)
        with pytest.raises(RuntimeError):
            service.update(
                session,
                society_id,
                {
                    "persona_contacto_nueva": person_draft("ROLLBACK123"),
                    "razon_social": "Cambiada",
                },
            )
    with Session(commercial_engine) as session:
        assert len(all_records(session, Persona)) == 1
        society = session.get(ProveedorSociedad, society_id)
        assert (
            society.persona_contacto_id == contact_id
            and society.razon_social == "Empresa SA"
        )


@pytest.mark.parametrize("model", [Cliente, ProveedorPersona])
def test_role_unique_constraint_includes_inactive(commercial_engine, model):
    with Session(commercial_engine) as session:
        catalog = seed_catalogs(session)
        supplier = ProveedorPersonaService().create(
            session, {"persona_nueva": supplier_draft(), "tipo_contribuyente_id": "01"}
        )
        customer = ClienteService().create(
            session, {"persona_id": supplier.persona_id, "tipo_cliente_id": catalog.id}
        )
        original = customer if model is Cliente else supplier
        original.activo = False
        session.add(original)
        session.commit()
        duplicate = model(**{**original.model_dump(), "id": uuid4(), "activo": True})
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        assert len(all_records(session, model)) == 1


def test_type_normalized_name_constraint(commercial_engine):
    with Session(commercial_engine) as session:
        catalog = TipoClienteService().create(
            session, {"nombre": "Regular", "descuento": 0}
        )
        TipoClienteService().delete(session, catalog.id)
        session.add(TipoCliente(nombre=" REGULAR ", descuento=0))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        assert len(all_records(session, TipoCliente)) == 1


@pytest.mark.parametrize(
    "service_class,payload",
    [
        (ClienteService, {"persona_nueva": person_draft()}),
        (
            ProveedorPersonaService,
            {"persona_nueva": supplier_draft(), "tipo_contribuyente_id": "01"},
        ),
        (ProveedorSociedadService, society_payload()),
    ],
)
def test_embedded_person_permission_and_authoritative_audit(
    commercial_engine, monkeypatch, service_class, payload
):
    with Session(commercial_engine) as session:
        catalog = seed_catalogs(session)
        service = service_class()
        incoming = {
            **payload,
            "usuario_auditoria": "forged",
            **(
                {"tipo_cliente_id": catalog.id}
                if service_class is ClienteService
                else {}
            ),
        }
        actor = str(uuid4())
        token = set_current_user_id(actor)
        seen = []

        def permission(session, user_id, module, action):
            seen.append((module, action))
            if action == "crear":
                raise HTTPException(
                    status_code=403, detail="Sin permiso PERSONAS crear"
                )

        monkeypatch.setattr(
            "osiris.modules.common.persona.composition.requiere_permiso", permission
        )
        try:
            with pytest.raises(HTTPException) as error:
                service.create(session, incoming)
            assert error.value.status_code == 403
            assert all_records(session, Persona) == []
            monkeypatch.setattr(
                "osiris.modules.common.persona.composition.requiere_permiso",
                lambda *args: None,
            )
            result = service.create(session, incoming)
        finally:
            reset_current_user_id(token)
        assert seen == [("PERSONAS", "leer"), ("PERSONAS", "crear")]
        assert result.usuario_auditoria == actor and result.created_by == actor
        person_id = getattr(result, service.persona_field)
        assert session.get(Persona, person_id).created_by == actor


def test_reuse_person_never_copies_or_overwrites_identity(commercial_engine):
    with Session(commercial_engine) as session:
        catalog = seed_catalogs(session)
        supplier = ProveedorPersonaService().create(
            session, {"persona_nueva": supplier_draft(), "tipo_contribuyente_id": "01"}
        )
        customer = ClienteService().create(
            session,
            {
                "persona_nueva": {**supplier_draft(), "nombre": "No sobrescribir"},
                "tipo_cliente_id": catalog.id,
            },
        )
        assert customer.persona_id == supplier.persona_id
        assert session.get(Persona, customer.persona_id).nombre == "Ana"
        assert len(all_records(session, Persona)) == 1
        assert "nombre" not in customer.model_dump()


@pytest.mark.parametrize(
    "service_class", [ClienteService, ProveedorPersonaService, ProveedorSociedadService]
)
def test_role_lists_search_pagination_history_and_bounded_queries(
    commercial_engine, service_class
):
    with Session(commercial_engine) as session:
        catalog = seed_catalogs(session)
        for position in range(4):
            draft = {
                **supplier_draft(),
                "identificacion": f"SEARCH{position}",
                "tipo_identificacion": "PASAPORTE",
                "nombre": f"Persona {position}",
            }
            customer = ClienteService().create(
                session, {"persona_nueva": draft, "tipo_cliente_id": catalog.id}
            )
            session.add(
                ProveedorPersona(
                    persona_id=customer.persona_id,
                    tipo_contribuyente_id="01",
                    nombre_comercial=f"Proveedor {position}",
                )
            )
            session.add(
                ProveedorSociedad(
                    persona_contacto_id=customer.persona_id,
                    tipo_contribuyente_id="02",
                    ruc=f"019036390{position}001",
                    razon_social=f"Empresa {position}",
                    direccion="Quito",
                    email="contacto@example.com",
                )
            )
            session.commit()
        service = service_class()
        items, meta = service.list_paginated(
            session,
            q="Persona",
            limit=2,
            offset=2,
            sort_by="nombre",
            sort_direction="asc",
        )
        assert meta.total == 4 and len(items) == 2
        assert items[0].persona.nombre == "Persona 2"
        service.delete(session, items[0].id)
        active, meta = service.list_paginated(session, q="SEARCH")
        assert meta.total == 3 and all(item.activo for item in active)
        history, meta = service.list_paginated(session, q="SEARCH", only_active=False)
        assert meta.total == 4 and len(history) == 4
        inactive, meta = service.list_paginated(session, q="SEARCH", estado="inactivo")
        assert meta.total == 1 and inactive[0].activo is False
        statements = []

        def count_query(
            connection, cursor, statement, parameters, context, executemany
        ):
            statements.append(statement)

        event.listen(commercial_engine, "before_cursor_execute", count_query)
        try:
            service.list_paginated(session, only_active=False, limit=100)
        finally:
            event.remove(commercial_engine, "before_cursor_execute", count_query)
        assert len(statements) == 4
        with pytest.raises(HTTPException) as error:
            service.list_paginated(session, sort_by="nombre;DROP TABLE")
        assert error.value.status_code == 422


@pytest.fixture
def commercial_app(commercial_engine):
    app = FastAPI()
    for router in COMMERCIAL_ROUTERS:
        app.include_router(router)

    def session_override():
        with Session(commercial_engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    return app


@pytest.mark.parametrize("router", COMMERCIAL_ROUTERS)
def test_commercial_endpoints_require_authenticated_permission(commercial_app, router):
    from inspect import getclosurevars

    modules = {
        "/api/v1/clientes": "CLIENTES",
        "/api/v1/tipos-cliente": "TIPOS_CLIENTE",
        "/api/v1/proveedores-persona": "PROVEEDORES_PERSONA",
        "/api/v1/proveedores-sociedad": "PROVEEDORES_SOCIEDAD",
    }
    actions = {
        "GET": "leer",
        "POST": "crear",
        "PUT": "actualizar",
        "DELETE": "eliminar",
    }
    with TestClient(commercial_app) as client:
        for route in router.routes:
            method = next(iter(route.methods))
            guard = route.dependencies[0].dependency
            variables = getclosurevars(guard).nonlocals
            assert variables["module"] == modules[router.prefix]
            assert variables["action"] == (
                "actualizar" if route.path.endswith("reactivar") else actions[method]
            )
            response = client.request(
                method, route.path.replace("{item_id}", str(uuid4())), json={}
            )
            assert response.status_code == 401


def authorize_commercial_routes(app):
    for router in COMMERCIAL_ROUTERS:
        for route in router.routes:
            app.dependency_overrides[route.dependencies[0].dependency] = lambda: None


def test_customer_http_contract_and_inactive_detail(commercial_app, commercial_engine):
    authorize_commercial_routes(commercial_app)
    with Session(commercial_engine) as session:
        catalog = seed_catalogs(session)
        type_id = str(catalog.id)
    with TestClient(commercial_app) as client:
        response = client.post(
            "/api/v1/clientes",
            json={"persona_nueva": person_draft(), "tipo_cliente_id": type_id},
        )
        assert response.status_code == 201, response.text
        record = response.json()
        assert (
            record["persona"]["nombre"] == "Ana"
            and record["tipo_cliente_nombre"] == "Regular"
        )
        assert record["creado_en"] and record["actualizado_en"] and record["created_by"]
        assert (
            record["created_at"] == record["creado_en"]
            and record["updated_at"] == record["actualizado_en"]
        )
        path = f"/api/v1/clientes/{record['id']}"
        assert client.put(path, json={"persona_id": str(uuid4())}).status_code == 409
        assert client.put(path, json={"activo": False}).status_code == 422
        assert client.delete(path).status_code == 204
        detail = client.get(path)
        assert detail.status_code == 200 and detail.json()["activo"] is False
        assert (
            client.get("/api/v1/clientes", params={"q": "Ana"}).json()["meta"]["total"]
            == 0
        )
        assert (
            client.get(
                "/api/v1/clientes", params={"q": "Ana", "only_active": "false"}
            ).json()["meta"]["total"]
            == 1
        )
        assert client.post(f"{path}/reactivar").json()["id"] == record["id"]


def test_society_http_optional_contact_union(commercial_app, commercial_engine):
    authorize_commercial_routes(commercial_app)
    with Session(commercial_engine) as session:
        seed_catalogs(session)
    with TestClient(commercial_app) as client:
        response = client.post("/api/v1/proveedores-sociedad", json=society_payload())
        assert response.status_code == 201, response.text
        record = response.json()
        assert record["telefono"] is None and record["persona"]["nombre"] == "Ana"
        path = f"/api/v1/proveedores-sociedad/{record['id']}"
        invalid = client.put(
            path,
            json={
                "persona_contacto_id": record["persona_contacto_id"],
                "persona_contacto_nueva": person_draft("NEW123"),
            },
        )
        assert invalid.status_code == 422
        assert client.put(path, json={"persona_contacto_id": None}).status_code == 422
        updated = client.put(
            path, json={"persona_contacto_nueva": person_draft("NEW123")}
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["persona_contacto_id"] != record["persona_contacto_id"]


def test_society_unique_ruc_and_real_foreign_key_constraints(commercial_engine):
    with Session(commercial_engine) as session:
        seed_catalogs(session)
        society = ProveedorSociedadService().create(session, society_payload())
        ProveedorSociedadService().delete(session, society.id)
        session.add(
            ProveedorSociedad(**{**society.model_dump(), "id": uuid4(), "activo": True})
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        invalid = {
            **society.model_dump(),
            "id": uuid4(),
            "ruc": "1790012345001",
            "persona_contacto_id": uuid4(),
        }
        session.add(ProveedorSociedad(**invalid))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        assert len(all_records(session, ProveedorSociedad)) == 1


@pytest.mark.parametrize(
    "service_class,model,payload",
    [
        (
            ClienteService,
            Cliente,
            {"persona_nueva": person_draft(), "tipo_cliente_id": uuid4()},
        ),
        (
            ProveedorPersonaService,
            ProveedorPersona,
            {"persona_nueva": supplier_draft(), "tipo_contribuyente_id": "XX"},
        ),
        (
            ProveedorSociedadService,
            ProveedorSociedad,
            society_payload(tipo_contribuyente_id="XX"),
        ),
    ],
)
def test_database_foreign_key_failure_rolls_back_new_person(
    commercial_engine, monkeypatch, service_class, model, payload
):
    with Session(commercial_engine) as session:
        seed_catalogs(session)
        service = service_class()
        monkeypatch.setattr(service, "validate_create", lambda *args: None)
        monkeypatch.setattr(service, "_check_fk_active_and_exists", lambda *args: None)
        with pytest.raises(HTTPException) as error:
            service.create(session, payload)
        assert error.value.status_code == 409
    with Session(commercial_engine) as session:
        assert all_records(session, Persona) == []
        assert all_records(session, model) == []


@pytest.mark.parametrize(
    "service_class,model,payload",
    [
        (
            ProveedorPersonaService,
            ProveedorPersona,
            {"persona_nueva": supplier_draft(), "tipo_contribuyente_id": "01"},
        ),
        (ProveedorSociedadService, ProveedorSociedad, society_payload()),
    ],
)
def test_supplier_reactivation_requires_active_catalog(
    commercial_engine, service_class, model, payload
):
    with Session(commercial_engine) as session:
        seed_catalogs(session)
        service = service_class()
        supplier = service.create(session, payload)
        service.delete(session, supplier.id)
        catalog = session.get(TipoContribuyente, supplier.tipo_contribuyente_id)
        catalog.activo = False
        session.add(catalog)
        session.commit()
        with pytest.raises(HTTPException) as error:
            service.reactivate(session, supplier.id)
        assert error.value.status_code == 409
        assert service.get(session, supplier.id).activo is False


def test_contextual_lookup_requires_person_read_permission(
    commercial_engine, monkeypatch
):
    with Session(commercial_engine) as session:
        catalog = seed_catalogs(session)
        supplier = ProveedorPersonaService().create(
            session, {"persona_nueva": supplier_draft(), "tipo_contribuyente_id": "01"}
        )
        actor = str(uuid4())

        def deny(*args):
            raise HTTPException(status_code=403, detail="Sin permiso PERSONAS leer")

        monkeypatch.setattr(
            "osiris.modules.common.persona.composition.requiere_permiso", deny
        )
        token = set_current_user_id(actor)
        try:
            with pytest.raises(HTTPException) as error:
                ClienteService().create(
                    session,
                    {"persona_id": supplier.persona_id, "tipo_cliente_id": catalog.id},
                )
            assert error.value.status_code == 403
        finally:
            reset_current_user_id(token)
        assert all_records(session, Cliente) == []
        assert len(all_records(session, Persona)) == 1


@pytest.mark.parametrize("router", COMMERCIAL_ROUTERS)
def test_denied_commercial_endpoint_never_persists(
    commercial_app, commercial_engine, router
):
    def deny():
        raise HTTPException(status_code=403, detail="Sin permiso de modulo")

    for route in router.routes:
        commercial_app.dependency_overrides[route.dependencies[0].dependency] = deny
    with TestClient(commercial_app) as client:
        for route in router.routes:
            response = client.request(
                next(iter(route.methods)),
                route.path.replace("{item_id}", str(uuid4())),
                json={},
            )
            assert response.status_code == 403
    with Session(commercial_engine) as session:
        assert all(all_records(session, model) == [] for model in COMMERCIAL_MODELS)


@pytest.fixture
def commercial_postgresql_engine():
    value = os.getenv("DIRECTORY_TEST_DATABASE_URL")
    if not value:
        pytest.skip("Requiere DIRECTORY_TEST_DATABASE_URL de PostgreSQL autorizado")
    url = make_url(value)
    if url.get_backend_name() != "postgresql":
        pytest.fail("DIRECTORY_TEST_DATABASE_URL debe apuntar a PostgreSQL")
    url = url.set(drivername="postgresql+psycopg")
    admin = create_engine(url)
    schema = f"directory_commercial_{uuid4().hex}"
    engine = None
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    try:
        engine = create_engine(
            url,
            connect_args={
                "options": f"-c search_path={schema} -c lock_timeout=15000 -c statement_timeout=20000"
            },
        )
        commercial_metadata().create_all(engine)
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def test_postgresql_person_deactivation_serializes_against_customer_creation(
    commercial_postgresql_engine,
):
    engine = commercial_postgresql_engine
    with Session(engine) as session:
        catalog_id = seed_catalogs(session).id
        person_id = (
            PersonaService()
            .create(
                session,
                {
                    **person_draft("PGRACE123"),
                    "usuario_auditoria": "test",
                },
            )
            .id
        )
    barrier = Barrier(2)

    def perform(action):
        with Session(engine) as session:
            barrier.wait(timeout=10)
            try:
                if action == "create":
                    ClienteService().create(
                        session,
                        {"persona_id": person_id, "tipo_cliente_id": catalog_id},
                    )
                    return 201
                PersonaService().delete(session, person_id)
                return 204
            except HTTPException as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = sorted(executor.map(perform, ["create", "deactivate"]))
    assert outcomes in ([201, 409], [204, 409])
    with Session(engine) as session:
        person = session.exec(
            select(Persona)
            .where(Persona.id == person_id)
            .execution_options(include_inactive=True)
        ).one()
        customers = session.exec(
            select(Cliente).where(Cliente.persona_id == person_id)
        ).all()
        assert not customers or person.activo is True


@pytest.mark.parametrize("same_role", [False, True])
def test_postgresql_competing_commercial_creates(
    commercial_postgresql_engine, monkeypatch, same_role
):
    engine = commercial_postgresql_engine
    with Session(engine) as session:
        catalog_id = seed_catalogs(session).id
    ready = Barrier(2)
    original = PersonaRepository.create

    def competing_insert(repository, session, payload):
        ready.wait(timeout=10)
        return original(repository, session, payload)

    monkeypatch.setattr(PersonaRepository, "create", competing_insert)

    def create_role(customer):
        with Session(engine) as session:
            service = ClienteService() if customer else ProveedorPersonaService()
            payload = {
                "persona_nueva": supplier_draft(),
                **(
                    {"tipo_cliente_id": catalog_id}
                    if customer
                    else {"tipo_contribuyente_id": "01"}
                ),
            }
            try:
                role = service.create(session, payload)
                return {"status": 201, "persona_id": role.persona_id, "id": role.id}
            except HTTPException as error:
                return {"status": error.status_code, "detail": error.detail}

    with ThreadPoolExecutor(max_workers=2) as executor:
        requests = [
            executor.submit(create_role, True),
            executor.submit(create_role, same_role),
        ]
        results = [request.result(timeout=30) for request in requests]
    assert sorted(result["status"] for result in results) == (
        [201, 409] if same_role else [201, 201]
    )
    with Session(engine) as session:
        persons = all_records(session, Persona)
        assert len(persons) == 1 and persons[0].nombre == "Ana"
        assert len(all_records(session, Cliente)) == 1
        assert len(all_records(session, ProveedorPersona)) == (0 if same_role else 1)
        assert all(
            result["persona_id"] == persons[0].id
            for result in results
            if result["status"] == 201
        )


def test_postgresql_inactive_person_conflict(commercial_postgresql_engine):
    with Session(commercial_postgresql_engine) as session:
        catalog = seed_catalogs(session)
        person = Persona(**supplier_draft(), activo=False)
        session.add(person)
        session.commit()
        person_id = person.id
        with pytest.raises(HTTPException) as error:
            ClienteService().create(
                session,
                {"persona_nueva": supplier_draft(), "tipo_cliente_id": catalog.id},
            )
        assert error.value.status_code == 409
        assert (
            error.value.detail["persona_id"] == str(person_id)
            and error.value.detail["accion"] == "reactivar"
        )
        assert (
            len(all_records(session, Persona)) == 1
            and all_records(session, Cliente) == []
        )


def test_postgresql_customer_creation_competes_with_type_deactivation(
    commercial_postgresql_engine,
):
    engine = commercial_postgresql_engine
    with Session(engine) as session:
        catalog_id = seed_catalogs(session).id
    ready = Barrier(2)

    def operation(deactivate):
        with Session(engine) as session:
            ready.wait(timeout=10)
            try:
                if deactivate:
                    TipoClienteService().delete(session, catalog_id)
                else:
                    ClienteService().create(
                        session,
                        {
                            "persona_nueva": person_draft(),
                            "tipo_cliente_id": catalog_id,
                        },
                    )
                return 200
            except HTTPException as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        requests = [executor.submit(operation, True), executor.submit(operation, False)]
        assert sorted(request.result(timeout=30) for request in requests) == [200, 409]
    with Session(engine) as session:
        catalog = TipoClienteService().get(session, catalog_id)
        customers = all_records(session, Cliente)
        assert catalog.activo == bool(customers)
        assert len(all_records(session, Persona)) == len(customers)


def test_postgresql_constraints_cover_commercial_history(commercial_postgresql_engine):
    with Session(commercial_postgresql_engine) as session:
        catalog = seed_catalogs(session)
        supplier = ProveedorPersonaService().create(
            session, {"persona_nueva": supplier_draft(), "tipo_contribuyente_id": "01"}
        )
        customer = ClienteService().create(
            session, {"persona_id": supplier.persona_id, "tipo_cliente_id": catalog.id}
        )
        society = ProveedorSociedadService().create(
            session,
            society_payload(
                persona_contacto_nueva=None, persona_contacto_id=supplier.persona_id
            ),
        )
        for model, original in (
            (Cliente, customer),
            (ProveedorPersona, supplier),
            (ProveedorSociedad, society),
        ):
            original.activo = False
            session.add(original)
            session.commit()
            session.add(
                model(**{**original.model_dump(), "id": uuid4(), "activo": True})
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
            assert len(all_records(session, model)) == 1
        session.add(TipoCliente(nombre=" REGULAR ", descuento=0))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.add(Cliente(persona_id=uuid4(), tipo_cliente_id=catalog.id))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

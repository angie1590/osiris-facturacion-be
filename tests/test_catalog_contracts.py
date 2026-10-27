from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from fastapi.routing import APIRoute

from osiris.domain.catalog_contracts import (
    AssignmentInput,
    AttributeCreate,
    AttributeUpdate,
    B3Confirmation,
    CategoryCreate,
    CategoryUpdate,
    ConfigurationInput,
    Confirmation,
    EffectiveAttribute,
    ErrorDetail,
    LifecycleInput,
    PreviewInput,
    SelectableCategory,
    UnitInput,
    UnitUpdate,
    CategoryTreeNode,
    CatalogError,
    PreviewResponse,
    UnitRead,
    create_contract_app,
)


IDENTITY = "11111111-1111-4111-8111-111111111111"


@pytest.mark.parametrize("field,value", [
    ("obligatorio", False), ("valor_default", None), ("orden", 0),
    ("aplicar_default_a_existentes", False),
])
def test_global_attribute_update_forbids_mapping_configuration(field: str, value: Any) -> None:
    with pytest.raises(ValidationError) as error:
        AttributeUpdate.model_validate_json(json.dumps({field: value}))
    assert error.value.errors()[0]["type"] == "extra_forbidden"
    assert error.value.errors()[0]["loc"] == (field,)
    payload = {"nombre": "RAM", "tipo_dato": "integer", "categoria_id": IDENTITY, field: value}
    assert AttributeCreate.model_validate_json(json.dumps(payload)).model_dump(
        mode="json", exclude_unset=True
    ) == payload
    with TestClient(create_contract_app()) as client:
        target = f"/api/v1/atributos/{IDENTITY}"
        assert client.put(target, json={field: value}).status_code == 422
        assert client.put(target, json={
            "payload": {field: value}, "precondicion_preview": "opaque",
        }).status_code == 422
        assert client.post(target + "/previsualizar", json={
            "operacion": "actualizar", "payload": {field: value},
        }).status_code == 422


def test_configuration_omission_null_and_backfill() -> None:
    omitted = ConfigurationInput.model_validate_json("{}")
    cleared = ConfigurationInput.model_validate_json('{"valor_default":null,"orden":null}')
    assert omitted.model_dump(exclude_unset=True) == {}
    assert cleared.model_dump(exclude_unset=True) == {"valor_default": None, "orden": None}
    assert omitted.aplicar_default_a_existentes is False
    assert omitted.valor_default is None
    assert omitted.obligatorio is False


@pytest.mark.parametrize("value", [0, False, "0", 1.25, None])
def test_default_preserves_explicit_value(value: Any) -> None:
    dto = ConfigurationInput.model_validate_json(json.dumps({"valor_default": value}))
    assert dto.valor_default == value
    assert type(dto.valor_default) is type(value)


@pytest.mark.parametrize("payload", [
    {"obligatorio": None}, {"obligatorio": "true"}, {"orden": True},
    {"orden": "1"}, {"aplicar_default_a_existentes": None},
    {"unidad_id": IDENTITY}, {"nombre": "Global"}, {"tipo_dato": "integer"},
    {"usuario_auditoria": "forged"}, {"valor_default": float("nan")},
])
def test_configuration_is_strict_and_local(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ConfigurationInput.model_validate_json(json.dumps(payload))


def test_uuid_json_and_assignment_identity() -> None:
    assignment = AssignmentInput.model_validate_json(json.dumps({"atributo_id": IDENTITY}))
    assert assignment.atributo_id == UUID(IDENTITY)
    assert AssignmentInput.model_validate({"atributo_id": IDENTITY}) == assignment
    assert AssignmentInput.model_validate({"atributo_id": UUID(IDENTITY)}) == assignment
    with pytest.raises(ValidationError):
        AssignmentInput.model_validate_json('{"atributo_id":"not-a-uuid"}')


@pytest.mark.parametrize("value", ["not-a-uuid", 1, 1.5, True, None, [], {}, b"uuid"])
def test_uuid_does_not_coerce_non_strings(value: Any) -> None:
    with pytest.raises(ValidationError):
        AssignmentInput.model_validate({"atributo_id": value})


@pytest.mark.parametrize("field,value", [
    ("categoria_id", "not-a-uuid"), ("unidad_id", "not-a-uuid"),
    ("catalog_id", "not-a-uuid"), ("categoria_id", 1), ("unidad_id", True),
    ("catalog_id", []), ("categoria_id", None), ("orden", "1"),
    ("orden", True), ("orden", 1.5), ("obligatorio", "true"),
    ("allow_negative", 1), ("confirmar_anotacion_unidad", "false"),
    ("aplicar_default_a_existentes", 0), ("usuario_auditoria", "forged"),
])
def test_attribute_http_body_remains_strict(field: str, value: Any) -> None:
    payload = {"nombre": "RAM", "tipo_dato": "integer", "categoria_id": IDENTITY,
               "unidad_id": IDENTITY, "catalog_id": IDENTITY, field: value}
    with TestClient(create_contract_app()) as client:
        for target, body in (
            ("/atributos", payload),
            ("/atributos", {"payload": payload, "precondicion_preview": "opaque"}),
            ("/atributos/previsualizar", {"operacion": "crear", "payload": payload}),
        ):
            response = client.post("/api/v1" + target, json=body)
            assert response.status_code == 422, response.text
            assert any(field in error["loc"] for error in response.json()["detail"])


@pytest.mark.parametrize("field,value", [
    ("atributo_id", "not-a-uuid"), ("atributo_id", 1), ("atributo_id", False),
    ("atributo_id", {}), ("atributo_id", None), ("orden", "1"),
    ("orden", True), ("obligatorio", 1), ("aplicar_default_a_existentes", "false"),
    ("usuario_auditoria", "forged"),
])
def test_assignment_http_body_remains_strict(field: str, value: Any) -> None:
    payload = {"atributo_id": IDENTITY, field: value}
    target = f"/api/v1/categorias/{IDENTITY}/atributos"
    with TestClient(create_contract_app()) as client:
        for path, body in (
            (target, payload),
            (target, {"payload": payload, "precondicion_preview": "opaque"}),
            (target + "/previsualizar", {"operacion": "asignar", "payload": payload}),
        ):
            response = client.post(path, json=body)
            assert response.status_code == 422, response.text
            assert any(field in error["loc"] for error in response.json()["detail"])


def test_move_to_root_differs_from_omission() -> None:
    assert CategoryUpdate.model_validate_json("{}").model_fields_set == set()
    assert CategoryUpdate.model_validate_json('{"parent_id":null}').model_fields_set == {
        "parent_id"
    }
    with pytest.raises(ValidationError):
        CategoryUpdate.model_validate_json('{"es_padre":true}')


@pytest.mark.parametrize("symbol", ["MB", "Mb", "%", "mL"])
def test_unit_preserves_symbol_case(symbol: str) -> None:
    dto = UnitInput(codigo="MEGABYTE", nombre="Megabyte", simbolo=symbol,
                    magnitud_codigo="DATA_STORAGE")
    assert dto.simbolo == symbol


def test_unit_read_exposes_backend_usage_counts() -> None:
    unit = UnitRead.model_validate({
        "id": IDENTITY,
        "codigo": "GIGABYTE",
        "nombre": "Gigabyte",
        "simbolo": "GB",
        "magnitud_codigo": "DATA_STORAGE",
        "es_sistema": True,
        "activo": True,
        "creado_en": datetime(2026, 10, 27),
        "actualizado_en": datetime(2026, 10, 27),
        "usuario_auditoria": None,
        "uso": {
            "atributos_activos": 2,
            "atributos_inactivos": 1,
            "snapshots_historicos": 3,
        },
    })
    assert unit.uso.model_dump() == {
        "atributos_activos": 2,
        "atributos_inactivos": 1,
        "snapshots_historicos": 3,
    }


@pytest.mark.parametrize("field", ["codigo", "simbolo", "magnitud_codigo", "nombre"])
def test_unit_rejects_blank_fields(field: str) -> None:
    payload = {"codigo": "GB", "nombre": "Gigabyte", "simbolo": "GB",
               "magnitud_codigo": "DATA_STORAGE"}
    payload[field] = " "
    with pytest.raises(ValidationError):
        UnitInput.model_validate(payload)


@pytest.mark.parametrize("kind", ["integer", "decimal"])
def test_numeric_definition_accepts_unit(kind: str) -> None:
    dto = AttributeCreate.model_validate_json(json.dumps({
        "nombre": "RAM", "tipo_dato": kind, "unidad_id": IDENTITY,
        "categoria_id": IDENTITY,
    }))
    assert dto.unidad_id == UUID(IDENTITY)
    assert dto.aplicar_default_a_existentes is False


@pytest.mark.parametrize("kind", ["string", "boolean", "date", "select", "catalog"])
def test_non_numeric_definition_rejects_unit(kind: str) -> None:
    with pytest.raises(ValidationError, match="ATTRIBUTE_UNIT_INVALID_TYPE"):
        AttributeCreate.model_validate_json(json.dumps({
            "nombre": "SKU", "tipo_dato": kind, "unidad_id": IDENTITY,
            "categoria_id": IDENTITY,
        }))


def test_partial_update_defers_unknown_type_to_future_service() -> None:
    dto = AttributeUpdate.model_validate_json(json.dumps({"unidad_id": IDENTITY}))
    assert dto.model_fields_set == {"unidad_id"}
    with pytest.raises(ValidationError, match="ATTRIBUTE_UNIT_INVALID_TYPE"):
        AttributeUpdate.model_validate_json(json.dumps({
            "unidad_id": IDENTITY, "tipo_dato": "boolean",
        }))


@pytest.mark.parametrize("model,field", [
    (UnitUpdate, "codigo"), (UnitUpdate, "nombre"), (UnitUpdate, "simbolo"),
    (UnitUpdate, "magnitud_codigo"), (CategoryUpdate, "nombre"),
    (AttributeUpdate, "nombre"), (AttributeUpdate, "tipo_dato"),
])
def test_non_nullable_patch_fields_allow_omission_only(model: Any, field: str) -> None:
    assert model.model_validate_json("{}").model_dump(exclude_unset=True) == {}
    with pytest.raises(ValidationError, match="explicit null is invalid"):
        model.model_validate_json(json.dumps({field: None}))
    schema = model.model_json_schema()["properties"][field]
    assert "anyOf" not in schema
    assert "default" not in schema


def test_effective_fixture_keeps_explicit_null_origin_and_unit() -> None:
    fixture = {
        "mapping_id": IDENTITY, "atributo_id": IDENTITY, "codigo": "memoria_ram",
        "nombre": "Memoria RAM", "tipo_dato": "integer",
        "unidad": {"id": IDENTITY, "codigo": "GIGABYTE", "nombre": "Gigabyte",
                   "simbolo": "GB", "magnitud_codigo": "DATA_STORAGE"},
        "restricciones": {"allow_negative": False, "min_value": None, "max_value": None},
        "select_options": None, "catalog_id": None, "obligatorio": True,
        "valor_default": None, "orden": None,
        "categoria_origen": {"id": IDENTITY, "nombre": "Computadores"},
        "profundidad": 1, "heredado": True,
    }
    dto = EffectiveAttribute.model_validate_json(json.dumps(fixture))
    assert EffectiveAttribute.model_validate(fixture) == dto
    assert dto.model_dump(mode="json") == fixture
    del fixture["orden"]
    with pytest.raises(ValidationError):
        EffectiveAttribute.model_validate_json(json.dumps(fixture))


def test_confirmation_preserves_exact_payload_and_opaque_token() -> None:
    dto = Confirmation[ConfigurationInput].model_validate_json(json.dumps({
        "payload": {"valor_default": None, "aplicar_default_a_existentes": False},
        "precondicion_preview": "opaque-not-decoded-even-if-expired",
    }))
    assert dto.model_dump(mode="json", exclude_unset=True)["payload"] == {
        "valor_default": None, "aplicar_default_a_existentes": False,
    }
    for token in (None, "", " "):
        with pytest.raises(ValidationError):
            Confirmation[ConfigurationInput].model_validate_json(json.dumps({
                "payload": {}, "precondicion_preview": token,
            }))


def test_selectable_category_excludes_parents_and_temporary_nodes() -> None:
    payload = {"id": IDENTITY, "nombre": "Laptop", "parent_id": None,
               "tiene_hijos": False, "is_default": False, "activo": True,
               "atributos_propios_count": 0, "atributos_efectivos_count": 1}
    SelectableCategory.model_validate_json(json.dumps(payload))
    for field, value in (("tiene_hijos", True), ("is_default", True), ("activo", False)):
        with pytest.raises(ValidationError):
            SelectableCategory.model_validate_json(json.dumps({**payload, field: value}))


def test_error_codes_are_canonical() -> None:
    for code in ("UNIT_DUPLICATE_CODE", "UNIT_DUPLICATE_SYMBOL", "CATALOG_PREVIEW_STALE"):
        dto = ErrorDetail.model_validate_json(json.dumps({
            "code": code, "message": "Conflicto", "conteos": {},
            "acciones_permitidas": ["previsualizar"],
        }))
        assert dto.affected_ids == []
    with pytest.raises(ValidationError):
        ErrorDetail.model_validate_json(json.dumps({
            "code": "UNIT_CODE_DUPLICATE", "message": "Conflicto", "conteos": {},
            "acciones_permitidas": [],
        }))


def test_contract_app_is_explicitly_not_runtime() -> None:
    app = create_contract_app()
    schema = app.openapi()
    assert "NOT DEPLOYED" in schema["info"]["title"]
    with TestClient(app) as client:
        assert client.get("/api/v1/categorias/arbol").status_code == 501
        assert client.get(f"/api/v1/unidades/{IDENTITY}").status_code == 501
        assert client.post("/api/v1/unidades", json={
            "codigo": "GB", "nombre": "Gigabyte", "simbolo": "GB",
            "magnitud_codigo": "DATA_STORAGE",
        }).status_code == 501
        assert client.get("/api/v1/unidades/not-a-uuid").status_code == 422
    for path in schema["paths"].values():
        for operation in path.values():
            assert operation["x-contract-only"] is True
            assert operation["x-deployed"] is False
            assert "501" in operation["responses"]
            assert "409" in operation["responses"]


def test_contextual_paths_and_unit_filters() -> None:
    schema = create_contract_app().openapi()
    paths = schema["paths"]
    expected = {
        "/categorias": {"get", "post"},
        "/categorias/previsualizar": {"post"},
        "/categorias/arbol": {"get"}, "/categorias/seleccionables": {"get"},
        "/categorias/{id}": {"get", "put", "delete"},
        "/categorias/{id}/previsualizar": {"post"},
        "/categorias/{id}/reactivar": {"post"},
        "/categorias/{id}/atributos-efectivos": {"get"},
        "/categorias/{id}/atributos-propios": {"get"},
        "/categorias/{id}/atributos": {"post"},
        "/categorias/{id}/atributos/previsualizar": {"post"},
        "/categorias/{id}/atributos/{mapping_id}": {"put", "delete"},
        "/categorias/{id}/atributos/{mapping_id}/previsualizar": {"post"},
        "/categorias/{id}/atributos/{mapping_id}/reactivar": {"post"},
        "/atributos": {"get", "post"}, "/atributos/{id}": {"get", "put", "delete"},
        "/atributos/previsualizar": {"post"},
        "/atributos/{id}/previsualizar": {"post"},
        "/atributos/{id}/reactivar": {"post"}, "/atributos/{id}/revertir": {"post"},
        "/atributos/{id}/reversion": {"get"},
        "/unidades": {"get", "post"}, "/unidades/{id}": {"get", "put", "delete"},
        "/unidades/{id}/reactivar": {"post"},
    }
    assert {path.removeprefix("/api/v1"): set(methods) for path, methods in paths.items()} == expected
    parameters = paths["/api/v1/unidades"]["get"]["parameters"]
    assert {param["name"] for param in parameters} == {
        "q", "magnitud_codigo", "only_active", "limit", "offset",
    }
    with TestClient(create_contract_app()) as client:
        for query in ("limit=0", "offset=-1", "only_active=bad"):
            assert client.get("/api/v1/unidades?" + query).status_code == 422


def test_b3_confirmation_requires_literal_consent_and_preview_token() -> None:
    confirmation = B3Confirmation[CategoryCreate].model_validate(
        {
            "payload": {"nombre": "Child", "parent_id": IDENTITY},
            "confirmar_b3": True,
            "precondicion_preview": "opaque-token",
        }
    )
    assert confirmation.confirmar_b3 is True
    with pytest.raises(ValidationError):
        B3Confirmation[CategoryCreate].model_validate(
            {
                "payload": {"nombre": "Child", "parent_id": IDENTITY},
                "confirmar_b3": False,
                "precondicion_preview": "opaque-token",
            }
        )


def test_openapi_required_nullable_strictness_and_examples() -> None:
    schema = create_contract_app().openapi()
    models = schema["components"]["schemas"]
    effective = models["EffectiveAttribute"]
    for field in ("unidad", "valor_default", "orden", "categoria_origen", "mapping_id"):
        assert field in effective["required"]
    assert {"type": "null"} in effective["properties"]["unidad"]["anyOf"]
    config = models["ConfigurationInput"]
    assert config["additionalProperties"] is False
    assert config["properties"]["aplicar_default_a_existentes"]["default"] is False
    assert "valor_default" not in config.get("required", [])
    assert "unidad_id" not in config["properties"]
    assert models["Confirmation_ConfigurationInput_"]["required"] == [
        "precondicion_preview", "payload",
    ]
    for path, model, many in (
        ("/categorias/arbol", CategoryTreeNode, True),
        ("/categorias/seleccionables", SelectableCategory, True),
        ("/categorias/{id}/atributos-efectivos", EffectiveAttribute, True),
        ("/unidades/{id}", UnitRead, False),
    ):
        example = schema["paths"]["/api/v1" + path]["get"]["responses"]["200"][
            "content"
        ]["application/json"]["example"]
        for item in example if many else [example]:
            model.model_validate_json(json.dumps(item))
    preview = schema["paths"]["/api/v1/atributos/{id}/previsualizar"]["post"]["responses"]
    PreviewResponse.model_validate_json(json.dumps(
        preview["200"]["content"]["application/json"]["example"]
    ))
    for example in preview["409"]["content"]["application/json"]["examples"].values():
        CatalogError.model_validate_json(json.dumps(example["value"]))


def test_every_confirmation_has_preview_for_exact_payload_target_and_operation() -> None:
    config = {"obligatorio": False, "valor_default": 0, "orden": None,
              "aplicar_default_a_existentes": False}
    cases: list[tuple[str, str, str, str, Any, dict[str, Any]]] = [
        ("put", "/categorias/{id}", "/categorias/{id}", "actualizar", CategoryUpdate,
         {"nombre": "Portatiles", "parent_id": IDENTITY}),
        ("delete", "/categorias/{id}", "/categorias/{id}", "desactivar", LifecycleInput,
         {"confirmar": False}),
        ("post", "/categorias/{id}/atributos", "/categorias/{id}/atributos", "asignar",
         AssignmentInput, {"atributo_id": IDENTITY, **config}),
        ("post", "/atributos", "/atributos", "crear", AttributeCreate,
         {"nombre": "RAM", "tipo_dato": "integer", "categoria_id": IDENTITY,
                    "unidad_id": IDENTITY, "catalog_id": IDENTITY,
                    "confirmar_anotacion_unidad": False, **config}),
        ("put", "/atributos/{id}", "/atributos/{id}", "actualizar", AttributeUpdate,
                 {"unidad_id": IDENTITY, "catalog_id": IDENTITY,
                    "confirmar_anotacion_unidad": False}),
    ]
    mapping = "/categorias/{id}/atributos/{mapping_id}"
    cases.extend([
        ("put", mapping, mapping, "actualizar", ConfigurationInput, config),
        ("delete", mapping, mapping, "desactivar", LifecycleInput, {"confirmar": False}),
        ("post", mapping + "/reactivar", mapping, "reactivar", ConfigurationInput, config),
    ])
    for method, suffix, operation in (
        ("delete", "", "desactivar"), ("post", "/reactivar", "reactivar"),
        ("post", "/revertir", "revertir"),
    ):
        cases.append((method, "/atributos/{id}" + suffix, "/atributos/{id}", operation,
                      LifecycleInput, {"confirmar": False}))

    app = create_contract_app()
    schema = app.openapi()
    paths = schema["paths"]
    models = schema["components"]["schemas"]

    def body_refs(path: str, method: str) -> list[str]:
        body = paths["/api/v1" + path][method]["requestBody"]["content"]["application/json"][
            "schema"
        ]
        return [item["$ref"].rsplit("/", 1)[-1] for item in body.get("anyOf", [body])]

    confirmed_routes = {
        (method, path.removeprefix("/api/v1"))
        for path, methods in paths.items() for method, endpoint in methods.items()
        if "requestBody" in endpoint
        and any(ref.startswith("Confirmation_") for ref in body_refs(
            path.removeprefix("/api/v1"), method
        ))
    }
    assert confirmed_routes == {(method, target) for method, target, *_ in cases}
    with TestClient(app) as client:
        for method, target, preview_target, operation, model, payload in cases:
            confirmation_name = f"Confirmation_{model.__name__}_"
            preview_name = f"PreviewInput_{model.__name__}_"
            assert confirmation_name in body_refs(target, method)
            assert preview_name in body_refs(preview_target + "/previsualizar", "post")
            assert models[confirmation_name]["properties"]["payload"]["$ref"] == models[preview_name][
                "properties"
            ]["payload"]["$ref"]
            preview_body = {"operacion": operation, "payload": payload}
            confirmation_body = {"payload": payload, "precondicion_preview": "opaque"}
            preview_model = PreviewInput.__class_getitem__(model)
            confirmation_model = Confirmation.__class_getitem__(model)
            assert isinstance(preview_model, type)
            assert isinstance(confirmation_model, type)
            assert preview_model.model_validate_json(json.dumps(preview_body)).model_dump(
                mode="json", exclude_unset=True
            ) == preview_body
            assert confirmation_model.model_validate_json(
                json.dumps(confirmation_body)
            ).model_dump(mode="json", exclude_unset=True) == confirmation_body
            preview_url = "/api/v1" + preview_target.replace("{id}", IDENTITY).replace(
                "{mapping_id}", IDENTITY
            ) + "/previsualizar"
            target_url = "/api/v1" + target.replace("{id}", IDENTITY).replace(
                "{mapping_id}", IDENTITY
            )
            for request_method, url, body in (
                ("post", preview_url, preview_body),
                (method, target_url, payload),
                (method, target_url, confirmation_body),
            ):
                response = client.request(request_method, url, json=body)
                assert response.status_code == 501, (request_method, url, response.text)
                assert response.json()["detail"] == (
                    "Contract only: endpoints are NOT deployed; handlers are not functional."
                )
    route_paths = [route.path for route in app.routes if isinstance(route, APIRoute)]
    assert route_paths.index("/api/v1/atributos/previsualizar") < route_paths.index(
        "/api/v1/atributos/{id}"
    )


def test_remaining_http_paths_reach_contract_only_handler() -> None:
    app = create_contract_app()
    unit = {"codigo": "GB", "nombre": "Gigabyte", "simbolo": "GB",
            "magnitud_codigo": "DATA_STORAGE"}
    with TestClient(app) as client:
        for path, methods in app.openapi()["paths"].items():
            if "get" in methods:
                url = path.replace("{id}", IDENTITY).replace("{mapping_id}", IDENTITY)
                response = client.get(url)
                assert response.status_code == 501, (url, response.text)
        for method, path, body in (
            ("post", "/categorias", {"nombre": "Laptop", "parent_id": IDENTITY}),
            ("post", f"/categorias/{IDENTITY}/reactivar", {"confirmar": False}),
            ("post", "/unidades", unit),
            ("put", f"/unidades/{IDENTITY}", unit),
            ("delete", f"/unidades/{IDENTITY}", {"confirmar": False}),
            ("post", f"/unidades/{IDENTITY}/reactivar", {"confirmar": False}),
        ):
            response = client.request(method, "/api/v1" + path, json=body)
            assert response.status_code == 501, (method, path, response.text)
        assert client.post("/api/v1/categorias", json={
            "nombre": "Laptop", "parent_id": "not-a-uuid",
        }).status_code == 422


def test_export_is_deterministic_and_snapshot_matches() -> None:
    from scripts.export_catalog_contract import render_contract

    rendered = render_contract()
    assert rendered == render_contract()
    snapshot = Path(__file__).resolve().parents[1] / "contracts" / (
        "catalog-administration-v1.openapi.json"
    )
    assert snapshot.read_text(encoding="utf-8") == rendered
"""Target administrative contract, NOT deployed and never connected to the runtime app.

No database, authorization, preview signing or business operations are implemented here.
"""

from __future__ import annotations

from datetime import datetime
from inspect import Parameter, Signature
from typing import Annotated, Any, Generic, Literal, NoReturn, TypeVar
from uuid import UUID

from fastapi import Body, FastAPI, HTTPException, Query
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator
from pydantic.json_schema import SkipJsonSchema


Text = Annotated[str, Field(min_length=1, pattern=r"\S")]
Code = Annotated[str, Field(min_length=1, pattern=r"^\S+$")]
AttributeCode = Annotated[str, Field(pattern=r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")]
Count = Annotated[int, Field(ge=0)]
DefaultValue = str | int | float | bool
DataType = Literal["string", "integer", "decimal", "boolean", "date", "select", "catalog"]


def parse_wire_uuid(value: object) -> object:
    return UUID(value) if isinstance(value, str) else value


UUIDWire = Annotated[UUID, BeforeValidator(parse_wire_uuid)]


def reject_explicit_null(value: object) -> object:
    if value is None:
        raise ValueError("Omit this field to preserve it; explicit null is invalid.")
    return value


def omit_patch_default(schema: dict[str, Any]) -> None:
    schema.pop("default", None)


PatchText = Annotated[
    Text | SkipJsonSchema[None], BeforeValidator(reject_explicit_null),
    Field(json_schema_extra=omit_patch_default),
]
PatchCode = Annotated[
    Code | SkipJsonSchema[None], BeforeValidator(reject_explicit_null),
    Field(json_schema_extra=omit_patch_default),
]
PatchDataType = Annotated[
    DataType | SkipJsonSchema[None], BeforeValidator(reject_explicit_null),
    Field(json_schema_extra=omit_patch_default),
]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class UnitInput(ContractModel):
    codigo: Code
    nombre: Text
    simbolo: Code = Field(description="Exact, case-sensitive symbol; MB and Mb differ.")
    magnitud_codigo: Code


class UnitUpdate(ContractModel):
    codigo: PatchCode = Field(default=None, description="Omitted preserves; null is invalid.")
    nombre: PatchText = None
    simbolo: PatchCode = None
    magnitud_codigo: PatchCode = None


class UnitSummary(UnitInput):
    id: UUIDWire


class UnitUsage(ContractModel):
    atributos_activos: Count = 0
    atributos_inactivos: Count = 0
    snapshots_historicos: Count = 0


class UnitRead(UnitSummary):
    es_sistema: bool
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    usuario_auditoria: str | None
    created_by: str | None = None
    updated_by: str | None = None
    uso: UnitUsage = Field(default_factory=UnitUsage)


class CategoryOrigin(ContractModel):
    id: UUIDWire
    nombre: Text


class CategoryRead(CategoryOrigin):
    parent_id: UUIDWire | None
    tiene_hijos: bool
    is_default: bool
    atributos_propios_count: Count
    atributos_efectivos_count: Count
    activo: bool


class CategoryTreeNode(ContractModel):
    id: UUIDWire
    nombre: Text
    parent_id: UUIDWire | None
    tiene_hijos: bool
    is_default: bool
    atributos_propios_count: Count
    atributos_efectivos_count: Count
    hijos: list[CategoryTreeNode]


class SelectableCategory(CategoryRead):
    tiene_hijos: Literal[False]
    is_default: Literal[False]
    activo: Literal[True]


class CategoryCreate(ContractModel):
    nombre: Text
    parent_id: UUIDWire | None = None


class CategoryUpdate(ContractModel):
    nombre: PatchText = None
    parent_id: UUIDWire | None = Field(
        default=None, description="Omitted preserves parent; explicit null moves to root."
    )


class ConfigurationInput(ContractModel):
    obligatorio: bool = Field(default=False, description="Omitted preserves on update.")
    valor_default: DefaultValue | None = Field(
        default=None,
        description="Omitted preserves; null clears; value is validated by future EAV service.",
    )
    orden: int | None = Field(default=None, description="Omitted preserves; null clears.")
    aplicar_default_a_existentes: bool = Field(
        default=False, description="Explicit opt-in, fill-only; never inferred from required."
    )


class AssignmentInput(ConfigurationInput):
    atributo_id: UUIDWire
    precondicion_preview: Text | None = None


class Restrictions(ContractModel):
    allow_negative: bool
    min_value: str | int | float | None
    max_value: str | int | float | None


class AttributeDefinition(ContractModel):
    nombre: Text
    tipo_dato: DataType
    unidad_id: UUIDWire | None = None
    select_options: list[Text] | None = None
    catalog_id: UUIDWire | None = None
    allow_negative: bool = False
    min_value: str | int | float | None = None
    max_value: str | int | float | None = None

    @model_validator(mode="after")
    def validate_unit_type(self) -> AttributeDefinition:
        if self.unidad_id is not None and self.tipo_dato not in ("integer", "decimal"):
            raise ValueError("ATTRIBUTE_UNIT_INVALID_TYPE")
        return self


class AttributeCreate(AttributeDefinition, ConfigurationInput):
    categoria_id: UUIDWire
    confirmar_anotacion_unidad: bool = False


class AttributeUpdate(ContractModel):
    nombre: PatchText = None
    tipo_dato: PatchDataType = None
    unidad_id: UUIDWire | None = None
    select_options: list[Text] | None = None
    catalog_id: UUIDWire | None = None
    allow_negative: bool = Field(default=False)
    min_value: str | int | float | None = None
    max_value: str | int | float | None = None
    confirmar_anotacion_unidad: bool = False

    @model_validator(mode="after")
    def validate_known_unit_type(self) -> AttributeUpdate:
        if (
            self.unidad_id is not None
            and "tipo_dato" in self.model_fields_set
            and self.tipo_dato not in ("integer", "decimal")
        ):
            raise ValueError("ATTRIBUTE_UNIT_INVALID_TYPE")
        return self


class AttributeRead(ContractModel):
    id: UUIDWire
    codigo: AttributeCode
    nombre: Text
    tipo_dato: DataType
    unidad: UnitSummary | None
    restricciones: Restrictions
    select_options: list[Text] | None
    catalog_id: UUIDWire | None
    activo: bool

    @model_validator(mode="after")
    def validate_unit_type(self) -> AttributeRead:
        if self.unidad is not None and self.tipo_dato not in ("integer", "decimal"):
            raise ValueError("ATTRIBUTE_UNIT_INVALID_TYPE")
        return self


class EffectiveAttribute(ContractModel):
    mapping_id: UUIDWire
    atributo_id: UUIDWire
    codigo: AttributeCode
    nombre: Text
    tipo_dato: DataType
    unidad: UnitSummary | None
    restricciones: Restrictions
    select_options: list[Text] | None
    catalog_id: UUIDWire | None
    obligatorio: bool
    valor_default: DefaultValue | None
    orden: int | None
    categoria_origen: CategoryOrigin
    profundidad: Count
    heredado: bool

    @model_validator(mode="after")
    def validate_unit_type(self) -> EffectiveAttribute:
        if self.unidad is not None and self.tipo_dato not in ("integer", "decimal"):
            raise ValueError("ATTRIBUTE_UNIT_INVALID_TYPE")
        return self


class LifecycleInput(ContractModel):
    confirmar: bool = False


Payload = TypeVar("Payload", bound=ContractModel)


class PreviewInput(ContractModel, Generic[Payload]):
    operacion: Text
    payload: Payload


class Confirmation(ContractModel, Generic[Payload]):
    precondicion_preview: Text = Field(
        description="Opaque authenticated token. Never parse claims/expiry in FE. "
        "Expired/changed token or state: 409 CATALOG_PREVIEW_STALE."
    )
    payload: Payload = Field(
        description="Exact previewed payload, including explicit consent flags. "
        "Preserve omission with model_dump(mode='json', exclude_unset=True)."
    )


class B3Confirmation(ContractModel, Generic[Payload]):
    confirmar_b3: Literal[True]
    precondicion_preview: Text
    payload: Payload


class ImpactItem(ContractModel):
    id: UUIDWire
    nombre: Text
    motivo: Text


class UnitChange(ContractModel):
    anterior: UnitSummary | None
    posterior: UnitSummary | None


class PreviewResponse(ContractModel):
    operacion: Text
    resumen: Text
    conteos: dict[str, Count]
    faltantes: list[ImpactItem]
    conversiones: list[ImpactItem]
    incompatibles: list[ImpactItem]
    remapeos: list[ImpactItem]
    cambio_unidad: UnitChange | None
    requiere_confirmacion: bool
    acciones_permitidas: list[Text]
    precondicion_preview: Text


ErrorCode = Literal[
    "CATEGORY_DUPLICATE_NAME", "CATEGORY_CYCLE", "CATEGORY_PARENT_INACTIVE",
    "CATEGORY_NOT_LEAF", "CATEGORY_DEFAULT_PROTECTED", "CATEGORY_HAS_ACTIVE_CHILDREN",
    "CATEGORY_PRODUCTS_HAVE_STOCK", "CATEGORY_CHANGE_REQUIRES_CONFIRMATION",
    "ATTRIBUTE_DUPLICATE_NAME", "ATTRIBUTE_DUPLICATE_CODE", "ATTRIBUTE_NOT_APPLICABLE",
    "ATTRIBUTE_ALREADY_ASSIGNED", "ATTRIBUTE_INVALID_TYPE", "ATTRIBUTE_HAS_PENDING_REMAPS",
    "ATTRIBUTE_STATE_CHANGED", "ATTRIBUTE_UNIT_INVALID_TYPE",
    "ATTRIBUTE_UNIT_ANNOTATION_REQUIRES_CONFIRMATION", "ATTRIBUTE_UNIT_CHANGE_REQUIRES_CONVERSION",
    "ATTRIBUTE_UNIT_REMOVAL_REQUIRES_MIGRATION", "CATEGORY_ATTRIBUTE_IN_USE",
    "CATEGORY_ATTRIBUTE_REMOVAL_REQUIRES_CONFIRMATION", "REQUIRED_ATTRIBUTE_MISSING",
    "DEFAULT_VALUE_INVALID", "PRODUCT_REQUIRED_ATTRIBUTES_MISSING", "UNIT_DUPLICATE_CODE",
    "UNIT_DUPLICATE_SYMBOL", "UNIT_IN_USE", "UNIT_PROTECTED", "UNIT_INACTIVE",
    "CATALOG_PREVIEW_STALE",
]


class ErrorDetail(ContractModel):
    code: ErrorCode
    message: Text
    conteos: dict[str, Count]
    affected_ids: list[UUIDWire] = Field(
        default_factory=list, description="Only when authorized; omit to avoid disclosure."
    )
    acciones_permitidas: list[Text]


class CatalogError(ContractModel):
    detail: ErrorDetail


class Pagination(ContractModel):
    total: Count
    limit: Annotated[int, Field(gt=0)]
    offset: Count
    next_offset: Count | None
    prev_offset: Count | None
    has_more: bool
    page: Annotated[int, Field(gt=0)]
    page_count: Count


class Page(ContractModel, Generic[Payload]):
    items: list[Payload]
    meta: Pagination


class ReversionRead(ContractModel):
    disponible: bool
    resumen: Text
    acciones_permitidas: list[Text]


class ContractUnavailable(ContractModel):
    detail: Literal["Contract only: endpoints are NOT deployed; handlers are not functional."]


EXAMPLE_ID = "11111111-1111-4111-8111-111111111111"
UNIT_EXAMPLE: dict[str, Any] = {
    "id": EXAMPLE_ID, "codigo": "GIGABYTE", "nombre": "Gigabyte", "simbolo": "GB",
    "magnitud_codigo": "DATA_STORAGE",
}
CATEGORY_EXAMPLE: dict[str, Any] = {
    "id": EXAMPLE_ID, "nombre": "Computadores", "parent_id": None,
    "tiene_hijos": False, "is_default": False,
    "atributos_propios_count": 1, "atributos_efectivos_count": 1,
}
EFFECTIVE_EXAMPLE: dict[str, Any] = {
    "mapping_id": EXAMPLE_ID, "atributo_id": EXAMPLE_ID, "codigo": "memoria_ram",
    "nombre": "Memoria RAM", "tipo_dato": "integer", "unidad": UNIT_EXAMPLE,
    "restricciones": {"allow_negative": False, "min_value": None, "max_value": None},
    "select_options": None, "catalog_id": None, "obligatorio": True,
    "valor_default": None, "orden": None,
    "categoria_origen": {"id": EXAMPLE_ID, "nombre": "Computadores"},
    "profundidad": 0, "heredado": False,
}
PREVIEW_EXAMPLE: dict[str, Any] = {
    "operacion": "actualizar", "resumen": "Anotar unidad sin modificar numeros.",
    "conteos": {"productos_activos": 2, "valores_actuales": 2, "valores_historicos": 1},
    "faltantes": [], "conversiones": [], "incompatibles": [], "remapeos": [],
    "cambio_unidad": {"anterior": None, "posterior": UNIT_EXAMPLE},
    "requiere_confirmacion": True, "acciones_permitidas": ["previsualizar"],
    "precondicion_preview": "EXAMPLE_ONLY_NOT_A_VALID_SIGNED_TOKEN",
}


def create_contract_app() -> FastAPI:
    """Build a schema fixture app only. Never mount this in osiris.main."""
    app = FastAPI(
        title="Catalog administration v1 - NOT DEPLOYED - CONTRACT ONLY",
        version="1.0.0",
        description=(
            "Target contract for deliveries 1-6, NOT the runtime API. "
            "Every handler is non-functional and returns 501. No DB/auth/signing. "
            "Nullable read fields are required; omitted update fields preserve state. "
            "Send the exact previewed payload, preserving omitted fields, inside "
            "{payload, precondicion_preview} when confirming. Consent flags belong "
            "inside payload and are bound by preview; this app does not verify tokens. "
            "Type/default/catalog validation requiring existing state belongs to future services."
        ),
        openapi_tags=[{"name": "contract-only", "description": "NOT deployed; stubs return 501."}],
    )
    examples: dict[tuple[str, str], Any] = {}

    def register(
        method: str,
        path: str,
        response: Any,
        body: Any = None,
        *,
        paginated: bool = False,
        unit_filters: bool = False,
        example: Any = None,
    ) -> None:
        async def unavailable(**kwargs: object) -> NoReturn:
            raise HTTPException(
                status_code=501,
                detail="Contract only: endpoints are NOT deployed; handlers are not functional.",
            )

        parameters = [
            Parameter(segment[1:-1], Parameter.KEYWORD_ONLY, annotation=UUID)
            for segment in path.split("/") if segment.startswith("{")
        ]
        if body is not None:
            parameters.append(Parameter(
                "body", Parameter.KEYWORD_ONLY, annotation=body, default=Body(...)
            ))
        if paginated:
            parameters.extend([
                Parameter("q", Parameter.KEYWORD_ONLY, annotation=str | None,
                          default=Query(None)),
                Parameter("only_active", Parameter.KEYWORD_ONLY, annotation=bool,
                          default=Query(True)),
                Parameter("limit", Parameter.KEYWORD_ONLY, annotation=int,
                          default=Query(100, ge=1)),
                Parameter("offset", Parameter.KEYWORD_ONLY, annotation=int,
                          default=Query(0, ge=0)),
            ])
        if unit_filters:
            parameters.append(Parameter(
                "magnitud_codigo", Parameter.KEYWORD_ONLY, annotation=str | None,
                default=Query(None),
            ))
        setattr(unavailable, "__signature__", Signature(parameters))
        responses: dict[int | str, dict[str, Any]] = {
            409: {"model": CatalogError, "description": "Canonical catalog conflict.",
                  "content": {"application/json": {"examples": {
                      code: {"value": {"detail": {
                          "code": code, "message": "Conflicto de catalogo.", "conteos": {},
                          "acciones_permitidas": ["previsualizar"],
                      }}} for code in (
                          "UNIT_DUPLICATE_CODE", "UNIT_DUPLICATE_SYMBOL", "CATALOG_PREVIEW_STALE"
                      )
                  }}}},
            501: {"model": ContractUnavailable, "description": "Non-functional contract stub."},
            403: {"description": "Effective permissions required by future runtime API."},
            404: {"description": "Target not found by future runtime API."},
        }
        if example is not None:
            responses[200] = {"content": {"application/json": {"example": example}}}
            examples[("/api/v1" + path, method.lower())] = example
        app.add_api_route(
            "/api/v1" + path, unavailable, methods=[method], response_model=response,
            responses=responses, tags=["contract-only"],
            operation_id=method.lower() + "_" + path.strip("/").replace(
                "/", "_"
            ).replace("{", "").replace("}", "").replace("-", "_"),
            description="NOT DEPLOYED. Contract fixture only; handler always returns 501.",
            openapi_extra={"x-contract-only": True, "x-deployed": False},
        )

    register("GET", "/categorias", Page[CategoryRead], paginated=True)
    register("GET", "/categorias/arbol", list[CategoryTreeNode],
             example=[{**CATEGORY_EXAMPLE, "hijos": []}])
    register("GET", "/categorias/seleccionables", list[SelectableCategory],
             example=[{**CATEGORY_EXAMPLE, "activo": True}])
    register("POST", "/categorias/previsualizar", PreviewResponse,
             PreviewInput[CategoryCreate], example=PREVIEW_EXAMPLE)
    register("POST", "/categorias", CategoryRead,
             CategoryCreate | B3Confirmation[CategoryCreate])
    register("GET", "/categorias/{id}", CategoryRead)
    register("PUT", "/categorias/{id}", CategoryRead,
             CategoryUpdate | Confirmation[CategoryUpdate] |
             B3Confirmation[CategoryUpdate])
    register("DELETE", "/categorias/{id}", CategoryRead,
             LifecycleInput | Confirmation[LifecycleInput])
    register("POST", "/categorias/{id}/previsualizar", PreviewResponse,
             PreviewInput[CategoryUpdate] | PreviewInput[LifecycleInput], example=PREVIEW_EXAMPLE)
    register("POST", "/categorias/{id}/reactivar", CategoryRead, LifecycleInput)
    for suffix in ("atributos-efectivos", "atributos-propios"):
        register("GET", "/categorias/{id}/" + suffix, list[EffectiveAttribute],
                 example=[EFFECTIVE_EXAMPLE])
    register("POST", "/categorias/{id}/atributos", EffectiveAttribute,
             AssignmentInput | Confirmation[AssignmentInput])
    register("POST", "/categorias/{id}/atributos/previsualizar", PreviewResponse,
             PreviewInput[AssignmentInput], example=PREVIEW_EXAMPLE)
    mapping_path = "/categorias/{id}/atributos/{mapping_id}"
    register("PUT", mapping_path, EffectiveAttribute,
             ConfigurationInput | Confirmation[ConfigurationInput])
    register("DELETE", mapping_path, EffectiveAttribute,
             LifecycleInput | Confirmation[LifecycleInput])
    register("POST", mapping_path + "/previsualizar", PreviewResponse,
             PreviewInput[ConfigurationInput] | PreviewInput[LifecycleInput],
             example=PREVIEW_EXAMPLE)
    register("POST", mapping_path + "/reactivar", EffectiveAttribute,
             ConfigurationInput | Confirmation[ConfigurationInput])
    register("GET", "/atributos", Page[AttributeRead], paginated=True)
    register("POST", "/atributos", AttributeRead,
             AttributeCreate | Confirmation[AttributeCreate])
    register("POST", "/atributos/previsualizar", PreviewResponse,
             PreviewInput[AttributeCreate], example=PREVIEW_EXAMPLE)
    register("GET", "/atributos/{id}", AttributeRead)
    register("PUT", "/atributos/{id}", AttributeRead,
             AttributeUpdate | Confirmation[AttributeUpdate])
    register("DELETE", "/atributos/{id}", AttributeRead,
             LifecycleInput | Confirmation[LifecycleInput])
    register("POST", "/atributos/{id}/previsualizar", PreviewResponse,
             PreviewInput[AttributeUpdate] | PreviewInput[LifecycleInput], example=PREVIEW_EXAMPLE)
    for suffix in ("revertir", "reactivar"):
        register("POST", "/atributos/{id}/" + suffix, AttributeRead,
                 LifecycleInput | Confirmation[LifecycleInput])
    register("GET", "/atributos/{id}/reversion", ReversionRead)
    register("GET", "/unidades", Page[UnitRead], paginated=True, unit_filters=True)
    register("POST", "/unidades", UnitRead, UnitInput)
    register("GET", "/unidades/{id}", UnitRead, example={
        **UNIT_EXAMPLE, "activo": True, "es_sistema": True,
        "creado_en": "2026-10-25T00:00:00Z", "actualizado_en": "2026-10-25T00:00:00Z",
        "usuario_auditoria": None,
    })
    register("PUT", "/unidades/{id}", UnitRead, UnitUpdate)
    register("DELETE", "/unidades/{id}", UnitRead, LifecycleInput)
    register("POST", "/unidades/{id}/reactivar", UnitRead, LifecycleInput)
    original_openapi = app.openapi

    def export_schema() -> dict[str, Any]:
        schema = original_openapi()
        for (path, method), example in examples.items():
            schema["paths"][path][method]["responses"]["200"]["content"][
                "application/json"
            ]["example"] = example
        schema["x-contract-only"] = True
        schema["x-deployed"] = False
        return schema

    setattr(app, "openapi", export_schema)
    return app
from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


SUCCESS_STATUS_BY_METHOD: dict[str, str] = {
    "get": "200",
    "post": "201",
    "put": "200",
    "patch": "200",
    "delete": "204",
}

RESOURCE_LABELS: dict[str, tuple[str, str]] = {
    "empresas": ("empresa", "empresas"),
    "sucursales": ("sucursal", "sucursales"),
    "puntos-emision": ("punto de emision", "puntos de emision"),
    "roles": ("rol", "roles"),
    "usuarios": ("usuario", "usuarios"),
    "personas": ("persona", "personas"),
    "clientes": ("cliente", "clientes"),
    "empleados": ("empleado", "empleados"),
    "tipos-cliente": ("tipo de cliente", "tipos de cliente"),
    "modulos": ("modulo", "modulos"),
    "roles-modulos-permisos": ("permiso de modulo", "permisos de modulo"),
    "proveedores-persona": ("proveedor persona", "proveedores persona"),
    "proveedores-sociedad": ("proveedor sociedad", "proveedores sociedad"),
    "audit-logs": ("registro de auditoria", "registros de auditoria"),
    "atributos": ("atributo", "atributos"),
    "categorias": ("categoria", "categorias"),
    "categorias-atributos": ("categoria atributo", "categorias atributos"),
    "casas-comerciales": ("casa comercial", "casas comerciales"),
    "bodegas": ("bodega", "bodegas"),
    "productos": ("producto", "productos"),
    "inventarios": ("movimiento de inventario", "movimientos de inventario"),
    "impuestos": ("impuesto", "impuestos"),
    "ventas": ("venta", "ventas"),
    "compras": ("compra", "compras"),
    "retenciones": ("retencion emitida", "retenciones emitidas"),
    "retenciones-recibidas": ("retencion recibida", "retenciones recibidas"),
    "cxc": ("cuenta por cobrar", "cuentas por cobrar"),
    "fe": ("proceso de facturacion electronica", "procesos de facturacion electronica"),
    "documentos": ("documento electronico", "documentos electronicos"),
    "impresion": ("documento impreso", "documentos impresos"),
    "reportes": ("reporte", "reportes"),
    "sri": ("recurso SRI", "recursos SRI"),
}

SPECIAL_SUMMARY_BY_SUFFIX: dict[str, str] = {
    "emitir": "Emitir {singular}",
    "anular": "Anular {singular}",
    "confirmar": "Confirmar {singular}",
    "aplicar": "Aplicar {singular}",
    "siguiente": "Obtener siguiente secuencial",
    "ajuste-manual": "Registrar ajuste manual de secuencial",
    "reimprimir": "Solicitar reimpresion del documento",
    "procesar-cola": "Procesar cola de documentos del SRI",
    "reset-password": "Resetear clave temporal de usuario",
    "verify-password": "Verificar credenciales de usuario",
    "fe-payload": "Generar payload para FE-EC",
    "kardex": "Consultar kardex operativo",
    "valoracion": "Consultar valoracion de inventario",
    "ride": "Descargar representacion impresa del documento",
    "xml": "Descargar XML autorizado",
    "ticket": "Generar ticket termico",
    "preimpresa": "Generar plantilla preimpresa",
    "menu": "Consultar menu habilitado para usuario",
    "permisos": "Consultar permisos del usuario",
}


def _path_parts(path: str) -> list[str]:
    parts = [part for part in path.strip("/").split("/") if part]
    if len(parts) >= 2 and parts[0] == "api" and parts[1] == "v1":
        return parts[2:]
    if parts and parts[0] == "api":
        return parts[1:]
    return parts


def _resource_labels(path: str) -> tuple[str, str, list[str]]:
    parts = _path_parts(path)
    first_resource = "recurso"
    for part in parts:
        if not part.startswith("{"):
            first_resource = part
            break
    singular, plural = RESOURCE_LABELS.get(first_resource, (first_resource.rstrip("s"), first_resource))
    return singular, plural, parts


def _contains_path_id(parts: list[str]) -> bool:
    return any(part.startswith("{") and part.endswith("}") for part in parts)


def _operation_suffix(parts: list[str]) -> str | None:
    if not parts:
        return None
    candidate = parts[-1]
    if candidate.startswith("{"):
        return None
    return candidate


def _build_summary(method_lc: str, singular: str, plural: str, parts: list[str]) -> str:
    suffix = _operation_suffix(parts)
    if suffix and suffix in SPECIAL_SUMMARY_BY_SUFFIX:
        return SPECIAL_SUMMARY_BY_SUFFIX[suffix].format(singular=singular, plural=plural)

    if method_lc == "get":
        if parts[:1] == ["reportes"]:
            reporte_nombre = " ".join([p for p in parts[1:] if not p.startswith("{")]) or "general"
            return f"Consultar reporte de {reporte_nombre}"
        if _contains_path_id(parts):
            return f"Obtener {singular} por identificador"
        return f"Listar {plural}"
    if method_lc == "post":
        if suffix == "pagos":
            return "Registrar pago asociado"
        return f"Crear {singular}"
    if method_lc == "put":
        return f"Actualizar {singular}"
    if method_lc == "patch":
        return f"Actualizar parcialmente {singular}"
    if method_lc == "delete":
        return f"Eliminar {singular}"
    return f"Operacion {method_lc.upper()} sobre {singular}"


def _build_description(method_lc: str, path: str, singular: str, plural: str, parts: list[str]) -> str:
    suffix = _operation_suffix(parts)
    if parts[:1] == ["reportes"]:
        detalle = " ".join([p for p in parts[1:] if not p.startswith("{")])
        return (
            f"Genera el reporte '{detalle}' aplicando filtros de fecha y criterios tributarios/operativos "
            "definidos para el dominio de reporteria."
        )

    if suffix == "emitir":
        return (
            f"Ejecuta la emision de la {singular} y desencadena sus efectos transaccionales "
            "(inventario, cartera y orquestacion FE-EC cuando corresponde)."
        )
    if suffix == "anular":
        return (
            f"Anula la {singular} aplicando reglas de negocio del SRI y registrando la trazabilidad "
            "en auditoria/historial de estados."
        )
    if suffix == "confirmar":
        return (
            f"Confirma el {singular} y aplica los cambios definitivos de stock/costos "
            "con control de concurrencia."
        )
    if suffix == "procesar-cola":
        return (
            "Procesa los documentos pendientes en cola de contingencia SRI, aplicando reintentos "
            "con backoff y actualizacion de estado."
        )
    if suffix == "reimprimir":
        return (
            "Genera una reimpresion controlada del documento solicitado, incrementa el contador "
            "de impresiones y registra un evento de auditoria."
        )
    if suffix == "siguiente":
        return (
            "Obtiene el siguiente secuencial del punto de emision con bloqueo pesimista para evitar "
            "duplicidad en concurrencia."
        )
    if suffix == "ajuste-manual":
        return (
            "Ajusta manualmente un secuencial del punto de emision. Requiere justificacion "
            "y registra evidencia de auditoria."
        )
    if suffix == "xml":
        return "Descarga el XML autorizado del documento electronico cuando su estado SRI es AUTORIZADO."
    if suffix == "ride":
        return "Genera y devuelve la representacion impresa (RIDE) del documento electronico."
    if suffix == "ticket":
        return "Genera un ticket termico en formato optimizado para impresion POS."
    if suffix == "preimpresa":
        return "Renderiza la plantilla para nota fisica preimpresa con margenes configurables por punto de emision."
    if suffix == "pagos":
        return (
            f"Registra un pago sobre la {singular} aplicando validaciones de sobrepago "
            "y recalculo de saldos."
        )
    if suffix == "fe-payload":
        return "Construye el payload estructurado para firma y transmision con la libreria FE-EC."

    if method_lc == "get":
        if _contains_path_id(parts):
            return f"Recupera la informacion detallada de la {singular} identificada en la ruta."
        return f"Consulta la coleccion de {plural} con filtros/paginacion segun parametros enviados."
    if method_lc == "post":
        return f"Registra una nueva {singular} aplicando validaciones de integridad y reglas del dominio."
    if method_lc == "put":
        return f"Actualiza completamente la {singular} indicada, respetando restricciones de negocio."
    if method_lc == "patch":
        return f"Actualiza parcialmente la {singular} indicada, modificando solo los campos enviados."
    if method_lc == "delete":
        return f"Realiza la baja logica de la {singular} para conservar trazabilidad historica."
    return f"Operacion {method_lc.upper()} sobre {path}."


def _build_400_description(method_lc: str, singular: str, parts: list[str], suffix: str | None) -> str:
    resource = parts[0] if parts else singular
    if resource == "empresas":
        return "Bad Request. El RUC o la configuracion tributaria de la empresa no cumple validaciones."
    if resource == "sucursales":
        return "Bad Request. El codigo de sucursal ya existe o la regla matriz/codigo es invalida."
    if resource == "puntos-emision":
        return "Bad Request. El codigo del punto de emision esta duplicado o el secuencial no es valido."
    if resource in {"ventas", "compras"}:
        return "Bad Request. La transaccion no cumple reglas tributarias, de stock o de estado."
    if resource in {"inventarios", "bodegas", "productos"}:
        return "Bad Request. Datos de inventario invalidos (cantidades, costos o relaciones)."
    if resource in {"retenciones", "retenciones-recibidas", "cxc"}:
        return "Bad Request. El movimiento financiero excede saldos o incumple validaciones de retencion/pago."
    if resource == "reportes":
        return "Bad Request. Parametros de consulta invalidos para el reporte solicitado."
    if resource == "impresion":
        return "Bad Request. Formato de impresion invalido o documento no apto para el formato solicitado."
    if resource == "impuestos":
        return "Bad Request. Codigos o vigencias del impuesto no son consistentes."
    if resource in {"fe", "documentos", "sri"}:
        return "Bad Request. El documento electronico no se encuentra en un estado apto para la operacion."
    if method_lc == "post" and suffix == "verify-password":
        return "Bad Request. La credencial enviada no cumple el formato esperado."
    return f"Bad Request. La solicitud para {singular} contiene datos invalidos."


def _build_404_description(singular: str) -> str:
    return f"Not Found. No existe una {singular} con el identificador proporcionado."


def _build_success_description(method_lc: str, singular: str, plural: str, parts: list[str]) -> tuple[str, str]:
    suffix = _operation_suffix(parts)
    status_code = SUCCESS_STATUS_BY_METHOD.get(method_lc, "200")

    if method_lc == "get":
        if parts[:1] == ["reportes"]:
            return "200", "OK. Devuelve el resultado agregado del reporte solicitado."
        if _contains_path_id(parts):
            return "200", f"OK. Devuelve la informacion detallada de la {singular}."
        return "200", f"OK. Devuelve la lista de {plural}."

    if method_lc == "post":
        if suffix in {"emitir", "confirmar", "anular", "aplicar", "siguiente", "ajuste-manual", "procesar-cola", "reimprimir"}:
            return "200", "OK. La operacion solicitada se ejecuto correctamente."
        return "201", f"Created. La {singular} fue registrada correctamente."

    if method_lc in {"put", "patch"}:
        return "200", f"OK. La {singular} fue actualizada correctamente."

    if method_lc == "delete":
        return "204", f"No Content. La {singular} fue dada de baja logicamente."

    return status_code, "Operacion completada correctamente."


def _infer_example(field_schema: dict[str, Any]) -> Any:
    schema_type = field_schema.get("type")
    if schema_type == "string":
        fmt = field_schema.get("format")
        if fmt == "uuid":
            return "550e8400-e29b-41d4-a716-446655440000"
        if fmt == "date":
            return "2026-02-22"
        if fmt == "date-time":
            return "2026-02-22T10:00:00Z"
        return "texto"
    if schema_type == "integer":
        return 1
    if schema_type == "number":
        return 1.0
    if schema_type == "boolean":
        return True
    if schema_type == "array":
        return []
    if schema_type == "object":
        return {}
    return None


def _ensure_schema_docs(openapi_schema: dict[str, Any]) -> None:
    components = openapi_schema.get("components", {})
    schemas = components.get("schemas", {})
    for schema_name, schema_data in schemas.items():
        if not schema_data.get("description"):
            schema_data["description"] = f"Esquema de datos para {schema_name}."

        properties = schema_data.get("properties")
        if not isinstance(properties, dict):
            continue

        for field_name, field_schema in properties.items():
            if not isinstance(field_schema, dict):
                continue
            if not field_schema.get("description"):
                field_schema["description"] = f"Campo `{field_name}` de `{schema_name}`."
            if "example" not in field_schema:
                example = _infer_example(field_schema)
                if example is not None:
                    field_schema["example"] = example


def _ensure_operation_docs(path: str, method: str, operation: dict[str, Any]) -> None:
    method_lc = method.lower()
    singular, plural, parts = _resource_labels(path)
    suffix = _operation_suffix(parts)

    operation["summary"] = _build_summary(method_lc, singular, plural, parts)
    operation["description"] = _build_description(method_lc, path, singular, plural, parts)

    responses = operation.setdefault("responses", {})
    if not isinstance(responses, dict):
        responses = {}
        operation["responses"] = responses

    success_code, success_description = _build_success_description(method_lc, singular, plural, parts)
    responses.setdefault(success_code, {})
    if isinstance(responses[success_code], dict):
        responses[success_code]["description"] = success_description
    else:
        responses[success_code] = {"description": success_description}

    responses.setdefault("400", {})
    responses.setdefault("401", {})
    responses.setdefault("404", {})
    if isinstance(responses["400"], dict):
        responses["400"]["description"] = _build_400_description(method_lc, singular, parts, suffix)
    if isinstance(responses["401"], dict):
        responses["401"]["description"] = "Unauthorized. No se ha indicado o es incorrecto el Token JWT."
    if isinstance(responses["404"], dict):
        responses["404"]["description"] = _build_404_description(singular)

    parameters = operation.get("parameters", [])
    if isinstance(parameters, list):
        for param in parameters:
            if not isinstance(param, dict):
                continue
            location = str(param.get("in", "query")).lower()
            name = str(param.get("name", "parametro"))
            required = bool(param.get("required", False))
            requirement = "Obligatorio." if required else "Opcional."

            if location == "path":
                if name.endswith("_id"):
                    entity_name = name[:-3].replace("_", " ")
                elif name == "id":
                    entity_name = singular
                else:
                    entity_name = name.replace("_", " ")
                param["description"] = f"Identificador unico (UUID) de {entity_name}. {requirement}"
                continue

            if location == "query":
                if name == "limit":
                    param["description"] = "Numero maximo de registros a retornar por pagina. Opcional."
                elif name in {"offset", "skip"}:
                    param["description"] = "Desplazamiento inicial para paginacion de resultados. Opcional."
                elif name == "only_active":
                    param["description"] = "Filtra solo registros activos cuando es true. Opcional."
                elif name in {"fecha_inicio", "fecha_fin", "fecha", "fecha_desde", "fecha_hasta"}:
                    param["description"] = f"Fecha de referencia para filtrar {plural}. {requirement}"
                elif name in {"mes", "anio"}:
                    param["description"] = f"Periodo fiscal utilizado en la consulta del reporte. {requirement}"
                elif name == "agrupacion":
                    param["description"] = "Nivel de agregacion temporal para series de ventas (diaria/mensual/anual). Opcional."
                elif name in {"sucursal_id", "bodega_id", "punto_emision_id", "usuario_id", "producto_id"}:
                    param["description"] = f"Filtro por identificador de {name[:-3].replace('_', ' ')}. {requirement}"
                elif name in {"tipo_impuesto", "solo_vigentes"}:
                    param["description"] = "Filtro del catalogo tributario SRI segun tipo o vigencia. Opcional."
                else:
                    param["description"] = f"Parametro de consulta `{name}` para filtrar {plural}. {requirement}"
                continue

            if location == "header":
                param["description"] = f"Cabecera HTTP `{name}` utilizada por control de acceso o trazabilidad. {requirement}"
                continue

            param["description"] = f"Parametro `{name}` asociado a la operacion sobre {plural}. {requirement}"


def build_gold_standard_openapi(app: FastAPI) -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    paths = openapi_schema.get("paths", {})
    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for method, operation in methods.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            if not isinstance(operation, dict):
                continue
            _ensure_operation_docs(path, method, operation)

    _ensure_schema_docs(openapi_schema)
    app.openapi_schema = openapi_schema
    return openapi_schema

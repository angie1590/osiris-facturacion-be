# Precondicion de preview y protocolo de integracion

Estado: firma, guard de lock y contrato OpenAPI objetivo implementados y probados de forma aislada. La conexion a endpoints runtime y a todos los writers sigue reservada a entregas funcionales posteriores. Este documento no declara protegidos los endpoints actuales.

## Firma

CatalogPreviewSigner recibe una clave de servidor de al menos 32 bytes y duracion entre 1 y 3600 segundos (por defecto 300). No introduce una variable obligatoria de settings ni expone claves mediante API/CLI; la seleccion de clave de despliegue y rotacion pertenece a la integracion posterior.

Formato opaco al cliente: base64url(claims) + firma HMAC-SHA256 con dominio `osiris.catalog.preview.v1`. Claims: version, issued-at, expiry, hash de binding y hash de estado. No incluyen nombres, valores ni identidad sin hash. JSON canonico: claves ordenadas, sin NaN, arrays preservan orden y los campos omitidos son distintos de null.

Los callers deben entregar payload/estado ya normalizados por DTO de servidor, con Decimal/date/UUID serializados segun el contrato. No admitir un actor ni una huella de estado enviados por cliente como autoridad. Clave y contenido no se escriben en DB; no hay registro persistente de preview.

Binding incluye operacion, target, actor autenticado y payload completo. Estado incluye definicion, unidad, ancestros, mappings efectivos/conjuntos de IDs, productos y valores/remapeos relevantes, incluidos historicos cuando proceda. Insertar un mapping o valor debe modificar la huella, no basta updated_at de Atributo.

Resultado de verify: exito sin retorno de datos o HTTP 409 CATALOG_PREVIEW_STALE con accion previsualizar. Se rechazan expiracion, emision futura, firma alterada, otra clave, operacion/destino/actor/payload/estado distintos y formatos invalidos. Campos de consentimiento deben vincularse mediante un payload normalizado estable definido en OpenAPI antes de integrar, nunca excluidos arbitrariamente del hash.

## Integracion transaccional requerida

1. Autorizar operacion y obtener actor del JWT.
2. Leer/calcular preview sin mutar datos ni realizar commit; emitir token con estado consistente.
3. Al confirmar, autorizar de nuevo. Servicio exterior abre la unica transaccion de escritura.
4. Adquirir acquire_catalog_mutation_lock ANTES de cualquier lock de fila. La primitiva usa pg_advisory_xact_lock global con clave estable derivada de los bytes OSIRISC1, no un hash de proceso. Exige transaccion exterior PostgreSQL, rechaza AUTOCOMMIT por execution options y por estado efectivo del driver, no hace flush/commit/rollback. Esto serializa mutaciones que participen en el protocolo; no protege a writers legacy que aun no lo invocan.
5. Bajo ese guard, bloquear filas afectadas en orden determinista de tabla/ID, releer estado/payload normalizado, verificar token, validar invariantes y escribir business/snapshot/audit antes del commit exterior. Cualquier fallo hace rollback integral.
6. Todos los caminos que mutan jerarquia/mappings/atributos/unidades/EAV o el puente legacy deben usar el mismo guard, incluidos backfills, B3 y escritores concurrentes existentes. No habilitar garantias nuevas si queda un writer sin integrar; no modificar el formulario Producto ni activar su FK para resolver esto.
7. Mantener constraints DB para identidades; el guard no sustituye integridad ante SQL directo. Probar carreras con dos sesiones PostgreSQL y rollback. SQLite es solo test de logica, no evidencia de locks distribuidos.

El guard fue probado contra PostgreSQL local con dos sesiones, commit, rollback y engine AUTOCOMMIT (7 tests). No registra rutas ni cambia writers existentes. La entrega 1 acredita contratos y primitivas; cada entrega funcional debe integrar guard/permisos y verificar todos sus caminos antes de activar nuevas invariantes. La serializacion global podra afinarse despues con evidencia de rendimiento sin rebajar el compare-and-set.

## Contratos y consumo frontend

El contrato objetivo se exporta con scripts/export_catalog_contract.py a contracts/catalog-administration-v1.openapi.json y tiene copia identica en frontend. x-contract-only=true y x-deployed=false distinguen el contrato de una API disponible; handlers aislados devuelven 501 para requests validos y 422 para payloads invalidos. La app principal no se modifica.

Cada Confirmation tiene una ruta preview compatible con el mismo payload. AttributeUpdate global rechaza obligatoriedad/default/orden/backfill; esos campos pertenecen a configuracion local o al create-and-assign atomico. UUID de JSON se validan sin rechazar el wire valido ni relajar booleanos/numeros estrictos. El error real del signer se valida contra CatalogError y conserva conteos:{}.

Frontend valida schemas Zod contra el snapshot, conserva payload omitido/null y mantiene draft clonado/congelado. Actor/target/operation/payload distintos invalidan preview; respuestas tardias se descartan y no hay doble confirmacion ni retry automatico de stale. Ninguno de estos helpers esta conectado a pantallas o Producto en este gate.
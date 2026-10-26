## Context

Fuente funcional: documento adjunto, decisiones D-001..D-009, reglas RN-GEN/RN-CTX/RN-PER/RN-TC/RN-CLI/RN-PP/RN-PS/RN-EMP/RN-USR/RN-LIFE/RN-TENANT y criterios de aceptacion 55..71. Esta propuesta cubre backend; el cambio homonimo frontend consume el contrato, sin editar este repositorio.

Evidencia local revisada durante planificacion:

| Superficie | Observacion | Consecuencia |
| --- | --- | --- |
| `domain/service.py` | Create/update/delete soportan `commit=False`, FKs activas y rollback | Reutilizar este limite de transaccion; no crear otro CRUD framework |
| `empleado/service.py` | Crea Usuario por estrategia con `commit=False`, luego Empleado y commit final; no define baja especifica | Extender alta a Persona, cubrir todos los fallos y agregar baja atomica |
| Cliente/Proveedor Persona/Empleado | Updates eliminan `persona_id` del payload | Validacion explicita de inmutabilidad en DTO y servicio |
| Proveedor Sociedad | Update elimina `persona_contacto_id` | Habilitar contacto mutable y validar Persona activa |
| Usuario | Update filtra campos; create admite `commit=False`; DTO minimo seis | Rechazar identidad/username y unificar politica de password |
| `core/auth.py` | Login compara `lower(username)` y existe control de invalidacion de sesion | Reutilizarlo y probar access/refresh; alinear unicidad persistente |
| Frontend | Persona y asociaciones ya existen | Conservar contratos base y evolucionar, no reemplazar modulos |

Los hallazgos del documento sobre restricciones SQL, auditoria y RBAC son objetivos de verificacion, no resultados certificados de una inspeccion de PostgreSQL. Reutilizar pruebas existentes `test_persona.py`, `test_cliente.py`, `test_tipo_cliente.py`, `test_proveedor_persona.py`, `test_proveedor_sociedad.py`, `test_empleado.py`, `test_usuario.py`, `test_auth_session_invalidation.py`, `test_audit_context.py` y `test_security_access_audit.py`.

## Goals / Non-Goals

**Goals:** fuente unica de identidad, roles simultaneos y unicos, altas atomicas, ciclo de vida explicito, seguridad, contratos compatibles, busquedas eficientes y documentacion verificable.

**Non-Goals:** Cliente Sociedad, nuevos tipos fiscales, consulta SRI externa sin fuente/contrato aprobados, cambios de inventario/cartera/emision, multiempleo, habilitacion comercial por empresa y portal. No crear tablas con `metadata.create_all`, ni borrar/fusionar datos historicos automaticamente.

## Decisions

### 1. Composicion y datos globales

Persona solo representa persona natural. Mantener FKs 1:1 unicas para los cuatro roles y contacto 1:N para sociedades. Identidad/contacto se consulta mediante joins/proyecciones, sin duplicar campos almacenados. Persona y maestros comerciales siguen globales; Empleado valida Empresa y acceso a esa Empresa. Alternativa descartada: herencia ORM o agregar `empresa_id` a todos los maestros en este refactor, porque cambia el dominio y rompe reutilizacion global.

### 2. Contratos compuestos sobre endpoints existentes

Ampliar POST de Cliente, Proveedor Persona, Empleado y Usuario con exactamente uno de `persona_id` o `persona_nueva` (DTO PersonaCreate sin actor autoritativo ni campos internos). Proveedor Sociedad acepta exactamente uno de `persona_contacto_id` o `persona_contacto_nueva`. Conservar la rama por ID y las respuestas Read existentes; documentar extensiones en OpenAPI. Ambas alternativas, ninguna o null sin alternativa valida producen 422.

Actualizar PUT de Proveedor Sociedad para aceptar como maximo una alternativa de contacto; ninguna conserva el contacto. Un contacto nuevo y la actualizacion son atomicos. No exigir que UI edite Persona encontrada: editarla es una accion explicita con permisos propios. Rechazar cambios efectivos de `persona_id` y de username de Usuario con 409; el mismo valor puede ser idempotente, nunca ignorar un valor distinto. DTO deben impedir que `extra=ignore` o filtrados oculten el intento. No admitir `activo` como bypass del ciclo de vida.

Alternativa descartada: dos requests Persona+rol desde frontend, porque no ofrecen rollback fiable ni proteccion de carrera.

### 3. Resolver Persona y controlar la transaccion

Un servicio/orquestador compartido de aplicacion resuelve Persona, invoca los servicios existentes con `commit=False` y realiza un solo commit exterior. Mantener reglas especificas en cada servicio. Nunca usar un commit anidado ni asumir que `session.begin()` es valido tras autobegin sin revisar el ciclo actual de Session.

Secuencia: validar payload y permisos; normalizar identidad; buscar incluyendo inactivos; reutilizar activa sin sobrescribir datos; para inactiva devolver 409 con ID/accion de reactivacion; si no existe, insertar y flush; validar rol/FKs/credenciales; persistir rol (y Usuario para Empleado); auditar; commit. Cualquier excepcion de validacion, flush o commit revierte toda la operacion.

La restriccion unica de identificacion protege carreras. Encapsular el intento de insercion de Persona en savepoint sin dejar que un rollback del repositorio aborte inadvertidamente la transaccion exterior. Ante violacion de esa restriccion, resolver de nuevo la Persona ganadora y continuar si activa y compatible. Si el repositorio actual no permite esa recuperacion, implementar reintento acotado de la transaccion completa con consulta fresca, no un bucle ilimitado. Distinguir la restriccion exacta de otros IntegrityError, no reusar ante cualquier fallo. Las carreras del mismo rol terminan en un solo rol y 409 para el perdedor. Pruebas PostgreSQL con dos sesiones son el criterio, no mocks ni SQLite.

### 4. Normalizacion y politica tributaria aisladas

Centralizar trim y canonicalizacion: cedula/RUC numericos, pasaporte trim y mayusculas; separadores de presentacion solo se eliminan si la politica los admite, no convertir letras invalidas silenciosamente en un numero valido. Revisar colisiones antes de migrar valores existentes. Cedula exige diez digitos y validador vigente; Persona RUC solo natural; sociedad no se registra como Persona. Cambio de identificacion exige tambien tipo y revalidacion completa. Nombres/apellidos trim no vacios, email valido y longitudes del documento.

Separar formato local, estado/existencia tributaria y reglas del comprobante. No afirmar existencia/actividad SRI por pasar un algoritmo ni consultar una fuente inexistente. Parametrizar/aislar reglas actualizables y documentar la politica vigente, incluidos casos sin algoritmo exigible. La longitud minima de pasaporte debe quedar fijada al caracterizar el contrato actual.

Agregar metadatos explicitos a TipoContribuyente (por ejemplo `aplica_persona_natural` y `aplica_sociedad`) con migracion/backfill y exposicion Read. Los servicios consultan esos datos y `activo`, no nombre libre ni listas de codigos dispersas. Revisar cada codigo actual con negocio; no traducir automaticamente texto a semantica. Preservar la exclusion actual de Gran Contribuyente para proveedor natural hasta configuracion aprobada.

### 5. Integridad SQL y preflight

Verificar/reconciliar entidades y Alembic: unique identificacion, Cliente/ProveedorPersona/Empleado/Usuario.persona_id, RUC sociedad y FKs. Agregar la restriccion ausente de Proveedor Persona y unicidad username mediante indice unico funcional `lower(trim(username))` en PostgreSQL, junto con almacenamiento normalizado y validacion de servicio. Preferir indice funcional a CITEXT para evitar una extension adicional; contemplar pruebas SQLite sin confundirlas con prueba de PostgreSQL.

Preflight incluye activos e inactivos y detecta colisiones de identificacion, username, tipo cliente y roles. Si hay duplicados, bloquear migracion con informe de IDs y referencias, pedir resolucion administrativa y repetir. No eliminar filas para satisfacer constraints. TipoCliente: nombre normalizado case-insensitive, decimal 0..100, proteccion de baja por clientes activos. Crear solo indices justificados por consultas; EXPLAIN sobre fixtures representativos antes de optimizar.

### 6. Ciclos de vida y seguridad

`POST /{recurso}/{id}/reactivar` para Persona, TipoCliente, Cliente, proveedores, Empleado y Usuario: requiere permiso actualizar, recupera el ID y revalida identidad, FKs y compatibilidad. Reactivacion ya activa es idempotente. Altas que encuentran rol inactivo devuelven 409 con referencia, nunca reactivan sin accion autorizada.

Persona: baja consulta Cliente, Proveedor Persona, Empleado, Usuario y sociedades donde es contacto; 409 con dependencias activas. Sin dependencias, soft delete auditado. TipoCliente: mismo guard para Clientes activos. Baja de Cliente/proveedores no altera Persona/Usuario/contacto.

Empleado: baja atomica de Empleado, Usuario por misma persona e invalidacion `sesion_invalidada_en`; nunca desactivar Persona. Usuario: baja y logout invalidan sesiones; reset invalida tokens previos como medida de seguridad y marca cambio obligatorio. Validar tambien refresh para no reemitir acceso revocado. Reactivar Empleado no reactiva Usuario; reactivar Usuario requiere accion administrativa separada con Persona/Rol activos, aviso de empleado inactivo si aplica y decision explicita auditada. Alta de Empleado sobre Persona con Usuario previo devuelve conflicto para decision administrativa; no crear otra cuenta ni alterar sus credenciales silenciosamente.

Politica unica de password de ocho o mas caracteres usada por create directo, Empleado, update de credenciales si se conserva, change-password y generador temporal. No rechazar login de usuarios historicos solo por longitud previa. Hashes nunca en Read/logs/auditoria; temporal una sola respuesta al actor autorizado; cambio correcto quita bandera; reset/creacion la activan. Username trim+lower, unico en toda instalacion.

Auditoria: revisar middleware/contexto y repositorios; actor JWT manda incluso si llega `usuario_auditoria`. Compatibilidad solo en seeds/tests/scripts confiables; no introducir un bypass HTTP. Proteger todos los endpoints/acciones y lectura de vinculos segun RBAC actual. Alta embebida requiere crear rol y crear Persona si realmente se inserta; si solo reutiliza, exige lectura de Persona y crear rol. Un 403 no debe revelar datos ni dejar escrituras parciales. Redactar datos sensibles en auditoria de accesos denegados.

### 7. Consultas y errores

Ampliar listado de Persona con `identificacion` exacta normalizada, `q`, `only_active=true`, `limit`, `offset`, orden/direccion de whitelist. `only_active=false` incluye inactivos; si se requiere solo inactivos, filtro `estado=inactivo` explicito sin reinterpretar el parametro legacy. Roles permiten buscar identidad relacionada mediante joins. TipoCliente y sociedad agregan filtros/orden pertinentes. Respuestas paginadas mantienen `items` y `meta` con total calculado sobre los mismos filtros, evitando truncar a 50/1000 o N+1.

`GET /personas/{id}/vinculos` devuelve roles con id/activo y sociedades contacto, dependencias activas, nombres legibles y auditoria permitida, nunca secretos. RBAC limita detalles sensibles de Usuario/Empleado sin debilitar el guard de baja.

Errores: 400 regla funcional, 401 auth, 403 permiso/tenant, 404 referencia ausente, 409 duplicidad/inactivo/dependencia/inmutabilidad, 422 payload. Mantener `detail` comprensible y anexar codigo/datos de conflicto si el manejador actual lo soporta; acordar forma exacta antes del frontend. No reemplazar reglas por mensajes genericos.

## Risks / Trade-offs

- Constraints con datos sucios -> preflight y resolucion humana; bloqueo sin perdida de referencias.
- Rollback interior del CRUD aborta savepoint -> caracterizar repositorio antes de implementar carrera y probar dos conexiones reales.
- Guard de baja frente a alta concurrente -> serializar operaciones relevantes sobre Persona con bloqueo compatible y probar competencia baja/alta; la lectura previa sola no basta.
- Cambios compartidos afectan otros dominios -> mantener API `commit` compatible, pruebas de regresion y gates completos.
- Alcance SRI incierto -> politica documentada y aislada, confirmar catalogo vigente antes de cambiar algoritmos.
- Directorio global expone limites multiempresa -> no prometer aislamiento inexistente; permisos y datos sensibles delimitados.

## Migration Plan

1. Caracterizar contratos, pruebas, migraciones reales y politica vigente; congelar OpenAPI compuesto con frontend.
2. Preflight solo lectura, backup y resolucion aprobada de colisiones; probar Alembic upgrade/downgrade en PostgreSQL descartable.
3. Desplegar restricciones/metadatos y backend compatible por ID; habilitar nuevas consultas y acciones con pruebas verdes.
4. Desplegar frontend comun por recorrido solo tras contratos listos; retirar payloads de actor y bypass `activo` coordinadamente.
5. Documentar y verificar CU010..CU013/CU004, seguridad, directorio, consumidor final y limites globales.

Rollback: deshabilitar nuevas altas UI y conservar contratos por ID; revertir version de aplicacion compatible sin perder filas. No deshacer constraints de seguridad/identidad en produccion ni borrar datos creados para facilitar rollback; downgrade solo con evaluacion/backup y plan aprobado. No ejecutar migraciones productivas durante planificacion.

## Open Questions

- Confirmar politica vigente para RUC sin algoritmo exigible, minimo de pasaporte y semantica de cada TipoContribuyente antes de cambiar validadores/backfill.
- Verificar disponibilidad de PostgreSQL de prueba y valores seguros de configuracion; no solicitar secretos por herramientas de preguntas.
- La visibilidad/habilitacion comercial por empresa y Cliente Sociedad requieren cambios posteriores, no bloquean este alcance pero si las afirmaciones de aislamiento/B2B completos.

## Traceability

| Documento fuente | Cobertura |
| --- | --- |
| D-001..D-008; RN-GEN-001..013 | Identidad, constraints, ciclo de vida, auditoria, FKs, inmutabilidad y RBAC |
| D-009; RN-CTX-001..007 | Contrato excluyente, resolver, carrera, rollback y permisos compuestos; UI en cambio par |
| RN-PER-001..010 | Normalizacion/validadores, duplicidad, cambio de identidad y guard de dependencias |
| RN-TC-001..004; RN-CLI-001..009 | TipoCliente, rol unico, FKs, reactivacion, Consumidor Final y alta contextual |
| RN-PP-001..010; RN-PS-001..008 | RUC/catalogo, constraints, contacto mutable y alta/cambio atomicos |
| RN-EMP-001..012; RN-USR-001..013 | Laboral, credenciales, atomicidad, baja/revocacion y reactivacion administrativa |
| RN-LIFE-001..003; RN-TENANT-001..002 | ID historico, auditoria y limites globales |
| H-001..H-012; secciones 55..71 | Verificacion de hallazgos, pruebas PostgreSQL, docs y backlog fuera de alcance |

## Implementation Evidence

Checkpoint 2026-10-03, fase de caracterizacion/datos:

- Baseline Directorio: 73 pruebas; caracterizacion adicional en test_empleado comprueba persona_id compartido, ausencia de credenciales en Empleado y un solo commit.
- Baseline frontend: 90 pruebas, lint y build verdes; no se habilitaron recorridos nuevos.
- PostgreSQL accesible por el puerto publicado 5435; host `postgres` solo resuelve dentro de Docker. Settings y credenciales no se modificaron.
- Preflight de solo lectura: 0 grupos conflictivos y 1 entrada pendiente de normalizacion; incluye activos/inactivos y referencias historicas detectadas por FKs. No se corrigio ni fusiono ningun dato.
- Confirmados H-002 (Proveedor Persona sin unique) y H-006 (username con unique sensible a case). Los indices/FKs de los otros roles estan declarados en las tablas actuales. TipoCliente ya tiene ck_descuento_rango en PostgreSQL.
- Revision e7a1b4c29d60 sobre d6f9a3c18b50: unique ProveedorPersona y claves normalizadas de Usuario, TipoCliente y Persona; el preflight bloquea antes de cualquier cambio de esquema. No se aplico a las tablas compartidas.
- Upgrade/downgrade e inserts SQL directos conflictivos verificados en un esquema PostgreSQL temporal aislado, eliminado al finalizar. Fixtures SQLite tambien prueban bloqueo sin cambios y preservacion de datos.
- Suite local tras esta fase: 519 passed, 2 skipped (incluye gate PostgreSQL condicionado a entorno, ejecutado aparte con exito). Ruff focalizado y mypy de preflight/CLI verdes usando MYPYPATH=src, explicit-package-bases y follow-imports=silent.
- Hallazgo adicional para fase 5: ambos servicios de proveedores declaran fk_map, pero BaseService consulta fk_models; corregir y cubrir FKs activas al integrar los servicios.
- Pendiente de aprobacion antes de fase 2.6: aplicabilidad semantica y politica local tributaria; preservar exclusiones actuales hasta decision explicita, sin inferir aplicabilidad de codigos desconocidos por texto.

### Final Functional Checkpoint

Las decisiones pendientes del checkpoint inicial fueron aprobadas por el usuario: metadatos `01/03` natural, `02/05` sociedad y `04` ambos; codigos desconocidos sin aplicabilidad hasta configuracion explicita. Se preservan algoritmos actuales y pasaporte minimo cinco caracteres, sin afirmar existencia/actividad SRI. RBAC por entidad, con grants iniciales solo para Administrador; no se sobrescriben permisos preexistentes. La delegacion de implementacion fue autorizada explicitamente.

| Hallazgo | Resultado |
| --- | --- |
| H-001 | Documentacion corregida a Persona natural |
| H-002 | Unique ProveedorPersona en entity y Alembic, probado por inserts PostgreSQL |
| H-003 | Baja Empleado revoca Usuario y access/refresh atomicamente |
| H-004 | DTO/servicios rechazan cambios de identidad y campos internos |
| H-005 | Contacto Sociedad mutable por ID o Persona nueva, con rollback |
| H-006 | Username trim/lower e indice unico normalizado; login alineado |
| H-007 | Politica unica de ocho caracteres en escrituras de password |
| H-008 | Actor autenticado autoritativo, pruebas de spoofing y auditoria de denegaciones sin payload sensible |
| H-009 | Validacion de contribuyente por flags, independiente del nombre |
| H-010 | Cliente Sociedad queda como capacidad futura, no workaround natural |
| H-011 | Maestros comerciales globales documentados; no aislamiento comercial completo |
| H-012 | Formato/algoritmo local separado del estado tributario y comprobante |

Matriz de contratos entregados y verificados con frontend:

| Recurso | Contrato |
| --- | --- |
| Personas | Identificacion exacta, q, estado, offset/limit, orden; GET vinculos; POST reactivar; GET contrato OpenAPI por prefijo API |
| TipoCliente | Nombre/decimal/guard de dependencias, GET vinculos, POST reactivar |
| Cliente y Proveedor Persona | POST persona_id XOR persona_nueva, Read con Persona, identidad inmutable, historicos/reactivar |
| Proveedor Sociedad | POST contacto existente/nuevo; PUT contacto mutable o nuevo; datos juridicos separados y telefono opcional |
| Empleado | POST Persona + Empleado + Usuario, decimal/fechas/empresa, baja revoca acceso, reactivar sin reactivar Usuario |
| Usuario | POST Persona + Usuario, username normalizado, Rol/password, reset, invalidar-sesion, reactivar administrativamente |
| Seguridad | Permisos propios autenticados; otros usuarios requieren RBAC; escrituras de roles/modulos/grants protegidas para impedir bypass |

Comprobaciones finales:

- Suite local backend: 667 passed, 8 skipped. Tests omitidos de PostgreSQL se ejecutaron separadamente con su entorno explicito; suite aislada de datos/RBAC/comerciales: 90 passed, incluyendo carreras con dos sesiones.
- Ruff global verde. Mypy focalizado: 45 archivos sin errores, incluidas las tres revisiones. Gate global sigue bloqueado por deuda heredada (baseline HEAD: 880 errores/109 archivos; comparacion worktree: 802/93), sin refactor ajeno al alcance.
- Revisiones e7a1b4c29d60, f8b2c5d30e71 y a9c3d6e41f82 aplicadas al entorno de desarrollo tras preflight limpio y respaldo custom de PostgreSQL con acceso restringido. No se fusionaron ni borraron datos para imponer constraints.
- Respaldo previo: `/var/folders/5f/_3nn02690s35k6g2ynlbhhfm0000gn/T/osiris-directory-backup-so4w53b9/before-directory-migrations.dump` (permisos 0600). No se restaurara automaticamente ni se hara downgrade productivo.
- API actualizada de prueba: `http://127.0.0.1:8003`; frontend: `http://127.0.0.1:4175`. Los servicios anteriores 8002/4174 no se detuvieron.
- E2E Playwright final: 36/36 comprobaciones desktop/mobile, cinco contextos existente/nueva, una llamada, estado preservado, dependencias, reactivacion, reset y acceso revocado; cero fallos del Directorio. Limpieza logica verificada de 129 registros UAT en cuatro ejecuciones; credenciales temporales retiradas de fixtures y credenciales preexistentes intactas.
- Reporte final: `/var/folders/5f/_3nn02690s35k6g2ynlbhhfm0000gn/T/osiris-directory-uat-k78_zkoj/report.json`; capturas en el mismo directorio. No publicar fixtures que contuvieron tokens.
- Incidencias independientes observadas en el shell existente: 409 en conteo de categorias sin empresa y 500 en remapeos por columna created_by ausente. No se altero inventario para ocultarlas.
- `make test` no ejecutado: depende del contenedor backend detenido y aplica limpieza fisica en la base compartida. No se marca como completado por equivalencia con pytest. Ambos cambios OpenSpec permanecen sin archivar hasta cerrar gates globales.

### Registered Subsequent Capabilities

| Capacidad futura | Limite obligatorio |
| --- | --- |
| customer-society | Modelar cliente juridico antes de declarar ventas B2B completas |
| directory-company-enablement | Habilitacion comercial por empresa antes de declarar aislamiento del Directorio |
| employee-multiemployment | Revisar unicidad laboral global para empleo simultaneo en varias empresas |
| customer-portal | Acceso de clientes con permisos y ciclo de vida propios |
| foreign-identification-and-fiscal-plate | Contratos fiscales separados; no alias silencioso de Pasaporte/Persona |

### Completed Global Gates

El usuario solicito explicitamente resolver los gates globales heredados y la incidencia de Remapeos para completar este cambio. Ese cierre amplia la reparacion de tipos a las areas necesarias del backend, sin introducir nuevas reglas de negocio ni capacidades fuera de alcance.

- Mypy mantiene `strict=true`; `mypy_path=src` y bases de paquete explicitas hacen reproducible el comando. `poetry run mypy -p osiris`: sin errores en 346 archivos; `poetry run mypy src`: sin errores en 320. No se excluyeron modulos ni se silenciaron errores globalmente.
- Se tiparon expresiones ORM con `sqlmodel.col`, retornos/protocolos y firmas reales. BaseService distingue entidad y proyeccion Read, con tipo Read por defecto compatible. El CRUD dinamico registra schemas concretos para FastAPI, probado mediante OpenAPI y peticiones HTTP.
- Se agregaron stubs de desarrollo `types-passlib` sin cambiar dependencias runtime. Los importes Decimal de campos calculados Pydantic se verificaron en ejecucion; formulas y politica tributaria permanecen intactas.
- Dockerfile.dev evita reutilizar el virtualenv macOS montado dentro de Linux. Backend Docker activo en 8002; PostgreSQL en 5435. Los servidores de prueba 8003/4175 permanecen disponibles.
- Remapeos: revision `b0d4e7f52a93` agrega created_by/updated_by e indices a tbl_producto_atributo_remapeo, con backfill legacy; upgrade/downgrade y preservacion de filas/FKs probados en SQLite y PostgreSQL aislado. Aplicada en desarrollo tras respaldo. Endpoint comprobado: 200, total 0.
- Respaldo previo al gate Docker: `/var/folders/5f/_3nn02690s35k6g2ynlbhhfm0000gn/T/osiris-before-make-test-l0phyct9/development.dump`, formato custom, verificado con pg_restore --list, permisos 0600.
- `make test` completo, sin omitir su fase de migraciones/limpieza: 683 passed, 8 skipped, exit 0. El fixture de Kardex registra ambos caminos de consulta y sigue verificando fechas, movimientos y parametros SQL.
- Ruff global aprobado. Frontend 125 pruebas, lint y build verdes. E2E repetido despues de reiniciar la API final: 36/36, desktop/mobile, cinco contextos y cero errores inesperados.
- Informe E2E de cierre: `/var/folders/5f/_3nn02690s35k6g2ynlbhhfm0000gn/T/osiris-directory-uat-rvzdoqaf/report.json`. Datos UAT desactivados, cero limpieza pendiente, secretos temporales retirados y credenciales/sesiones/permisos originales intactos.
- El 409 de conteo de categorias sin empresa representa el contexto requerido; el 500 de Remapeos esta resuelto. Los checkpoints historicos anteriores no describen el estado actual.
- Tareas completas 63/63 backend y 55/55 frontend. No se archiva automaticamente ni se realizan commits; cambio listo para archivo posterior explicito.
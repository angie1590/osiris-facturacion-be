## 1. Caracterizacion y contrato compartido

- [x] 1.1 Contrastar D-001..D-009 y H-001..H-012 del documento con entidades, DTO, servicios, routers, middleware y Alembic actuales; registrar confirmado/resuelto/pendiente sin asumir el estado del commit original.
- [x] 1.2 Ejecutar baseline de pruebas existentes de Persona, TipoCliente, Cliente, proveedores, Empleado, Usuario, auditoria y sesiones; agregar caracterizaciones en esos mismos archivos antes de cambiar comportamiento.
- [x] 1.3 Congelar OpenAPI de union excluyente persona_id/persona_nueva y contacto_id/contacto_nuevo, respuestas Read, errores de conflicto, listados, vinculos y acciones de reactivacion con el cambio frontend homonimo.
- [x] 1.4 Inventariar permisos efectivos por endpoint/accion/empresa y acordar permisos de buscar, crear Persona embebida, reactivar, reset e invalidar sesion; revisar compatibilidad con organization-and-access del cambio de dominio existente.
- [x] 1.5 Confirmar politica vigente de cedula/RUC/pasaporte, minimo de pasaporte y aplicabilidad de cada TipoContribuyente; documentar fuentes y distinguir formato local, estado SRI y comprobante.

## 2. Preflight y migraciones seguras

- [x] 2.1 Agregar preflight solo lectura en scripts existentes o un script dedicado si no hay uno adecuado: duplicados por persona_id en roles, colisiones normalizadas de identificacion/username/nombre TipoCliente y RUC; incluir inactivos y referencias historicas.
- [x] 2.2 Definir bloqueo de migracion ante colisiones y procedimiento de resolucion administrativa sin borrar/fusionar automaticamente; verificar con fixtures conflictivos y limpios.
- [x] 2.3 Verificar unique/FKs reales de Persona, Cliente, Empleado, Usuario y Proveedor Sociedad; crear revision Alembic para UNIQUE(tbl_proveedor_persona.persona_id) si falta, alineando entity y esquema.
- [x] 2.4 Crear revision Alembic para username normalizado e indice unico lower(trim(username)); proteger activos e inactivos y probar insercion SQL directa case-insensitive.
- [x] 2.5 Alinear nombre normalizado unique y descuento decimal 0..100 de TipoCliente mediante Alembic cuando el esquema requiera cambios; evitar funciones incompatibles con pruebas SQLite sin confundirlas con PostgreSQL.
- [x] 2.6 Agregar metadatos semanticos de aplicabilidad de TipoContribuyente, backfill aprobado por codigo, modelos Read y migracion Alembic; no inferir semantica solo por nombre.
- [x] 2.7 Probar upgrades/downgrades de nuevas revisiones en PostgreSQL descartable y comprobar constraints/FKs con inserts directos; ejecutar preflight antes de cualquier aplicacion a datos existentes.

## 3. Identidad Persona y consultas

- [x] 3.1 Centralizar normalizacion/validacion y reutilizarla en DTO, busqueda y servicios; cubrir cedula valida/invalida, RUC natural, pasaporte, trim/mayusculas, email, longitudes y duplicados.
- [x] 3.2 Exigir tipo_identificacion al cambiar identificacion y revalidar combinacion completa; cubrir payload parcial y collision con registro inactivo.
- [x] 3.3 Agregar filtro exacto identificacion y q por identificacion/nombre/apellido/email/telefono con paginacion/orden permitidos y total correcto; mantener only_active=true por defecto y semantica include-inactive compatible.
- [x] 3.4 Implementar GET personas/{id}/vinculos con estados/IDs de roles, sociedades contacto, dependencias y datos legibles permitidos; excluir hashes y limitar datos sensibles segun RBAC.
- [x] 3.5 Implementar guard de baja Persona por todas las dependencias activas, incluidas sociedades contacto, con 409 detallado y prueba de cada dependencia.
- [x] 3.6 Implementar reactivacion explicita Persona con permiso actualizar, mismo ID y auditoria; bloquear bypass via activo en update generico.
- [x] 3.7 Serializar baja/alta dependiente sobre Persona segun ciclo de Session existente y probar que una carrera no deja roles activos apuntando a Persona inactiva.

## 4. Resolucion contextual transaccional

- [x] 4.1 Implementar DTO compuesto compartido y validacion excluyente en create de Cliente, Proveedor Persona, Empleado y Usuario; validar contacto equivalente en sociedad y cubrir ambas/ninguna/null.
- [x] 4.2 Implementar resolver/orquestador de Persona normalizada: reutilizar activa sin sobrescribir, rechazar inactiva con referencia y crear nueva sin commit interior.
- [x] 4.3 Adaptar solo servicios/repositorios que lo necesiten para participar con commit=False; revisar flush, savepoint y rollback del repositorio y cubrir excepciones anteriores al commit exterior.
- [x] 4.4 Implementar recuperacion acotada de carrera por la restriccion exacta de identificacion, usando savepoint seguro o reintento completo; no tratar otros IntegrityError como Persona existente.
- [x] 4.5 Agregar pruebas PostgreSQL con dos sesiones para Persona ganadora compartida, rol duplicado y conflicto con Persona inactiva; comprobar un solo ID sin sobrescritura de identidad.

## 5. TipoCliente y roles comerciales

- [x] 5.1 Validar TipoCliente normalizado, descuento decimal y baja bloqueada por Clientes activos; implementar reactivacion auditada y pruebas de rango/nombre/dependencia.
- [x] 5.2 Integrar alta Persona+Cliente en una transaccion; validar Persona/TipoCliente activos, conflicto activo/inactivo y pruebas de rollback por FK, duplicidad y fallo de persistencia.
- [x] 5.3 Rechazar cambio efectivo persona_id de Cliente en DTO y servicio, permitir cambio TipoCliente auditado y agregar pruebas que impidan silencio por extra=ignore.
- [x] 5.4 Integrar alta Persona+Proveedor Persona, validar RUC natural y metadatos activos de contribuyente; cubrir CEDULA, categoria incompatible y constraint SQL real.
- [x] 5.5 Rechazar cambio efectivo persona_id de Proveedor Persona; implementar reactivacion con mismo ID y pruebas de baja sin alterar Persona/Usuario.
- [x] 5.6 Integrar alta contacto Persona+Proveedor Sociedad con RUC juridico unique, razon/direccion, email y telefono opcional; cubrir duplicidad/inactivos/FKs y rollback.
- [x] 5.7 Permitir cambio de contacto existente/nuevo en ProveedorSociedad, con union excluyente y transaccion completa; probar contacto anterior intacto y rollback del nuevo contacto ante fallo.
- [x] 5.8 Implementar reactivacion auditada de Cliente y Sociedad revalidando FKs/compatibilidad; impedir activo arbitrario como bypass y mantener independencia de Persona/contacto.
- [x] 5.9 Agregar busqueda/orden/paginacion de roles comerciales por datos relacionados de Persona y sociedad, con totals correctos e indices justificados, sin copiar identidad a tablas.

## 6. Usuario y politica de credenciales

- [x] 6.1 Centralizar politica de ocho o mas caracteres en Usuario create/update, Empleado, change-password y reset; adaptar fixtures sin restringir login de claves historicas por longitud.
- [x] 6.2 Aplicar trim/lower a username en create/login/conflictos y cubrir duplicados activos/inactivos/case-insensitive, alineados con constraint SQL.
- [x] 6.3 Rechazar cambio efectivo persona_id/username en Usuario y validar Rol activo; probar que DTO y servicio no ignoran campos inmutables.
- [x] 6.4 Integrar alta directa Persona+Usuario sin exigir Empleado; garantizar hash, requiere_cambio_password=true, FKs y rollback por rol/username/persistencia.
- [x] 6.5 Verificar reset temporal una sola respuesta autorizada, politica unica, cambio obligatorio, auditoria y limpieza de secretos en Read/logs; invalidar sesiones previas al reset.
- [x] 6.6 Implementar/verificar baja Usuario, logout e invalidacion de access/refresh; cubrir login inactivo, tokens previos, cambio exitoso de password y permisos de acciones de seguridad.
- [x] 6.7 Implementar reactivacion administrativa Usuario con Persona/Rol activos y decision explicita ante Empleado inactivo; recuperar mismo ID sin nueva cuenta y registrar auditoria.

## 7. Empleado y revocacion de acceso

- [x] 7.1 Cubrir salario decimal no negativo, EMP_MIN_AGE default 16, ingreso no futuro y salida posterior; validar updates contra fechas existentes y Empresa activa/autorizada.
- [x] 7.2 Extender creacion existente a Persona+Empleado+Usuario con un commit exterior; cubrir Persona por ID/nueva, Usuario previo como conflicto y ninguna sobrescritura de credenciales.
- [x] 7.3 Agregar rollback si falla Usuario, Empleado, FK laboral, flush o commit y comprobar desde otra sesion que no quedan Persona/Empleado/Usuario parciales.
- [x] 7.4 Rechazar cambios efectivos persona_id en Empleado con mensaje explicito desde DTO/servicio; mantener unicidad global actual sin habilitar multiempleo.
- [x] 7.5 Implementar baja transaccional Empleado+Usuario+sesion_invalidada_en por misma Persona, sin afectar Persona/Cliente/proveedores; cubrir Usuario ausente o ya inactivo.
- [x] 7.6 Probar rollback de baja y rechazo de access/refresh previos; verificar que ex-empleado no autentica tras revocacion.
- [x] 7.7 Implementar reactivacion Empleado con Persona/Empresa activas y mismo ID, sin reactivar Usuario automaticamente; documentar accion administrativa separada.
- [x] 7.8 Agregar consultas paginadas/orden/busqueda relacionada de Empleados y Usuarios sin exponer hashes ni datos no permitidos.

## 8. Auditoria y permisos transversales

- [x] 8.1 Revisar contexto JWT/middleware/repositorios y asegurar actor autoritativo en todas las escrituras; probar usuario_auditoria falsificado y conservar compatibilidad solo para scripts/tests confiables.
- [x] 8.2 Verificar RBAC read/create/update/delete y seguridad en cada endpoint del alcance, incluida lectura de vinculos, cambio de contacto y reactivacion; cubrir llamadas directas 403.
- [x] 8.3 Validar permisos compuestos para Persona nueva y rol, reutilizacion de Persona existente y tenant de Empleado antes de persistir; probar 403 sin registros parciales ni fuga de datos.
- [x] 8.4 Registrar auditoria create/update/deactivate/reactivate/reset y accesos denegados, redactando passwords/codigo de aprobacion/tokens; probar actor/timestamps y transacciones revertidas.

## 9. Documentacion y entrega coordinada

- [x] 9.1 Corregir intro a Persona natural y actualizar Directorio/Seguridad/empresa de sesion con unicidades, contacto mutable, baja Empleado->Usuario, errores, consultas y reactivacion.
- [x] 9.2 Documentar Search-or-Create, contrato excluyente, permisos compuestos, carrera/rollback y politica tributaria por tipo; actualizar CU010..CU013 y CU004.
- [x] 9.3 Registrar en OpenSpec deuda de Cliente Sociedad, exterior/placa fiscal, habilitacion comercial por empresa, multiempleo y portal; no declarar ventas B2B ni aislamiento completo sin esos cambios.
- [x] 9.4 Publicar matriz de endpoints listos para frontend: fases 3/4 habilitan bloque comun, fase 5 comerciales, fases 6/7 acceso; no habilitar recorrido sin pruebas del contrato correspondiente.
- [x] 9.5 Verificar no regresion de Consumidor Final cliente_id=null, referencias historicas de compras/ventas/cartera, stock sin cambios y compatibilidad FE-EC; no modificar calculos SRI.

## 10. Gates de cierre ejecutables

- [x] 10.1 Ejecutar pruebas enfocadas: `poetry run pytest tests/test_persona.py tests/test_cliente.py tests/test_tipo_cliente.py tests/test_proveedor_persona.py tests/test_proveedor_sociedad.py tests/test_empleado.py tests/test_usuario.py tests/test_auth_session_invalidation.py tests/test_audit_context.py tests/test_security_access_audit.py`.
- [x] 10.2 Ejecutar suite PostgreSQL de constraints/migraciones/carreras con entorno descartable configurado y Alembic upgrade/downgrade; registrar comando reproducible y no sustituir por SQLite/mock.
- [x] 10.3 Ejecutar `make test` y corregir fallos antes de cierre; no marcar terminado con suite roja ni ocultar gates bloqueados por entorno.
- [x] 10.4 Ejecutar `poetry run ruff check .` y `poetry run mypy src` conforme a configuracion vigente, registrar resultados y resolver regresiones del cambio.
- [x] 10.5 Ejecutar `openspec validate refactor-directory-person-client-supplier-employee-user --strict --no-interactive` y cotejar trazabilidad documento->spec->prueba, incluidas operaciones compuestas y sesiones.
- [x] 10.6 Validar conjuntamente con frontend los cinco recorridos sobre backend real y cerrar solo con atomicidad, permisos y datos persistidos verificados; planificar archivo OpenSpec despues, sin archivarlo anticipadamente.

## Estado De Gates

Gates completados el 2026-10-03. Todas las tareas implementadas y verificadas; listo para archivo posterior por solicitud explicita.

- 10.3: `make test` ejecutado en Docker con su flujo original de migraciones/limpieza: 683 passed, 8 skipped, exit 0. Respaldo PostgreSQL custom verificado antes de ejecutarlo, permisos 0600. El fallo inicial del fixture de Kardex se corrigio capturando Session.exec y Session.execute, conservando las aserciones de fechas/SQL.
- 10.4: `poetry run ruff check .` verde; `poetry run mypy -p osiris` verde en 346 archivos; `poetry run mypy src` verde en 320. Modo strict conservado, sin exclusiones nuevas ni ignore_errors; se corrigieron firmas, expresiones SQLModel, contratos genericos y stubs passlib de desarrollo.
- 10.6: 36/36 comprobaciones E2E desktop/mobile sobre API actualizada, cinco contextos; cero limpieza pendiente. Remapeos responde 200 tras la migracion b0d4e7f52a93. Credenciales, sesiones y permisos originales preservados.
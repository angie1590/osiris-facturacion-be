# Configuración por ambiente: base, certificados y FE-EC

La configuración se carga desde `.env.<ENVIRONMENT>` en la raíz del backend y luego se sobrescribe con variables del proceso. No versionar contraseñas, claves privadas, certificados ni URLs con credenciales.

## Matriz operativa

| Ambiente | Base de datos | FE-EC / SRI | Firma y esquema |
| --- | --- | --- | --- |
| Desarrollo con Compose | `DATABASE_URL` usa el hostname del servicio PostgreSQL y el puerto interno. | `FEEC_AMBIENTE=pruebas`; usar `SRI_MODO_EMISION=NO_ELECTRONICO` para flujos sin envío real. El mock de gateway solo se habilita explícitamente con `FEEC_MOCK_ENABLED=true`. | La firma se configura por empresa. El XSD es necesario si se habilita emisión electrónica. |
| Pruebas automatizadas | Usar SQLite aislado o una base PostgreSQL de prueba dedicada; no apuntar pruebas destructivas a una base compartida. | Inyectar gateways/mocks en pruebas unitarias. `FEEC_MOCK_ENABLED=true` solo simula autorización en `development`/`test`; los tests de FE no deben llamar al SRI real. | Usar archivos XSD de fixture; nunca copiar claves productivas a fixtures. |
| Staging / certificación | Base aislada y credenciales entregadas por el entorno. | `ENVIRONMENT=staging`, `FEEC_AMBIENTE=pruebas`; habilitar emisión solo para pruebas autorizadas. | Certificado de pruebas custodiado por el entorno; fecha de caducidad comprobada antes de emitir. |
| Producción | `DATABASE_URL` y `DB_URL_ALEMBIC` provienen del gestor de secretos. Aplicar Alembic antes de desplegar código. | `ENVIRONMENT=production`, `FEEC_AMBIENTE=produccion`; la integración debe fallar cerrada si FE-EC no está disponible. | XSD desplegado y versionado; firma por empresa cifrada en base de datos. No configurar autorización simulada. |

## Variables

| Variable | Requerida | Uso |
| --- | --- | --- |
| `ENVIRONMENT` | No; por defecto `development` | Selecciona `.env.<ENVIRONMENT>`. Valores operativos: `development`, `staging`, `production`; pruebas usan fixtures aislados. |
| `DATABASE_URL` | Sí | Conexión SQLAlchemy a PostgreSQL o SQLite de prueba. |
| `DB_URL_ALEMBIC` | No | Conexión separada de Alembic; si falta se reutiliza `DATABASE_URL`. |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Sí | Parámetros usados por Compose; en despliegues deben venir del gestor de secretos. |
| `SECRET_KEY` | Tiene default solo para desarrollo | Clave JWT. Reemplazar en staging/producción y rotar según política operativa. |
| `SRI_MODO_EMISION` | No; por defecto `ELECTRONICO` | `ELECTRONICO` o `NO_ELECTRONICO`. El modo electrónico requiere `FEEC_XSD_PATH`. |
| `FEEC_AMBIENTE` | No; por defecto `pruebas` | `pruebas` o `produccion`; debe corresponder al certificado y endpoint SRI del ambiente. |
| `FEEC_MOCK_ENABLED` | No; por defecto `false` | Solo `true` en `development` o `test`; en staging/producción la dependencia FE ausente siempre rechaza la emisión. |
| `FEEC_TIPO_EMISION` | Sí | `1` normal o `2` contingencia. |
| `FEEC_REGIMEN` | Sí | Régimen declarado para generar el comprobante; valores aceptados están validados en `Settings`. |
| `FEEC_XSD_PATH` | Condicional | Ruta absoluta o relativa al repo del XSD; obligatoria con `SRI_MODO_EMISION=ELECTRONICO`. |
| `FEEC_P12_PATH`, `FEEC_P12_PASSWORD` | No | Variables legadas opcionales. La emisión vigente obtiene la firma cifrada de la empresa; no usar valores globales productivos. |
| `FE_QUEUE_AUTO_PROCESS_ENABLED`, `FE_QUEUE_POLL_INTERVAL_SECONDS` | No | Procesamiento automático y frecuencia de la cola SRI; el intervalo mínimo es 5 segundos. |

La dependencia FE-EC se instala desde `lib/fe_ec-0.1.0-py3-none-any-3.whl`, declarada en `pyproject.toml`; no se debe sustituir por una versión de PyPI sin validar compatibilidad. Los XSD se mantienen bajo `conf/sri_docs/`. La firma subida por empresa se cifra y su estado incluye caducidad.

## Arranque local

- Compose: el backend usa el servicio PostgreSQL por nombre interno y expone la API en el puerto configurado por Compose.
- Backend directo en macOS: configurar `DATABASE_URL` hacia `127.0.0.1` y el puerto PostgreSQL publicado; no usar el hostname Compose `postgres` fuera de la red Docker.
- Aplicar cambios de esquema con Alembic. No usar `SQLModel.metadata.create_all()` en producción.

## Modo mock

El gateway solo devuelve autorización simulada cuando FE-EC no está disponible, `FEEC_MOCK_ENABLED=true` y `ENVIRONMENT` es `development` o `test`. Si falta FE-EC en staging o producción, el documento se rechaza y queda auditable; el flag no habilita autorización simulada fuera de esos ambientes.
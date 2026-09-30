# Instrucciones para asistentes de código (Copilot / AGENT)

Breve (qué necesitas saber para ser productivo)

- Stack: Python 3.10, FastAPI + SQLModel/SQLAlchemy. Código en `src/osiris`. App exportada en `src/osiris/main.py` (variable `app`).
- Configuración: `src/osiris/core/settings.py` usa pydantic-settings y resuelve rutas relativas respecto al root del repo. Busca `.env.<ENVIRONMENT>` (por defecto `development`).

Arquitectura y patrones esenciales

- Modular: cada dominio vive en `src/osiris/modules/common/<nombre>/` y sigue: entity, models, repository, service, router.
- Enrutado: los routers se registran en `src/osiris/main.py` y tienen prefijo `/api`.
- CRUD generator: `src/osiris/domain/router.py::register_crud_routes` espera que un `service` implemente `list_paginated(session, ...)`, `get(session, id)`, `create(session, dto)`, `update(session, id, dto)`, `delete(session, id)`.
- DB: `src/osiris/core/db.py` exporta `engine` y `get_session()` (dependencia FastAPI). Las sesiones son síncronas; los servicios reciben una `Session` y devuelven instancias SQLModel.
- No ejecutar `SQLModel.metadata.create_all()` — el esquema evoluciona con Alembic (revisiones/autogenerate).

Comandos y flujos de desarrollo (ejemplos comprobados)

- Instalar deps: `poetry install`.
- Levantar containers: `make build` / `make up` (usa `docker compose`, nota el espacio).
- Crear migración: `PYTHONPATH=src ENVIRONMENT=development poetry run alembic revision --autogenerate -m "mensaje"`
- Aplicar migraciones: `make migrate`.
- Correr tests: `make test` (o `poetry run pytest`). `pytest.ini` ya añade `pythonpath = src`.
- Ejecutar local: `PYTHONPATH=src poetry run uvicorn osiris.main:app --reload --port 8000`.

Integraciones y dependencias clave

- Rueda local: `lib/fe_ec-0.1.0-*.whl` (paquete `fe-ec`) — no asumas que está en PyPI; está referenciada en `pyproject.toml`.
- Archivos sensibles: `conf/firma.p12`, `conf/sri_docs/*.xsd` — `Settings` carga rutas relativas; valida antes de moverlos.

Convenciones de código que afectan cambios

- Servicios reciben `Session` y retornan modelos SQLModel. Mantén esa firma para compatibilidad con `register_crud_routes`.
- Evita imports que dependan de rutas relativas fuera de `src/` — el proyecto asume `PYTHONPATH=src`.
- Validaciones de settings lanzan `RuntimeError` con mensajes legibles: si añades variables de entorno, actualiza `.env.development` y documenta en README.

Qué hacer antes de abrir PR / cambiar infra

- Ejecutar toda la suite: `make test` y corregir fallos.
- Ejecutar linters y tipos: `poetry run ruff` y `poetry run mypy`.
- Si tocas modelos/db: crear migración Alembic y verificar `ENVIRONMENT` + `PYTHONPATH=src` antes de generar la revisión.

Preguntas rápidas que pedir al mantenedor

- ¿Hay valores de `.env.development` de prueba para CI/local? (si no, pide credenciales de prueba o un archivo .env temporal).
- ¿Se debe mantener compatibilidad con la rueda local `lib/fe_ec-*.whl` o migrar a un paquete externo?

Dónde mirar primero (archivos ejemplares)

- Entrada app: `src/osiris/main.py`
- Settings: `src/osiris/core/settings.py`
- DB/session: `src/osiris/core/db.py`
- CRUD generator: `src/osiris/domain/router.py`
- Ejemplo de módulo: `src/osiris/modules/common/cliente/` (entity/models/repository/service/router)

Si algo es inseguro o no puedes ejecutar pruebas porque faltan secretos, pregunta al mantenedor antes de modificar settings/firmas.

## Uso de RTK (Rust Token Killer)

RTK está instalado y disponible en el entorno de desarrollo.

### Regla general

Cuando ejecutes comandos de terminal, utiliza RTK siempre que exista un equivalente soportado, especialmente para comandos que puedan producir salidas extensas.

El objetivo es reducir el consumo de tokens y mantener el contexto del agente limpio sin perder información necesaria para realizar la tarea.

### Comandos preferidos

Preferir:

- `rtk git status` en lugar de `git status`
- `rtk git diff` en lugar de `git diff`
- `rtk git log` en lugar de `git log`
- `rtk ls` en lugar de `ls`
- `rtk grep` en lugar de `grep` cuando sea apropiado
- `rtk read` en lugar de `cat` para inspeccionar archivos
- `rtk pytest` en lugar de ejecutar `pytest` directamente, cuando sea compatible
- otros comandos `rtk` equivalentes cuando RTK los soporte

Para comandos ejecutados mediante Poetry, Make, Docker u otras herramientas del proyecto, usa RTK únicamente cuando exista un wrapper compatible y no altere la semántica del comando.

### Excepciones

Ejecuta el comando original sin RTK cuando:

1. RTK no soporte el comando u opción requerida.
2. Se necesite la salida exacta y sin filtrar para diagnosticar un problema.
3. La salida comprimida por RTK omita información necesaria.
4. El uso de RTK pueda cambiar el comportamiento esperado del comando.

Si la salida de RTK es suficiente, NO ejecutes inmediatamente después el mismo comando sin RTK.

### Exploración del repositorio

Durante tareas de análisis o investigación del código:

1. Empieza por búsquedas y listados específicos.
2. Evita leer archivos completos cuando solo necesitas localizar una función, clase o referencia.
3. Usa `rtk grep` para localizar símbolos o referencias cuando sea apropiado.
4. Usa `rtk read` para inspeccionar archivos cuando RTK pueda reducir la salida.
5. Amplía la búsqueda solo cuando la información obtenida sea insuficiente.

### Git

Para inspeccionar cambios, prefiere:

- `rtk git status`
- `rtk git diff`
- `rtk git diff --stat`
- `rtk git log`

No realices commits, pushes, resets, rebases, checkouts destructivos ni descartes cambios existentes salvo que el usuario lo solicite explícitamente.

### Verificación

RTK es una optimización de contexto, no una restricción funcional.

Si RTK impide obtener información necesaria para completar correctamente una tarea, utiliza el comando original y continúa con el análisis.

### Fin

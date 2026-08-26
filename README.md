# 🏛️ Osiris Backend

Backend del sistema empresarial **Osiris**, desarrollado en **Python 3.10** utilizando **Poetry** para la gestión de dependencias y **Docker** para contenerización. Este servicio maneja información tributaria, usuarios, empleados, clientes, proveedores, compras, ventas e inventario. Incluye una integración modular con la librería de facturación electrónica de Ecuador.

---

## 📁 Estructura del Proyecto

```
osiris-be/
├── conf/                      # Archivos de configuración (.p12, .xsd, JSON catálogos SRI)
│   ├── aux_impuesto_catalogo.json
│   ├── firma.p12
│   └── sri_docs/
│       └── factura_V1_1.xsd
├── lib/                      # Librería de facturación empaquetada (.whl)
│   └── fe_ec-0.1.0-py3-none-any-3.whl
├── scripts/                  # Scripts de utilidad y seed
│   ├── seed_sample_product.py
│   └── cleanup_test_data.py
├── src/
│   └── osiris/
│       ├── core/            # Configuración (settings, db, security, errors)
│       │   ├── settings.py
│       │   ├── db.py
│       │   └── security.py
│       ├── db/              # Migraciones Alembic
│       │   └── alembic/
│       │       └── versions/
│       ├── domain/          # Modelos base, repositorios, servicios, routers genéricos
│       │   ├── base_models.py
│       │   ├── repository.py
│       │   ├── service.py
│       │   └── router.py
│       ├── modules/         # Módulos de dominio (DDD)
│       │   ├── common/      # Entidades comunes (empresa, persona, cliente, etc.)
│       │   ├── sri/         # Catálogos tributarios y orquestación FE
│       │   ├── inventario/  # Catálogo/maestros y movimientos de inventario
│       │   ├── compras/     # Compras, CxP y retenciones emitidas
│       │   ├── ventas/      # Ventas, CxC y retenciones recibidas
│       │   ├── reportes/    # Reportería gerencial/tributaria
│       │   └── impresion/   # RIDE, ticket térmico y preimpresa
│       ├── utils/           # Utilidades (validaciones, paginación)
│       └── main.py          # Punto de entrada FastAPI
├── tests/                   # Pruebas unitarias y smoke tests
│   ├── smoke/              # Pruebas smoke de integración
│   │   ├── test_all_endpoints.py
│   │   ├── test_crud_smoke.py
│   │   ├── test_producto_smoke.py
│   │   └── utils.py
│   ├── test_empresa.py     # Pruebas unitarias
│   ├── test_producto.py
│   └── test_impuesto_catalogo.py
├── .env.development         # Variables de entorno (desarrollo)
├── pyproject.toml           # Configuración de Poetry
├── poetry.lock
├── Dockerfile.dev           # Imagen Docker para desarrollo
├── docker-compose.yml       # Orquestación de contenedores
├── Makefile                 # Comandos útiles para desarrollo
└── README.md
```

---

## ⚙️ Variables de Entorno

⚠️ **El archivo `.env.development` NO está en el repositorio por seguridad.** Debes crearlo manualmente en la raíz del proyecto.

Ejemplo `.env.development`:

```env
ENVIRONMENT=development

# Base de datos
POSTGRES_USER=postgres
POSTGRES_PASSWORD=dev_password
POSTGRES_DB=osiris_db
DATABASE_URL=postgresql+psycopg://postgres:dev_password@postgres/osiris_db
DB_URL_ALEMBIC=postgresql+psycopg://postgres:dev_password@postgres/osiris_db

# Facturación Electrónica Ecuador
# Rutas relativas al directorio /app dentro del contenedor
FEEC_P12_PATH=conf/firma.p12
FEEC_P12_PASSWORD=clave123
FEEC_XSD_PATH=conf/sri_docs/factura_V1_1.xsd
FEEC_AMBIENTE=pruebas
SRI_MODO_EMISION=ELECTRONICO
FEEC_TIPO_EMISION=1
FEEC_REGIMEN=GENERAL

# Configuraciones adicionales
SQL_ECHO=true
EMP_MIN_AGE=16
```

---

## ▶️ Comandos con Makefile

```bash
# Desarrollo
make build              # Construye imagen Docker
make run                # Levanta los contenedores (build + up -d)
make bootstrap-zero     # Flujo completo desde cero (rebuild + deps + migraciones + seed + docs)
make stop               # Detiene los servicios
make shell              # Acceso al contenedor backend
make logs               # Ver logs en tiempo real

# Base de datos
make db-upgrade         # Ejecuta migraciones Alembic
make db-makemigration   # Crea nueva migración autogenerada (requiere mensaje="...")
make db-recreate        # DROP/CREATE DB + alembic upgrade (no toca migrations)

# Testing
make test               # Ejecuta la suite completa (incluye smoke live, sin skips)
make smoke              # Ejecuta smoke tests (tests/smoke)
make smoke-ci           # Ejecuta smoke tests seguros para CI (solo listados)

# Utilidades
make lint               # Ejecuta linters (ruff + mypy)
make docs-audit         # Valida que docs/docs/api cubra todos los endpoints del backend
make gate-go-no-go      # Gate técnico base (lint + tests + build docs)
make security-scan      # Bandit + pip-audit (con política estricta por defecto)
make enterprise-gate    # Gate integral: técnico + seguridad + cobertura docs
make enterprise-gate-runtime  # Validaciones runtime (performance + DR)
make seed               # Carga datos completos de prueba (empresa, productos, bodegas, etc.)
make seed-sample        # Carga solo un producto de ejemplo (seed antiguo)
make verify-seed        # Verifica datos cargados por el seed
make verify-relations   # Verifica relaciones de productos (categorías, impuestos, bodegas)
make cleanup-test-data  # Limpia datos de prueba
make validate           # Valida configuración del entorno (multiplataforma)
```

Nota: en instalaciones modernas de Docker el comando es el plugin `docker compose` (espacio). El `Makefile` ya usa `docker compose --env-file ...`, por lo que los objetivos `make build`/`make run` funcionarán con la CLI moderna. Si tu sistema aún requiere el binario legacy `docker-compose`, instala `docker-compose` o crea un alias local.

### ✅ Secuencia recomendada para dejar todo en verde

```bash
make validate
make build
make run
make db-upgrade
make docs-audit
make test
make stop
```

### 🔐 Gate Enterprise y Política de Seguridad

```bash
# Gate integral (estricto)
make enterprise-gate

# Solo seguridad (estricto)
make security-scan

# Solo para entornos sin internet / troubleshooting local:
make security-scan SECURITY_SCAN_STRICT=false
```

Detalles relevantes del flujo de seguridad:
- Antes del lock, se normaliza automáticamente el wheel local `fe-ec` con `scripts/patch_feec_wheel_constraints.py`.
- Luego se ejecuta `poetry lock --regenerate --no-cache` para evitar metadata cacheada.
- Se audita con `bandit` y `pip-audit`.
- En modo estricto (`SECURITY_SCAN_STRICT=true`), cualquier hallazgo de `pip-audit` falla el gate.

### 🧯 Reseteo seguro de base de datos

Para reconstruir la base sin comprometer el historial de migraciones:

```bash
# Opción recomendada
make db-reset && make db-upgrade

# (Opcional) Cargar datos de ejemplo
make seed

# Alternativa equivalente en un paso
make db-recreate  # hace DROP/CREATE y luego alembic upgrade head
```

Buenas prácticas:
- No borrar `src/osiris/db/alembic/versions/*`.
- No "re-inicializar" migraciones autogenerando una única migración inicial.
- Preservar la historia asegura coherencia entre ambientes y en CI.

### 🖥️ Compatibilidad Multiplataforma (Mac/Windows/Linux)

El proyecto está configurado para funcionar en **Mac, Windows 11 y Linux** sin cambios:

✅ **Cambios aplicados para compatibilidad:**
- Docker detecta automáticamente la arquitectura (ARM64/AMD64)
- Variables de entorno se pasan con `-e` (compatible con todos los sistemas)
- Imports estandarizados a `osiris.*` (sin hacks de `PYTHONPATH`)
- Rutas de archivos usan formato Linux dentro del contenedor

⚠️ **Requisitos por sistema operativo:**
- **Windows**: Docker Desktop con WSL2 habilitado
- **Mac**: Docker Desktop (Intel o Apple Silicon)
- **Linux**: Docker Engine + Docker Compose plugin

💡 **Si usas Windows y tienes errores:**

**WSL2:**
- Verifica instalación: `wsl --list --verbose` en PowerShell
- Si WSL2 no responde pero Docker Desktop funciona, ignora el warning
- Instalar WSL2: `wsl --install` (requiere reinicio)
- Configurar como v2: `wsl --set-default-version 2`

**Docker Desktop:**
- Debe estar en modo "Use WSL 2 based engine" (Settings > General)
- Backend WSL2 debe estar habilitado (Settings > Resources > WSL Integration)

**Archivos:**
- `.env.development` debe tener line endings LF (no CRLF)
- Convertir si es necesario: En VS Code, click "CRLF" en la barra inferior y selecciona "LF"

### 🔍 Script de Validación

Antes de iniciar el proyecto, puedes validar tu configuración:

```bash
# Mac/Linux: Usar Makefile
make validate

# Windows: Script batch dedicado (recomendado)
validate.bat

# O manualmente con Python:
# Mac/Linux:
python3 scripts/validate_setup.py

# Windows PowerShell/CMD:
python scripts\validate_setup.py
```

El script verifica:
- ✓ Docker y Docker Compose instalados
- ✓ WSL2 activo (Windows - warning si no responde pero Docker funciona)
- ✓ Archivo `.env.development` presente y completo
- ✓ Import path consistente entre local y Docker
- ✓ Compatibilidad multiplataforma (sin platform hardcodeado)

**Nota Windows:** Si `make validate` da error, ejecuta directamente:
```powershell
python scripts\validate_setup.py
```

---

## 🐳 Levantar el Proyecto desde Cero

```bash
# Opcion 1 (recomendada): flujo automatizado completo
make bootstrap-zero

# Si el equipo es lento o red inestable, puedes ampliar reintentos:
make bootstrap-zero BOOTSTRAP_RETRIES=60 BOOTSTRAP_RETRY_SLEEP=3

# Opcion 2: paso a paso manual
# 0. (Recomendado) Validar configuración
make validate

# 1. Instalar dependencias localmente (opcional, útil para IDE)
poetry install

# 2. Iniciar contenedores
make build
make run

# 3. Migrar la base de datos
make db-upgrade

# 4. (Opcional) Seed de datos completos de prueba
make seed
# Esto carga: 1 empresa, 2 sucursales, 4 puntos emisión, 3 bodegas,
# 10 categorías, 19 productos con impuestos y stock

# Verificar datos cargados
make verify-seed

# 5. Ver la documentación Swagger
http://localhost:8000/docs
```

---

## 🌱 Datos de Prueba (Seed)

El sistema incluye un script completo de seed para poblar la base de datos con datos de prueba realistas:

```bash
make seed              # Carga datos completos
make verify-seed       # Verifica datos cargados
make verify-relations  # Verifica relaciones de productos
```

### Contenido del Seed

El seed carga una estructura completa de datos de prueba basada en el archivo `scripts/seed_data_structure.yaml`:

**Datos empresariales:**
- 1 empresa (OpenLatina - RUC: 0103523908001)
- 2 sucursales (Centro, Norte)
- 4 puntos de emisión (2 matriz, 2 sucursales)
- 3 bodegas (1 matriz, 2 sucursales)

**Catálogos:**
- 10 categorías (jerarquía: Tecnología → Computadoras/Periféricos → subcategorías)
- 12 atributos (Procesador, RAM, DPI, Conectividad, etc.)
- 5 casas comerciales (HP, Dell, Logitech, Razer, Sony)

**Proveedores:**
- 2 proveedores persona natural
- 2 proveedores sociedad (ImportaTech, GlobalDist)

**Productos (19 total):**
- 4 Laptops (HP Pavilion, Dell Inspiron, HP EliteBook, Dell Educación)
- 3 All-in-One (HP, Dell, HP Envy)
- 3 Mouse (Logitech MX Master, Razer DeathAdder, Logitech G305)
- 3 Teclados (Logitech MX Keys, Razer BlackWidow, HP K500F)
- 6 Audífonos: 3 Earbuds + 3 Diadema (Sony, Razer, Logitech, HP)

Cada producto incluye:
- Descripción detallada (campo `descripcion`)
- Código de barras único (campo `codigo_barras`)
- Precio de venta (PVP)
- Categoría asignada (solo nodos hoja)
- Impuestos aplicados (IVA 15%, IVA 0%, ICE según corresponda)
- Stock distribuido en las 3 bodegas
- Atributos informativos según categoría
- Casa comercial asociada

### Estructura del Seed

El sistema de seed se compone de:

1. **`scripts/seed_data_structure.yaml`** (643 líneas)
   - Archivo YAML declarativo con toda la estructura de datos
   - Fácil de modificar para personalizar datos de prueba
   - Incluye comentarios explicativos

2. **`scripts/seed_complete_data.py`** (571 líneas)
   - Script Python que lee el YAML y crea todas las entidades
   - Maneja dependencias y relaciones automáticamente
   - Evita duplicados (ejecutable múltiples veces)
   - Muestra progreso con indicadores ✓

3. **Scripts de verificación:**
   - `check_seed_data.py`: Resumen de tablas y primeros registros
   - `check_producto_relations.py`: Verifica relaciones completas de un producto

### Personalizar Datos

Para modificar los datos de prueba, edita `scripts/seed_data_structure.yaml`:

```yaml
# Ejemplo: Agregar un nuevo producto
productos:
  - nombre: "Mi Nuevo Producto"
    codigo_barras: "PROD-001"
    descripcion: "Descripción del producto"
    precio: 150.00
    tipo: "BIEN"
    casa_comercial: "HP"
    categorias: ["Laptop"]  # Solo categorías hoja
    impuestos: ["4"]  # Código SRI (4 = IVA 15%)
    bodegas:
      - codigo: "BOD-MATRIZ"
        cantidad: 10
```

Luego ejecuta `make seed` para aplicar los cambios.

## 🧾 Catálogo de Impuestos SRI

El sistema incluye el catálogo oficial de impuestos del SRI (Servicio de Rentas Internas de Ecuador) precargado mediante migraciones:

- **84 registros** de impuestos: 9 IVA + 75 ICE
- Cargados desde `conf/aux_impuesto_catalogo.json`
- Fecha de vigencia por defecto: `2023-02-01`

### Estructura de Impuestos

- `codigo_tipo_impuesto`: Código del tipo de impuesto según SRI (2=IVA, 3=ICE, 5=IRBPNR)
- `codigo_sri`: Código único de tarifa SRI
- `descripcion`: Descripción del impuesto
- **Restricción unique**: Combinación `(codigo_sri, descripcion)` permite códigos ICE repetidos con distintas descripciones

### Endpoint: `GET /api/v1/impuestos/catalogo`

- **Paginación**: `limit` (int) y `offset` (int)
- **Filtro por tipo**: `tipo_impuesto` opcional (`IVA`, `ICE`, `IRBPNR`)
- **Respuesta**:
  - `items`: Lista de impuestos con información completa
  - `meta`: `{ total, limit, offset, page, page_count }`

## 🛒 Productos e Impuestos

### Reglas de Negocio

- **IVA obligatorio**: Todos los productos deben tener exactamente un impuesto IVA
- **Máximo un impuesto por tipo**: Un producto puede tener máximo 1 IVA, 1 ICE, 1 IRBPNR
- **Reemplazo automático**: Asignar un nuevo impuesto del mismo tipo reemplaza el anterior
- **IVA no eliminable**: El IVA solo puede reemplazarse, no eliminarse directamente
- **Compatibilidad tipo**: Los impuestos validan compatibilidad con el tipo de producto (BIEN/SERVICIO)
- **Vigencia**: Solo se pueden asignar impuestos vigentes
- **Cantidad (inventario)**: Nuevo atributo `cantidad` (int). Se inicializa automáticamente en `0` y no lo envía el usuario en la creación/actualización del producto. Se incluye en las respuestas.
- **Proveedores (persona/sociedad)**: No se envían en creación/actualización de producto. Estas relaciones se crean automáticamente vía trigger después de ingresar una compra. Por defecto, las listas `proveedores_persona` y `proveedores_sociedad` estarán vacías hasta que haya compras asociadas.

### Endpoints de Productos

```
POST   /api/v1/productos                                    # Crear producto
GET    /api/v1/productos                                    # Listar productos (paginado)
GET    /api/v1/productos/{producto_id}                      # Detalle completo con impuestos
PUT    /api/v1/productos/{producto_id}                      # Actualizar producto
DELETE /api/v1/productos/{producto_id}                      # Eliminar (soft delete)
```

### Endpoints de Impuestos de Producto

```
GET    /api/v1/productos/{producto_id}/impuestos            # Listar impuestos del producto
POST   /api/v1/productos/{producto_id}/impuestos            # Asignar impuesto
       ?impuesto_catalogo_id=UUID&usuario_auditoria=str     # (reemplaza si existe mismo tipo)
DELETE /api/v1/productos/impuestos/{producto_impuesto_id}   # Eliminar (excepto IVA)
```

### Flujo de Creación de Producto

Al crear un producto mediante `POST /api/v1/productos`:
1. NO se especifican `impuesto_catalogo_ids` en el payload inicial
2. El producto se crea sin impuestos
3. Se asignan impuestos después mediante `POST /{producto_id}/impuestos`
4. El primer impuesto debe ser un IVA (obligatorio)
5. El campo `cantidad` se establece automáticamente en `0` y aparece en las respuestas del API.

---

## 🌐 Documentación Swagger

Disponible automáticamente al levantar el sistema en:

- [http://localhost:8000/docs](http://localhost:8000/docs)
- [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🧱 Migraciones Alembic

```bash
# Crear una nueva revisión basada en los modelos (desde dentro del contenedor)
docker compose --env-file .env.development exec -e ENVIRONMENT=development osiris-backend poetry run alembic revision --autogenerate -m "mensaje"
# O usar el alias:
make db-makemigration mensaje="descripción de la migración"

# Aplicar migraciones pendientes
make db-upgrade

# Revertir última migración
docker compose --env-file .env.development exec osiris-backend poetry run alembic downgrade -1

# Ver historial de migraciones
docker compose --env-file .env.development exec osiris-backend poetry run alembic history
```

⚠️ **Migraciones existentes:**
- `cec1e957113e`: Cambio de restricción única en `aux_impuesto_catalogo` (codigo_sri → codigo_sri + descripcion)
- `20f3d9f4a008`: Carga inicial de 84 registros del catálogo SRI desde JSON

---

## 📦 Librería de Facturación Electrónica (fe-ec)

Librería local en `lib/fe_ec-0.1.0-py3-none-any-3.whl`, instalada vía `pyproject.toml`:

```toml
[tool.poetry.dependencies]
fe-ec = { file = "lib/fe_ec-0.1.0-py3-none-any-3.whl" }
```

**Uso típico:**

```python
from fe_ec import GeneradorClaveAcceso, ManejadorXML

# Generar clave de acceso para factura electrónica
clave = GeneradorClaveAcceso.generar(
    fecha_emision="01/02/2024",
    tipo_comprobante="01",  # Factura
    ruc="1234567890001",
    ambiente="1",  # Pruebas
    serie="001001",
    numero_secuencial="000000001",
    codigo_numerico="12345678",
    tipo_emision="1"
)

# Generar XML firmado
xml_firmado = ManejadorXML.firmar_xml(
    xml_sin_firmar,
    ruta_certificado="conf/firma.p12",
    password_certificado="contraseña"
)
```

⚠️ **Nota:** La librería no está en PyPI, se distribuye como `.whl` local. Requiere certificados `.p12` válidos para firmar documentos electrónicos.

Para el gate de seguridad:
- El script `scripts/patch_feec_wheel_constraints.py` normaliza la restricción de `cryptography` del wheel local antes de ejecutar `poetry lock`.
- Esto evita conflictos de resolución con políticas de seguridad más estrictas del backend.

---

## ✅ Pruebas

El repositorio mantiene pruebas unitarias/integración y smoke tests. Se dividen en dos categorías:

### Pruebas Unitarias (tests/)

Incluyen validaciones de lógica, servicios y rutas con fixtures de base de datos:

```bash
make test
```

**Cobertura:**
- Validaciones (identificación, impuestos, productos)
- Servicios CRUD (cliente, empleado, empresa, proveedor)
- Repositorios (validación de duplicados, catálogo de impuestos)
- Utilidades (paginación, jerarquía de categorías)

✅ `make test` corre la suite completa en contenedor con smoke live habilitado (sin skips).

### Smoke Tests (tests/smoke/)

Validan integración completa contra sistema levantado:

```bash
# Smoke tests (incluye flujos E2E y validaciones de API)
make smoke

# Solo pruebas seguras para CI (listados)
make smoke-ci
```

**Archivos principales:**
- `test_all_endpoints.py`: Flujos empresa → sucursal → punto_emision
- `test_crud_smoke.py`: CRUD completo de endpoints principales
- `test_producto_crud_completo_smoke.py`: Creación de productos con impuestos/categorías/atributos
- `test_list_only.py`: Validación de listados (seguro para CI)
- `utils.py`: Retry automático, cliente HTTP, limpieza de recursos

⚠️ **Requisitos para smoke tests:**
- Sistema levantado (`make run`)
- Base de datos migrada (`make db-upgrade`)
- `.env.development` configurado
- Catálogo de impuestos cargado (84 registros SRI)
- Para ejecutar smoke "live" manualmente: `RUN_LIVE_SMOKE=true make smoke`

---

## 🔐 Seguridad

**Archivos sensibles protegidos:**
- `.env.*` → Excluido en `.gitignore` (nunca versionar credenciales)
- `conf/firma.p12` → Certificado digital (mantener fuera del repo)
- Contraseñas de BD y P12 → Usar secretos externos en producción

**Mejores prácticas:**
- En desarrollo: `.env.development` local (no versionado)
- En producción: Variables de entorno del sistema o secret managers (AWS Secrets Manager, HashiCorp Vault, etc.)
- Rotar certificados `.p12` según políticas de seguridad del SRI

---

## 📞 Contacto

**OpenLatina**
📱 0984228883
📱 0995767370

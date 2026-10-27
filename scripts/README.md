# Scripts de Utilidad

Este directorio contiene scripts de utilidad para gestionar datos en la base de datos del proyecto Osiris y validar la configuración del entorno.

## Scripts Disponibles

### audit_catalog_integrity.py

Preflight global de Categorias/Atributos, solo lectura. Detecta hermanos
duplicados incluyendo inactivos, atributos/codigos/asignaciones duplicados,
ciclos, padres invalidos, flags padre inconsistentes y problemas de clasificacion
o atributos obligatorios de productos. No fusiona, renombra ni actualiza filas.

```bash
ENVIRONMENT=development PYTHONPATH=src poetry run python scripts/audit_catalog_integrity.py --host 127.0.0.1 --port 5435 --summary
```

Sin `--summary` incluye nombres, IDs y rutas accionables; restringir ese reporte
a revision administrativa. Sale con 0 si no hay conflictos detectados, 1 si hay
bloqueos/esquema incompleto y 2 para argumentos invalidos. PostgreSQL se consulta
con una transaccion REPEATABLE READ y READ ONLY. No ejecuta migraciones ni seeds.

`--unit-candidates <archivo.json>` acepta un objeto explicito
`{"<atributo UUID>": "GIGABYTE"}` para informar el alcance de una anotacion
futura; no infiere ni asigna unidades y no valida el destino aun no desplegado.
Los defaults no cuentan como valores ya cargados y los remapeos pendientes no
satisfacen un obligatorio. El diagnostico reconoce buckets B3 por estructura;
no certifica por si solo la procedencia de auditoria de un bucket legacy.

Si existen conflictos, detener las migraciones dependientes y conciliar con
aprobacion administrativa. Un resultado limpio no sustituye las pruebas de
constraints, permisos, migraciones y concurrencia ni autoriza activar la FK de
Producto; ese corte sigue reservado a la entrega 7.

### reconcile_test_catalog.py

Conciliacion explicita para datos de prueba autorizados. Conserva IDs y relaciones;
renombra categorias inactivas historicamente duplicadas y recalcula es_padre desde
hijos activos. No elimina filas, no aplica migraciones ni elige entre duplicados
activos. Cada cambio registra auditoria antes/despues en la misma transaccion.

```bash
# Previsualizar sin escrituras y revisar cambios/plan_hash:
ENVIRONMENT=development PYTHONPATH=src poetry run python scripts/reconcile_test_catalog.py --host 127.0.0.1 --port 5435
# Solo con autorizacion para datos de prueba y el hash revisado:
ENVIRONMENT=development PYTHONPATH=src poetry run python scripts/reconcile_test_catalog.py --host 127.0.0.1 --port 5435 --apply-test-data --expected-plan-hash <hash-revisado>
```

La aplicacion exige hash vigente, actor de mantenimiento y entorno development/test;
adquiere locks, revalida el plan y comprueba el preflight antes de confirmar.
Un fallo de auditoria/postflight hace rollback. Un segundo plan limpio no propone
cambios. Esta herramienta no autoriza reconciliaciones de datos productivos.

### audit_directory_integrity.py

Preflight de solo lectura antes de las migraciones de identidad del Directorio.
Incluye activos e inactivos, colisiones normalizadas de identificacion, username,
nombre de TipoCliente y RUC, duplicados de roles por Persona y referencias
historicas detectadas por foreign keys. No modifica ni fusiona registros.

```bash
PYTHONPATH=src poetry run python scripts/audit_directory_integrity.py --summary
# En macOS, con el puerto publicado del compose actual:
PYTHONPATH=src poetry run python scripts/audit_directory_integrity.py --host 127.0.0.1 --port 5435 --summary
```

Sin `--summary`, muestra claves e IDs para revision administrativa. Tratar ese
reporte como datos personales: no publicarlo en logs abiertos. Sale con codigo 1
si hay conflictos y con 0 si las claves estan libres de colisiones. Las entradas
en `requieren_normalizacion` no autorizan modificar datos automaticamente.

Si hay conflictos: detener el despliegue, respaldar la base, revisar todos los
registros y referencias (incluidos historicos), obtener aprobacion administrativa
de la correccion y repetir el preflight. No borrar filas, cambiar FKs ni fusionar
identidades solo para satisfacer un constraint. La revision Alembic vuelve a
comprobar las colisiones antes de crear cualquier indice.

### 0. validate_setup.py / validate_setup.sh

**Propósito**: Validar la configuración del entorno de desarrollo antes de ejecutar el proyecto (compatible Mac/Windows/Linux).

**Uso:**

```bash
# Desde Makefile (recomendado - multiplataforma)
make validate

# O manualmente con Python:
# Mac/Linux:
python3 scripts/validate_setup.py

# Windows PowerShell:
python scripts/validate_setup.py

# Linux/Mac con Bash (alternativa ligera):
bash scripts/validate_setup.sh
```

**Validaciones que realiza**:

- ✓ Sistema operativo detectado (Mac/Windows/Linux)
- ✓ Docker instalado y corriendo
- ✓ Docker Compose disponible (plugin moderno o legacy)
- ✓ WSL2 activo (solo en Windows)
- ✓ Archivo `.env.development` existe y completo
- ✓ Variables de entorno requeridas presentes
- ✓ Line endings correctos en `.env` (LF no CRLF en Windows)
- ✓ Archivos del proyecto presentes (pyproject.toml, Dockerfile, etc.)
- ✓ Import path consistente entre local y Docker (sin PYTHONPATH manual)
- ✓ CMD usa `osiris.main:app` (no `src.osiris.main:app`)
- ✓ docker-compose.yml sin `platform: linux/arm64` (multiplataforma)

**Salida**:

- Exit code 0: Entorno listo ✅
- Exit code 1: Hay errores que corregir ❌

**Cuándo ejecutarlo**:

- Primera vez que configuras el proyecto
- Después de cambiar de sistema operativo
- Si encuentras errores 500 o ModuleNotFoundError
- Antes de reportar un bug

---

### 1. seed_sample_product.py

**Propósito**: Poblar la base de datos con un producto de ejemplo completo para demostración y testing manual.

**Uso**:

```bash
# Opción 1: Usando Makefile
make seed

# Opción 2: Directamente con Python
docker compose exec osiris-backend poetry run python scripts/seed_sample_product.py
```

**Qué crea**:

- 1 producto: "Laptop Gamer X Pro" (tipo=BIEN, pvp=2999.00)
- 1 casa comercial: "Casa ACME"
- Jerarquía de categorías: Tecnología → Computadoras → Laptop
- 2 proveedores persona: Juan Gómez Importaciones, Tecnologías Pepe
- 2 proveedores sociedad: Tipti S.A., ABC Comercial S.A.
- 3 atributos: color_principal=negro, memoria_ram=32GB, tamano_pantalla=15.6
- 2 impuestos: IVA 15%, ICE 10%

**Características**:

- Todos los registros tienen `usuario_auditoria = 'seed'`
- Los datos son idempotentes: ejecutar múltiples veces no crea duplicados
- Imprime el contrato JSON completo del producto al finalizar

---

### 2. cleanup_test_data.py

**Propósito**: Eliminar físicamente (hard delete) todos los datos creados por tests, preservando los datos del seed.

**Uso**:

```bash
# Opción 1: Usando Makefile (recomendado)
make cleanup-test-data

# Opción 2: Directamente con Python
docker compose exec osiris-backend poetry run python scripts/cleanup_test_data.py
```

**Qué elimina**:

- Todos los registros con `usuario_auditoria IN ('smoke_test', 'ci', 'test')`
- Elimina en el orden correcto respetando foreign keys:
  1. Relaciones de productos (tablas bridge)
  2. Productos
  3. Atributos
  4. Proveedores
  5. Casas comerciales
  6. Categorías
  7. Impuestos de test
  8. Clientes, empleados, usuarios
  9. Personas
  10. Roles, tipos de cliente
  11. Puntos de emisión, sucursales, empresas

**Qué preserva**:

- ✅ Todos los datos del seed (`usuario_auditoria = 'seed'`)
- ✅ Datos auxiliares del sistema (tipo_contribuyente, etc.)

**Cuándo usar**:

- Después de ejecutar la suite de tests completa
- Para limpiar la base de datos sin perder el seed
- Antes de hacer pruebas manuales con datos limpios

**Salida del script**:

```
🧹 Iniciando limpieza de datos de test...
   Usuarios de test: ('smoke_test', 'ci', 'test')

📊 Estado ANTES:
   - Productos test: 13
   - Productos seed: 1
   - Total: 14

🗑️  Eliminando relaciones de productos...
   - tbl_producto_categoria: 1 registros
   - tbl_producto_proveedor_persona: 1 registros
   ...

📊 Estado DESPUÉS:
   - Productos test: 0
   - Productos seed: 1
   - Total: 1

✅ Limpieza completada exitosamente!
   Los datos del seed han sido preservados.
```

---

## Diferencia entre Soft Delete y Hard Delete

### Soft Delete (comportamiento por defecto)

- Los registros se marcan como `activo = false`
- Permanecen en la base de datos para auditoría
- Los endpoints filtran por `activo = true` para no mostrarlos
- **Usado por**: `cleanup_product_scenario()` en tests (por defecto)
- **Variable de entorno**: `TEST_HARD_DELETE=false` (o no definida)

### Hard Delete (eliminación física)

- Los registros se eliminan físicamente de la base de datos
- Ideal para limpiar completamente después de tests
- **Usado por**:
  - `scripts/cleanup_test_data.py` (siempre)
  - `cleanup_product_scenario()` cuando `TEST_HARD_DELETE=true`
- **Variable de entorno**: `TEST_HARD_DELETE=true`

### Cómo activar Hard Delete en smoke tests

```bash
# Ejecutar smoke tests con hard delete
docker compose exec osiris-backend bash -c "TEST_HARD_DELETE=true poetry run pytest tests/smoke/ -v"

# O exportar la variable antes
export TEST_HARD_DELETE=true
make test
```

---

## Comandos del Makefile

```bash
# Sembrar datos de ejemplo
make seed

# Limpiar datos de test (hard delete)
make cleanup-test-data

# Ejecutar tests
make test

# Ejecutar tests + limpiar en un solo comando
make test && make cleanup-test-data
```

---

## Notas Importantes

1. **Siempre verifica el entorno**: Los scripts usan la configuración definida en `.env.development` por defecto.

2. **Orden de ejecución recomendado**:

   ```bash
   make seed                    # Poblar datos iniciales
   make test                    # Ejecutar suite de tests
   make cleanup-test-data       # Limpiar datos de test
   ```

3. **Cleanup en smoke tests**:
   - Tests de **productos** usan `cleanup_product_scenario()` y limpian automáticamente
   - Tests **CRUD generales** (roles, clientes, empresas, etc.) **NO limpian automáticamente**
   - Se recomienda ejecutar `make cleanup-test-data` después de la suite completa

4. **Hard delete vs Soft delete en tests**:
   - Por defecto, los tests usan **soft delete** (activo=false)
   - Para usar **hard delete**, exporta `TEST_HARD_DELETE=true` antes de ejecutar los tests
   - El hard delete elimina físicamente los registros de la BD

5. **Seguridad**: El script `cleanup_test_data.py` **NUNCA** elimina datos del seed. Usa transacciones para garantizar atomicidad.

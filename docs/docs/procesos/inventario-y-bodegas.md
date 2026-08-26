---
id: procesos-inventario-y-bodegas
title: "03. Inventario y Bodegas"
sidebar_position: 4
---

# 03. Inventario y Bodegas

## CU020: Construir catálogo de inventario

**Actores:** Encargado de Almacén, Administrador.

**Descripción:** Definir estructura de productos con categorías, atributos e impuestos.

**Precondiciones:**

- Catálogo SRI de impuestos disponible.
- Usuario con permisos de inventario.

**Flujo de Eventos Básico:**

1. Crear categorías y subcategorías.
2. Crear atributos (tipo de dato correcto).
3. Asociar atributos a categorías.
4. Crear producto.
5. Asignar categorías al producto.
6. Asignar impuestos al producto.

**Flujos Alternativos:**

- Atributo no aplicable a categoría: operación rechazada.
- Configuración tributaria inválida: operación rechazada.

**Postcondiciones:**

- Producto listo para asignación a bodegas y operación comercial.

**APIs involucradas:**

- `POST /api/v1/categorias` ([doc API](../api/inventario/bloques-construccion))
- `POST /api/v1/atributos` ([doc API](../api/inventario/bloques-construccion))
- `POST /api/v1/categorias-atributos` ([doc API](../api/inventario/bloques-construccion))
- `POST /api/v1/productos` ([doc API](../api/inventario/producto-crud-base))
- `PUT /api/v1/productos/{producto_id}/atributos` ([doc API](../api/inventario/producto-atributos-impuestos-bodegas))
- `POST /api/v1/productos/{producto_id}/impuestos` ([doc API](../api/inventario/producto-atributos-impuestos-bodegas))

---

## CU021: Configurar bodegas operativas

**Actores:** Encargado de Almacén, Administrador.

**Descripción:** Crear bodegas activas por empresa/sucursal para controlar stock físico.

**Precondiciones:**

- Empresa activa y, de ser el caso, sucursal definida.

**Flujo de Eventos Básico:**

1. Registrar bodega con código y nombre.
2. Marcar estado activo.
3. Validar disponibilidad en asignación de productos.

**Flujos Alternativos:**

- Código duplicado por ámbito: el sistema rechaza.

**Postcondiciones:**

- Bodega disponible para stock y movimientos.

**APIs involucradas:**

- `POST /api/v1/bodegas` ([doc API](../api/inventario/casa-comercial-bodega))
- `GET /api/v1/bodegas` ([doc API](../api/inventario/casa-comercial-bodega))

---

## CU022: Asignar producto a bodega y cargar stock inicial

**Actores:** Encargado de Almacén.

**Descripción:** Vincular productos a bodegas activas y definir cantidades iniciales.

**Precondiciones:**

- Producto activo.
- Bodega activa.

**Flujo de Eventos Básico:**

1. El actor selecciona producto y bodega destino.
2. Registra cantidad inicial.
3. Guarda asignación producto-bodega.
4. Consulta stock disponible por producto/bodega.

**Flujos Alternativos:**

- Producto servicio con stock > 0: rechazo.
- Producto sin fracciones con cantidad decimal: rechazo.

**Postcondiciones:**

- Stock disponible listo para compras/ventas.

**APIs involucradas:**

- `POST /api/v1/productos/{producto_id}/bodegas/{bodega_id}` ([doc API](../api/inventario/producto-atributos-impuestos-bodegas))
- `PUT /api/v1/productos/{producto_id}/bodegas/{bodega_id}` ([doc API](../api/inventario/producto-atributos-impuestos-bodegas))
- `GET /api/v1/inventarios/stock-disponible` ([doc API](../api/inventario/producto-atributos-impuestos-bodegas))

---

## CU023: Operar movimientos de inventario (ingreso, egreso, transferencia, ajuste)

**Actores:** Encargado de Almacén, Supervisor.

**Descripción:** Ejecutar movimientos con control de concurrencia, anti-negativos y costo promedio.

**Precondiciones:**

- Bodega y producto activos.
- Existencias disponibles para egresos/transferencias.

**Flujo de Eventos Básico:**

1. Crear movimiento en borrador.
2. Confirmar movimiento para aplicar impacto de stock.
3. En transferencias, ejecutar egreso origen + ingreso destino de forma atómica.
4. Consultar kardex operativo y valoración.

**Flujos Alternativos:**

- Intento de egreso con saldo insuficiente: rollback y rechazo.
- Ajuste sin motivo: rechazo.

**Postcondiciones:**

- Stock actualizado y trazabilidad en kardex.

**APIs involucradas:**

- `POST /api/v1/inventarios/movimientos` ([doc API](../api/inventario/casa-comercial-bodega))
- `POST /api/v1/inventarios/movimientos/{movimiento_id}/confirmar` ([doc API](../api/inventario/casa-comercial-bodega))
- `POST /api/v1/inventarios/transferencias` ([doc API](../api/inventario/producto-atributos-impuestos-bodegas))
- `GET /api/v1/inventarios/kardex` ([doc API](../api/inventario/producto-atributos-impuestos-bodegas))
- `GET /api/v1/inventarios/valoracion` ([doc API](../api/inventario/producto-atributos-impuestos-bodegas))

---

## CU024: Baja lógica de bodega sin romper integridad

**Actores:** Administrador, Encargado de Almacén.

**Descripción:** Desactivar bodega únicamente cuando no tenga productos activos ni stock remanente.

**Precondiciones:**

- Bodega seleccionada.

**Flujo de Eventos Básico:**

1. El actor solicita eliminación lógica de bodega.
2. El sistema valida asignaciones activas y stock materializado.
3. Si cumple reglas, desactiva bodega.

**Flujos Alternativos:**

- Si existe stock o asignación activa, sistema rechaza operación.

**Postcondiciones:**

- Bodega desactivada sin afectar trazabilidad histórica.

**APIs involucradas:**

- `DELETE /api/v1/bodegas/{id}` ([doc API](../api/inventario/casa-comercial-bodega))

---

# Inventario de rutas y consumidores

Estado observado el 2026-10-04. Este inventario no depreca rutas; registra el contrato antes de cualquier retiro.

## Contratos API canónicos

| Dominio | Prefijos actuales | Consumidor frontend observado |
| --- | --- | --- |
| Organización y acceso | `/api/v1/empresas`, `/sucursales`, `/puntos-emision`, `/usuarios`, `/roles`, `/personas` | `features/empresa`, `features/personas`, `ConfiguracionOperativaPage`, `AuthContext` |
| Catálogo e inventario | `/api/v1/productos`, `/categorias`, `/categorias-atributos`, `/atributos`, `/impuestos`, `/bodegas`, `/inventarios` | `ProductosPage`, `CategoriasPage`, `features/productos/api`, `BodegasPage`, páginas de inventario |
| Compras y CxP | `/api/v1/compras`, `/cxp`, `/retenciones` | `features/compras/api`, `ComprasPage`, `CuentasPorPagarPage`, `RetencionesPage` |
| Ventas y CxC | `/api/v1/ventas`, `/cxc`, `/retenciones-recibidas` | `features/ventas/api`, `VentasPage`, páginas de cartera |
| Documentos electrónicos | `/api/v1/fe`, `/documentos`, `/tipos-contribuyente` | `DocumentosSRIPage`, `features/ventas/api` |
| Reportes e impresión | `/api/v1/reportes`, `/impresion` | páginas `Reporte*`, `ReportsPage`, páginas de impresión |

Los prefijos son los registrados por los routers incluidos en `src/osiris/main.py`. Compras y ventas registran varios routers por dominio (`compras`/`cxp`/`retenciones` y `ventas`/`cxc`/`retenciones-recibidas`); no son duplicados legacy.

## Aliases de interfaz

El frontend conserva redirects en `src/lib/route-redirects.ts` y casos especiales en `getSpanishRouteRedirect`:

| Ruta antigua | Destino actual | Consumidor o riesgo |
| --- | --- | --- |
| `/login`, `/change-password` | `/iniciar-sesion`, `/cambiar-contrasena` | enlaces de acceso externos y bookmarks |
| `/inventory/*` | `/inventario/*` | links guardados de movimientos |
| `/categories*` | `/categorias*` | bookmarks; conservar parámetros/rutas compatibles |
| `/products`, `/products/new`, `/products/:id`, `/products/:id/edit` | `/productos` con intención en query | bookmarks y enlaces de productos |
| `/customers`, `/suppliers` | `/clientes`, `/proveedores` | links antiguos; el flujo consolidado es `/personas` |
| `/catalogs`, `/reports*`, `/audit` | `/catalogos`, `/reportes/resumen*`, `/auditoria` | bookmarks del MVP |
| `/admin/company`, `/admin/users`, `/admin/params` | `/empresa`, `/admin/usuarios`, `/admin/parametros` | enlaces administrativos |
| `/inventario/bajas*`, `/inventario/ajustes*` | `/inventario/egresos*`, `/inventario/ingresos*` | compatibilidad entre acciones antiguas y movimientos tipados |
| `/atributos`, `/categorias-atributos` | `/categorias` | configuración integrada por categoría |

## Retiro seguro

- No se encontraron routers backend alternos fuera de los prefijos versionados listados; la documentación de cobertura contabiliza 176 endpoints bajo `/api/v1`.
- Antes de retirar un redirect, buscar consumidores internos, actualizar bookmarks/documentación y revisar telemetría de uso externo durante una ventana acordada.
- Los aliases de producto e inventario conservan intención o traducen una acción; no reemplazarlos por un redirect genérico sin probar esos parámetros.
- `/atributos` y `/categorias-atributos` son redirects actuales; la creación canónica exige `categoria_id` y la asociación se persiste en la misma transacción.
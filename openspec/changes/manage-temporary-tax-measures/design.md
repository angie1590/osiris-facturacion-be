## Context

El catálogo SRI y `ProductoImpuesto` definen las tarifas regulares. `VentaService` calcula venta e impuestos al construir `VentaCreate`, y `VentaDetalleImpuesto` congela actualmente código, tarifa, base y valor. No hay clasificación de actividades turísticas ni productos cerveceros, y el cálculo MVP interpreta todo ICE como porcentaje y admite un único ICE por línea.

Una medida excepcional no puede inferir su elegibilidad desde texto libre, RUC o fechas solamente. Las imágenes tampoco bastan para establecer códigos de porcentaje, reglas de redondeo, unidades de alcohol puro o requisitos formales del contribuyente; esos datos deben verificarse con la resolución/SRI antes de activar una medida.

## Goals / Non-Goals

**Goals:**
- Administrar la medida tributaria por empresa, vigencia inclusiva, tipo y componente del impuesto, tarifa y código SRI confirmados, con auditoría y activación explícita.
- Declarar alcance por productos específicos; para componentes específicos ICE, registrar conversión de unidad por producto (por ejemplo, litros gravables por unidad vendida).
- Resolver medida vigente en backend antes de calcular una venta, aplicar solo a la empresa/producto/componente coincidente y rechazar configuraciones ambiguas.
- Congelar identificador/código de medida, código SRI, tarifa, unidad/base y valor calculado en el snapshot de la línea.
- Permitir administrar medidas desde el frontend usando patrones y componentes compartidos existentes.

**Non-Goals:**
- Extraer automáticamente condiciones desde PDF/decretos o determinar elegibilidad legal.
- Precargar o deducir códigos SRI/tarifas de las imágenes; el código exacto debe ser confirmado por un administrador contra la publicación oficial del SRI.
- Cambiar compras, retenciones, catálogo tributario base, contabilidad o documentos históricos.
- Clasificar automáticamente empresas como turísticas ni productos como cerveza artesanal/industrial.

## Decisions

1. **Medida por empresa con alcance explícito producto-componente.** Cada medida pertenece a una empresa y contiene una o más asignaciones de productos. Cada asignación apunta al componente de impuesto afectado; un objetivo ICE específico declara su factor de conversión a la unidad tributaria. Se elige sobre una etiqueta textual o una bandera general de empresa para evitar afectar ventas no elegibles. Otra alternativa considerada fue aplicar globalmente por fecha y categoría; se descarta porque hoy el producto no posee clasificación regulatoria confiable.
2. **Fechas `date`, inclusivas, evaluadas con `fecha_emision`.** Evita diferencias de zona horaria y permite facturación retroactiva solo cuando el flujo existente la permita. El reloj del servidor no decide si un comprobante fechado pertenece al periodo.
3. **Componentes tributarios explícitos.** IVA sigue siendo porcentual. ICE puede tener componentes `AD_VALOREM` porcentuales y `ESPECIFICO` por unidad gravable; una línea puede contener ambos. No se reduce una tarifa específica a un porcentaje ni se mezcla con el catálogo regular.
4. **Activación validada y sin precedencia implícita.** Solo una medida `ACTIVA`, con periodo, código SRI, tarifa y objetivos completos puede participar. Se rechazan solapamientos para la misma empresa, producto e impuesto/componente. No se resuelve conflicto por “última actualización”.
5. **Snapshot de venta autosuficiente.** El snapshot añade componente/unidad y referencia/código de la medida, pero sus importes siguen siendo valores congelados. Desactivar, modificar o vencer una medida no reescribe ventas autorizadas.
6. **Cambios de venta centralizados en backend.** Tanto la venta manual como la venta hidratada desde productos pasan por un único resolver antes de calcular totales, IVA sobre ICE, cartera e integración FE. El cliente no puede enviar la tarifa final ni un ID de medida para forzar una excepción.
7. **Administración UI independiente del catálogo base.** Una pantalla administrativa permite crear/revisar/activar y seleccionar empresa/productos; solo expone los códigos y valores recibidos/configurados por mantenedores. La lista muestra fechas, estado calculado, componente, código y alcance legibles.

## Risks / Trade-offs

- [Código SRI incorrecto o publicado con posterioridad] → La medida inicia en borrador y no puede activarse sin código confirmado; incluir referencia documental/acto oficial y usuario auditor.
- [Conversión ICE específica equivocada] → Exigir unidad compatible y factor positivo explícito por producto; probar con casos de unidades parciales (botella/litro) y no aplicar la medida si falta.
- [Importes FE incompatibles con estructura/código esperado por SRI] → Validar XML de factura con XSD y tests del mapper; no autorizar en modo mock en producción.
- [Un cambio altera líneas históricas] → El resolver solo se ejecuta al crear/registrar venta; snapshots son inmutables y las medidas no tienen operación de recálculo masivo.
- [Overlapping configurations across users] → Restricción de solapamiento en servicio/transacción y auditoría de activación; no asumir locking optimista sin tests de concurrencia.
- [Permisos de administración insuficientes] → Reutilizar autorización administrativa existente; fallo cerrado para cualquier rol no autorizado.

## Migration Plan

1. Añadir tablas de medida y alcance, estado/código oficial y campos de componente/unidad al snapshot ICE/IVA mediante Alembic.
2. Migrar snapshots existentes como componente porcentual regular con referencia temporal nula; no modificar tarifa ni totales históricos.
3. Desplegar backend con medidas inactivas por defecto y aplicar migración antes del frontend.
4. Desplegar frontend administrativo; operadores cargan y verifican medidas antes de activarlas.
5. Rollback: desactivar medidas antes de revertir; conservar backups de ventas. El downgrade elimina tablas/campos nuevos solo si no existen datos temporales que deban retenerse; no se ofrece downgrade destructivo automáticamente en producción.

## Open Questions

- ¿Qué publicación oficial/SRI confirma el código de porcentaje IVA 8% y códigos y modo de cálculo para cada componente ICE durante esos periodos?
- Para el ICE específico, ¿el volumen imponible se deriva de litros de bebida o litros de alcohol puro, y dónde se obtiene el porcentaje alcohólico por SKU? La imagen usa “litro de alcohol puro”, por lo que el factor posiblemente necesita capacidad × graduación alcohólica, no solo capacidad.
- ¿Qué perfiles actuales están autorizados para crear/activar medidas tributarias? El cambio reutilizará la autorización administrativa existente hasta acordar un permiso más granular.

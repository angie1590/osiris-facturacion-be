## 1. Persistencia y dominio

- [x] 1.1 Añadir entidades para medidas temporales por empresa y objetivos por producto/componente, con referencia legal, vigencia, código SRI confirmado, estado, base de cálculo y factor por producto para unidades específicas.
- [x] 1.2 Extender entrada/snapshot tributario para diferenciar componentes porcentuales y específicos ICE, preservar compatibilidad de registros históricos y permitir más de un componente ICE por detalle.
- [x] 1.3 Crear migración Alembic reversible que preserve snapshots existentes como porcentuales regulares y no precargue reglas/códigos excepcionales.
- [x] 1.4 Implementar validaciones de activación, productos compatibles, fechas inclusivas, referencia oficial, conversión y conflictos de solapamiento; registrar auditoría y fallo cerrado.

## 2. API administrativa

- [x] 2.1 Añadir schemas, servicio y rutas CRUD/paginación para listar, crear, editar, activar y desactivar medidas con autorización administrativa existente.
- [x] 2.2 Añadir pruebas de permisos, atomicidad, invalidaciones, medidas incompletas y solapamiento para endpoints y servicio.

## 3. Evaluación y snapshot de ventas

- [x] 3.1 Resolver medidas por empresa, fecha de emisión, producto, impuesto y componente dentro del backend para ventas manuales e hidratadas desde productos; ignorar cualquier tarifa temporal suministrada por el cliente.
- [x] 3.2 Calcular IVA porcentual y componentes ICE ad valorem/específicos, incluidos factores de unidad, antes de IVA/totales/cartera, preservando reglas actuales cuando no aplica medida.
- [x] 3.3 Persistir referencia y valores efectivos en snapshots e integrar múltiples componentes con mapper XML/FE-EC sin alterar comprobantes previos.
- [x] 3.4 Añadir regresiones para fechas límite inclusivas, empresa/producto ajenos, tasas normales fuera de alcance, IVA sobre ICE, cálculo ICE específico y estabilidad histórica tras modificar medida.

## 4. Administración frontend

- [x] 4.1 Añadir tipos/API/hooks y una pantalla administrativa protegida para listar, buscar, crear y editar medidas, usando nombres de empresa/producto y componentes compartidos; incluir alcance por categoría y todos los productos.
- [x] 4.2 Implementar activación/desactivación con revisión de referencia/códigos/unidades, estados de carga/error/vacío, errores de solapamiento y paginación del selector de productos.
- [x] 4.3 Añadir pruebas de recorridos clave, búsqueda, selección masiva, paginación y rechazo de activación, y validar build/lint.

## 5. Documentación y verificación

- [x] 5.1 Documentar API, operación, fuentes oficiales requeridas, códigos pendientes de verificación y procedimiento de desactivación/rollback.
- [x] 5.2 Ejecutar suite backend, Ruff y MyPy sobre el dominio nuevo; ejecutar suite frontend, ESLint y build; corregir regresiones y verificar Alembic history.

Nota: MyPy específico de `medidas_temporales` pasa. MyPy ampliado a módulos existentes de ventas/mapper reporta errores de tipado ya distribuidos en código previo, incluidos imports FE-EC y esquemas con `computed_field`; no se hizo una refactorización de alcance mayor para este cambio.

## 1. Series y modelo de punto

- [x] 1.1 Añadir modalidad física/electrónica inmutable al punto y formalizar el campo de secuencia inicial como próximo número a emitir.
- [x] 1.2 Crear migración Alembic con backfill desde modalidad de empresa, ajuste seguro de contadores legacy y unicidad por empresa/punto/número.
- [x] 1.3 Completar pruebas de formato exacto, inicial 1/personalizado, contadores por punto y rango de nueve dígitos.

## 2. Asignación transaccional

- [x] 2.1 Quitar asignación de secuencial de creación de borrador y asignarlo al emitir dentro de la transacción de inventario, CxC y cola FE.
- [x] 2.2 Convertir el endpoint separado “siguiente” en preview no consumidor; impedir ajustes manuales que salten/reutilicen números después del primer documento.
- [x] 2.3 Validar modalidad del punto frente a emisión efectiva y exigir una nueva serie al cambiar físico/electrónico.
- [x] 2.4 Probar rollback sin huecos, concurrencia/row lock, duplicados, overflow, borradores y restricciones de modalidad.

## 3. Configuración frontend

- [x] 3.1 Añadir modalidad al alta de punto, mostrar formato completo y próximo número, y retirar ajuste manual inseguro en puntos usados.
- [x] 3.2 Explicar creación de una serie/punto nuevo al cambiar modalidad y cubrir el flujo en pruebas frontend.

## 4. Documentación y validación

- [x] 4.1 Documentar semántica del inicial, correlatividad, preview, series legacy y migración a electrónico.
- [x] 4.2 Ejecutar suite backend/frontend, Ruff, Mypy focalizado, ESLint, build y migración SQLite; verificar historial Alembic.

> Validación: backend 450 passed/1 skipped; frontend 71 passed; Ruff, ESLint, build, migración SQLite y Alembic head correctos. MyPy focalizado ejecutado, pero conserva diagnósticos strict preexistentes en las abstracciones SQLModel/BaseService/Repository y servicios compartidos.

# Evidence: manage-reversible-attribute-lifecycle

Fecha: 2026-10-27. Complementa las tareas históricas pendientes con cobertura identificable, sin alterar otros cambios OpenSpec.

| Tarea | Evidencia |
|---|---|
| BE 3.4 | `tests/test_atributo_conversion_remap.py::test_legacy_inactive_attribute_cannot_be_reactivated_without_snapshot` comprueba 409 y no-reactivación parcial. `tests/test_atributo_configuracion.py` prueba baja/reversión y constata que no hay escrituras en tablas de compra, venta, impuestos, bodega o movimientos ni cambio de cantidad/categoría del producto. |
| BE 4.1 | `tests/test_atributo_configuracion.py::test_attribute_put_updates_type_specific_fields_without_replacing_identity` cubre string, integer, decimal, boolean, date, select y catalog; `test_attribute_put_rejects_duplicate_name_without_changing_identity_or_mapping` verifica 409 sin mutación. |
| BE 4.5 | `tests/test_attribute_lifecycle_migration.py` cubre SQLite Core y PostgreSQL en schema aleatorio: upgrade no destructivo, downgrade bloqueado con snapshot no revertido, permitido tras revertirlo y preservación de Atributo. PostgreSQL: 2 tests passed; schema eliminado en finally. |
| Suite | Suite BE: 1276 passed, 77 skipped, 0 failed. Ruff y mypy: limpios. |
Módulo: Inventario / Categoría

Semántica y reglas de negocio

- Una categoría puede actuar como padre y/o como hija al mismo tiempo.
  Ejemplo válido: Tecnología -> Computadoras -> Laptop. Aquí "Computadoras" es hija de "Tecnología" y padre de "Laptop".

- Campos relevantes:
  - `nombre` (string): nombre de la categoría.
  - `es_padre` (bool): indica si la categoría se considera contenedora de otras (no obliga a que `parent_id` sea nulo).
  - `parent_id` (UUID | null): referencia a otra categoría que actúa como padre de esta.

- Reglas de validación implementadas:
  - `parent_id` es opcional. Si se provee, se valida que exista y (si aplica) esté activo.
  - Se evita la autorreferencia: `parent_id` no puede ser el mismo `id` del registro.
  - Se evita la creación de ciclos en la jerarquía: no se permite establecer como padre a uno de sus propios descendientes (A -> B -> A).

Notas de implementación

- La validación de existencia y estado de `parent_id` se delega a `_check_fk_active_and_exists` del `BaseService`.
- La detección de ciclos se realiza por DFS descendente partiendo del nodo actual; si el `target_parent_id` aparece entre sus descendientes, la actualización falla con HTTP 400.

Pruebas

- Hay tests unitarios que cubren:
  - Validación de `parent_id` y FK.
  - Prevención de autorreferencia y ciclos.
  - Comportamiento de `update` y creación con `parent_id`.

Si cambias la semántica (por ejemplo: hacer que `es_padre` y `parent_id` sean mutuamente exclusivos), actualiza también `service.py` y los tests bajo `tests/test_categoria.py` y `tests/test_categoria_service.py`.

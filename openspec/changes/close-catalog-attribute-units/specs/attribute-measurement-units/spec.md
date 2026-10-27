## ADDED Requirements

### Requirement: Units are global independently reusable catalog records
Unidad SHALL contain UUID, codigo, nombre, simbolo, magnitud_codigo, es_sistema, activo and audit fields. Codigo SHALL be case-insensitively unique; simbolo SHALL be exactly case-sensitively unique. Unit APIs SHALL support search, magnitude, active/history and pagination filters with effective UNIDADES permissions.

#### Scenario: Symbols differ only by case
- **WHEN** MB and Mb are created with distinct valid codes
- **THEN** they SHALL remain distinct symbols without case normalization; a second exact MB SHALL return UNIT_DUPLICATE_SYMBOL.

#### Scenario: Duplicate unit code differs only by case
- **WHEN** a request duplicates an existing code ignoring case
- **THEN** it SHALL return UNIT_DUPLICATE_CODE with no writes.

### Requirement: System unit seeds are permanent and protected
Alembic SHALL seed the 22 units listed in the v2 document and design, including UNIDAD/u/COUNT. Seeds SHALL have stable identities and be idempotent. API clients SHALL NOT change, deactivate or remove system units; controlled future migrations SHALL own corrections.

#### Scenario: Actor attempts to modify the system Unidad
- **WHEN** any API request edits or deactivates UNIDAD
- **THEN** backend SHALL return UNIT_PROTECTED and preserve the seed.

### Requirement: Unit semantics are fixed on the numeric canonical attribute
Atributo.unidad_id SHALL be an optional FK to an active unit, supported only for integer and decimal. No usa_unidad persistence flag SHALL exist. Unit SHALL NOT vary by Product or category. Typed values and defaults SHALL exclude symbols. No commercial Product unit or conversion SHALL be implemented.

#### Scenario: Numeric RAM value uses GB
- **WHEN** RAM with fixed GB receives value 16
- **THEN** EAV/default SHALL retain only numeric 16 and API SHALL return the unit separately.

#### Scenario: Non-numeric SKU is assigned a unit
- **WHEN** a string/select/catalog/boolean/date attribute receives non-null unidad_id
- **THEN** the request SHALL return ATTRIBUTE_UNIT_INVALID_TYPE without modifying the attribute.

#### Scenario: Selected unit is inactive
- **WHEN** a definition references an inactive unit
- **THEN** UNIT_INACTIVE SHALL be returned with no writes.

### Requirement: First unit annotation of existing values requires confirmation
When there is no current or relevant historical data, adding/changing/removing a unit SHALL be allowed after validation. With existing values, null-to-unit SHALL require read-only preview, matching precondicion_preview and confirmar_anotacion_unidad=true. Counts SHALL cover affected current/historical values and Products, and numbers/defaults SHALL remain exact.

#### Scenario: First unit is added without annotation consent
- **WHEN** a populated numeric attribute changes from null to GB without explicit consent
- **THEN** backend SHALL return ATTRIBUTE_UNIT_ANNOTATION_REQUIRES_CONFIRMATION without writes.

#### Scenario: Annotation is confirmed against unchanged state
- **WHEN** a valid matching preview and explicit annotation flag are supplied
- **THEN** unit meaning SHALL be recorded in definition/snapshot/audit while all numeric values remain unchanged.

### Requirement: Semantic unit changes and ordinary removal protect history
The service SHALL consider active/inactive EAV and relevant snapshots, not only active values. Switching A-to-B with history SHALL return ATTRIBUTE_UNIT_CHANGE_REQUIRES_CONVERSION; ordinary A-to-null SHALL return ATTRIBUTE_UNIT_REMOVAL_REQUIRES_MIGRATION. No automatic factor or relabeling SHALL occur.

#### Scenario: Active values are gone but inactive history remains
- **WHEN** GB is replaced by MB or removed
- **THEN** the request SHALL still be blocked without altering either numbers or history.

### Requirement: Units referenced in current or historical state remain protected
Non-system units used by active/inactive attributes or snapshots SHALL NOT be deactivated, removed or semantically changed in code/symbol/magnitude. Descriptive name corrections SHALL be audited without altering meaning. Unused non-system units SHALL support logical deactivation/reactivation with uniqueness validation.

#### Scenario: Only a reverted snapshot references a unit
- **WHEN** a caller attempts to deactivate that unit
- **THEN** UNIT_IN_USE SHALL prevent losing the historical meaning.

#### Scenario: Unit deactivation races with annotation
- **WHEN** one transaction annotates an attribute while another deactivates the unit
- **THEN** the shared locking protocol SHALL permit only a consistent outcome, never a committed annotation to an inactive unit.

### Requirement: Unit annotation participates in safe snapshot restoration
Attribute snapshots SHALL serialize codigo and unidad_id. Legacy JSON without these fields SHALL be interpreted by a compatible version policy without rewriting original history or regenerating stable codes. Undo of a first annotation SHALL be allowed as an explicit exception to ordinary removal only when exact post-state matches. Other unit edit prohibitions SHALL remain intact.

#### Scenario: Untouched annotation is reverted
- **WHEN** an authorized actor invokes snapshot undo and no relevant state changed
- **THEN** previous null unit SHALL be restored atomically without changing numeric values and the annotation unit SHALL remain protected by history.

#### Scenario: Annotation state changed before undo
- **WHEN** a value, definition, remap or assignment differs from the annotation post-snapshot
- **THEN** undo SHALL return ATTRIBUTE_STATE_CHANGED without removing the unit or overwriting newer data.

#### Scenario: Legacy snapshot lacks a unit key
- **WHEN** a compatible legacy snapshot is restored
- **THEN** missing unit SHALL mean its known legacy null state, stable codigo SHALL be preserved, and ambiguous restoration SHALL fail without partial writes.
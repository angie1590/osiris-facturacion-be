## ADDED Requirements

### Requirement: Attributes have stable canonical identities
Attributes SHALL have global unique stable normalized snake_case codes and unique normalized active names. Existing IDs SHALL be retained. Renaming a label SHALL NOT change its code. An attribute SHALL be reusable in multiple category branches rather than duplicated by name.

#### Scenario: Canonical attribute label is corrected
- **WHEN** an authorized user renames Memoria RAM
- **THEN** its ID, code, unit and assignments SHALL remain stable unless separately changed through their valid operations.

### Requirement: Effective attributes have one backend resolver
GET /categorias/{id}/atributos-efectivos SHALL resolve only active category ancestry, active mappings and active attributes for one category. The closest mapping for each atributo_id SHALL win, including explicitly null default/order. Results SHALL include mapping_id, canonical definition/unit/restrictions, effective config, origin and depth. Panel counts, EAV validation, impacts and backfills SHALL share that resolver.

#### Scenario: Child overrides a parent's default with null
- **WHEN** an active child mapping explicitly has valor_default=null
- **THEN** the effective default SHALL be null, not the ancestor's default, and origin SHALL identify the child.

#### Scenario: Explicit order and unordered attributes coexist
- **WHEN** effective mappings have numeric and null orden values
- **THEN** non-null orden SHALL sort first by number, followed by normalized name and atributo_id, while null entries sort alphabetically last.

### Requirement: Assignments reuse historical rows and isolate local overrides
Exactly one historical row SHALL exist for categoria_id plus atributo_id. Assigning existing active mapping SHALL return ATTRIBUTE_ALREADY_ASSIGNED; an inactive row SHALL be reactivated with its ID. Child overrides SHALL affect only obligatorio, valor_default and orden, never canonical name/code/type/unit/catalog/options/bounds. Creating a new attribute with assignment SHALL be atomic.

#### Scenario: Child overrides a reused attribute
- **WHEN** an actor configures the inherited Marca specifically in Mouse
- **THEN** a child mapping with the same atributo_id SHALL be created or reactivated while the ancestor mapping and definition remain unchanged.

#### Scenario: Assignment creation fails after definition creation
- **WHEN** relationship validation or audit fails in create-and-assign
- **THEN** neither the new definition nor assignment SHALL persist.

### Requirement: Defaults are explicit typed business values
Required SHALL NOT imply a default. Omitted fields SHALL preserve configuration, null SHALL clear default/order, and supplied defaults SHALL validate/canonicalize against the full attribute definition even for optional attributes. No N/A, zero, false, current date or first option SHALL be synthesized.

#### Scenario: Required mapping without default affects no incomplete Products
- **WHEN** required=true is requested without a default and no active applicable Product would lack a valid value
- **THEN** the mapping SHALL save with null default and no generated values.

#### Scenario: Caller explicitly clears a default
- **WHEN** valor_default=null is supplied and effective completeness remains valid
- **THEN** the stored default SHALL be cleared instead of preserved or replaced by a safe fallback.

#### Scenario: Supplied default violates the definition
- **WHEN** an optional or required mapping receives an out-of-range number or invalid select/catalog value
- **THEN** the request SHALL return DEFAULT_VALUE_INVALID and leave mappings and values unchanged.

### Requirement: Backfill is explicit and respects effective overrides
aplicar_default_a_existentes SHALL default to false, including create/assign/update. Backfill SHALL require a valid explicit default and opt-in, operate on active applicable Products for which this mapping is effective, be idempotent, preserve active values and audit writes. Existing inactive identities SHALL be handled without duplicate insertion or untracked historical overwrite.

#### Scenario: Flag is absent
- **WHEN** a mapping receives a default but backfill flag is false or omitted
- **THEN** no existing Product values SHALL be created, modified or reactivated.

#### Scenario: Parent default is applied with descendant overrides
- **WHEN** parent backfill is confirmed and some descendants have a different effective mapping
- **THEN** those overridden Products SHALL NOT receive the parent default and existing active values SHALL remain unchanged.

### Requirement: Administrative operations cannot introduce missing required values
Assignment changes, category moves and definition conversions SHALL preview affected active Products, missing valid required values and permitted actions. The final transaction SHALL recount/validate under locks. Missing values SHALL require valid supplied values or explicit valid fill-only backfill in the same operation; otherwise 409 PRODUCT_REQUIRED_ATTRIBUTES_MISSING SHALL occur without writes. No persistent remediation queue SHALL be created.

#### Scenario: Optional is changed to required with missing values
- **WHEN** active affected Products lack valid values and no backfill is explicitly confirmed
- **THEN** the operation SHALL report counts and actionable IDs and SHALL NOT mark the mapping required or invent values.

#### Scenario: Required attribute conversion would create incompatible remaps
- **WHEN** preview or final validation finds required effective values incompatible with the target definition
- **THEN** final application SHALL be blocked until valid replacements are provided atomically; a pending remap SHALL NOT be accepted as a valid required value.

#### Scenario: Optional conversion contains incompatible values
- **WHEN** incompatible values do not introduce required gaps
- **THEN** existing conversion/remap preservation and reversible snapshot behavior SHALL remain available without discarding originals.

### Requirement: Local removal differs from global deactivation
Local removal SHALL preview the resulting effective schema, validate completeness, deactivate only the target mapping and values that cease to apply, preserve applicable values and audit atomically. Global deactivation SHALL use the complete existing snapshot and deactivate all active mappings/EAV; pending remaps SHALL block it. Inherited relationships SHALL NOT be removed as if owned by the selected child.

#### Scenario: Removing an override reveals an ancestor assignment
- **WHEN** the ancestor still makes that attribute applicable and its required constraints remain satisfied
- **THEN** values SHALL be retained and the effective mapping SHALL revert to the ancestor instead of globally deactivating the attribute.

#### Scenario: Removing an assignment makes active values non-applicable
- **WHEN** a confirmed removal has affected values and no other effective assignment applies
- **THEN** those values SHALL be logically deactivated, never physically deleted, in the same audited transaction.

### Requirement: Restoration is exact and conditional
Global attribute reactivation/undo SHALL retain existing identity and restore a complete snapshot only if definition, mappings, EAV and remap post-state still match under lock. Resolved remaps or newer rows SHALL block restoration. Legacy inactive attributes without snapshots SHALL receive a readable administrative recovery conflict, not partial reactivation.

#### Scenario: A mapping changes after a global deactivation snapshot
- **WHEN** a restore request encounters that changed post-state
- **THEN** it SHALL return ATTRIBUTE_STATE_CHANGED with no partial restoration.
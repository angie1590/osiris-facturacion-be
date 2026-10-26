## ADDED Requirements

### Requirement: Attribute definitions can be edited in place

The system SHALL allow authorized actors to update an active attribute's name and complete type-specific definition while retaining its ID. Updates SHALL validate SELECT options, active catalog, numeric bounds and every affected product value before committing. Changes that invalidate existing values SHALL preserve those values and produce auditable remaps rather than discarding them.

#### Scenario: Correct a misspelled name

- **WHEN** an authorized actor changes only an attribute name to an unused normalized name
- **THEN** the same attribute ID and all category assignments/product values SHALL remain intact and the change SHALL be audited.

#### Scenario: Change type with convertible and incompatible values

- **WHEN** an authorized actor confirms a type change affecting product values
- **THEN** compatible values SHALL convert, incompatible values SHALL remain recoverable with pending remaps, and one snapshot SHALL record the complete before/after state atomically.

#### Scenario: Change same-type constraints

- **WHEN** SELECT options, catalog, min_value or max_value change and invalidate existing values
- **THEN** validation SHALL produce remaps for incompatible values and preserve their original typed values.

### Requirement: Attribute changes have a read-only impact preview

The system SHALL expose a non-mutating preview of applicable categories, assigned products/active values, expected conversions and required remaps for a proposed attribute update. Preview SHALL NOT create or reactivate catalogs or persist snapshots.

#### Scenario: Preview type change

- **WHEN** an authorized actor previews a valid target type and its options/bounds
- **THEN** the response SHALL include total affected values, convertible values, values requiring remap and whether explicit confirmation is needed, with no database writes.

#### Scenario: Preview references missing or inactive catalog

- **WHEN** a catalog definition is invalid or inactive
- **THEN** preview SHALL return a readable validation error and SHALL NOT modify catalogs or attribute state.

### Requirement: Attribute updates and deactivation have complete reversible snapshots

Each successful update that changes persisted definition/value/assignment state and each logical deactivation SHALL atomically append a snapshot containing the full attribute definition, category assignments, typed product values and related remap state before and after. Snapshot SHALL retain actor and timestamps and SHALL NOT physically delete business data.

#### Scenario: Update or deactivation fails

- **WHEN** any validation, conversion, audit, flush or commit fails during an attribute update/deactivation
- **THEN** attribute, assignments, values, remaps and snapshot SHALL all roll back.

#### Scenario: Soft-delete attribute

- **WHEN** an authorized actor deactivates an attribute without unresolved remaps
- **THEN** attribute, active category assignments and active product values SHALL become inactive in one transaction while IDs and historical rows remain.

#### Scenario: Deactivation has pending remaps

- **WHEN** an attribute has unresolved remaps
- **THEN** deactivation SHALL return 409 with blocking remap details and SHALL leave all records unchanged.

### Requirement: Revert is conditional on exact unchanged post-state

The system SHALL allow reverting only the latest unreverted snapshot. Before writing, it SHALL lock and compare current attribute definition, assignment/value row IDs and contents, and remap statuses to the recorded post-state. A mismatch SHALL return 409 without partial restoration. A successfully reverted change SHALL itself be audited and snapshots SHALL remain available for history.

#### Scenario: Undo an untouched type conversion with pending remaps

- **WHEN** no value/assignment changed and all remaps created by that conversion remain unresolved
- **THEN** the system SHALL restore the prior definition and typed values, deactivate those remaps, retain row IDs and mark the snapshot reverted atomically.

#### Scenario: Undo after a remap has been resolved

- **WHEN** a remap created by the snapshot is inactive/resolved or its product value differs from the snapshot post-state
- **THEN** the system SHALL return 409 explaining that the operation is no longer safely reversible and SHALL preserve current data.

#### Scenario: Concurrent EAV edit or new assignment

- **WHEN** a product value or category assignment changes after snapshot creation
- **THEN** undo SHALL detect the post-state mismatch, return 409 and SHALL NOT overwrite the newer change.

#### Scenario: Revert sequential edits

- **WHEN** an actor reverts the latest unchanged operation and then requests the preceding operation
- **THEN** each operation SHALL be restored in reverse order only while its recorded post-state matches exactly.

### Requirement: Attribute reactivation restores a deactivation snapshot

The system SHALL provide explicit reactivation for attributes deactivated by this lifecycle. Reactivation SHALL restore the same attribute ID and the category assignments/product values recorded before deactivation only if the deactivation snapshot remains latest and its post-state is intact. Legacy inactive attributes without snapshot SHALL NOT be partially reactivated.

#### Scenario: Reactivate unchanged deactivation

- **WHEN** an authorized actor reactivates an attribute whose deactivation snapshot remains unchanged
- **THEN** the same attribute, assignment and EAV IDs/states SHALL be restored atomically and the action SHALL be audited.

#### Scenario: Legacy attribute lacks snapshot

- **WHEN** reactivation is requested for an attribute deactivated before snapshot support
- **THEN** the API SHALL return 409 with a clear administrative recovery message and SHALL make no writes.

### Requirement: Snapshot schema migration is non-destructive

Schema evolution SHALL use Alembic and SHALL preserve existing attribute/category/EAV/remap rows. Downgrade SHALL refuse to drop unreverted recovery snapshots. Snapshot data SHALL exclude secrets and shall not rewrite sales/purchase documents or inventory quantities.

#### Scenario: Downgrade with recoverable snapshots

- **WHEN** downgrade is attempted while any snapshot remains unreverted
- **THEN** migration SHALL stop with a clear error and preserve the snapshot table and all data.

### Requirement: Required category attributes can backfill missing product values

Updating a category-attribute assignment from optional to required SHALL accept a typed default value. The API SHALL allow the caller to explicitly opt into applying that default to existing applicable products. Backfill SHALL create values only where no active EAV value exists and SHALL preserve every existing value.

#### Scenario: Require an optional attribute and backfill opted-in products

- **WHEN** an authorized actor marks an optional assignment required, supplies a valid default, and sets `aplicar_default_a_existentes` to true
- **THEN** applicable existing products without a value SHALL receive the typed default, while products with an existing value SHALL remain unchanged.

#### Scenario: Require an optional attribute without backfill

- **WHEN** an authorized actor marks an optional assignment required and declines backfill
- **THEN** the assignment SHALL become required with the default stored, but existing product values SHALL NOT be created or changed.

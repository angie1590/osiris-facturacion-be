## ADDED Requirements

### Requirement: Catalog planning has an explicit implementation boundary
This change SHALL cover administrative deliveries 1-6 only. Product atomic forms, direct primary-category activation, its active-product CHECK, legacy bridge removal and the full Product E2E SHALL remain gated to subsequent deliveries 7-8. No destructive migration or runtime change SHALL be performed when generating this proposal.

#### Scenario: Current delivery is applied later
- **WHEN** tasks for deliveries 1-6 are implemented
- **THEN** they SHALL NOT switch Product writers to a new FK, activate its CHECK or remove the existing bridge or Product form.

### Requirement: Preflight is read-only and blocks ambiguous data
Preflight SHALL report actionable IDs for normalized duplicate sibling names including inactive history, duplicate active attributes/codes, historical mapping duplicates, cycles, inconsistent parent flags, missing/multiple/invalid Product categories and required-value gaps. Unit candidates SHALL require explicit input, not name inference. Ambiguity SHALL produce a blocking exit status without choosing, merging, deactivating or renaming records.

#### Scenario: Legacy Product has multiple candidate categories
- **WHEN** preflight finds more than one candidate or no valid candidate
- **THEN** it SHALL report the Product and candidates, block the dependent migration and leave all records unchanged.

#### Scenario: Historical duplicate assignments exist
- **WHEN** inactive and active rows share categoria_id and atributo_id
- **THEN** preflight SHALL report every conflicting identity and SHALL NOT choose a survivor automatically.

### Requirement: Database constraints back historical identities
New Alembic revisions SHALL enforce normalized sibling-name uniqueness across active/inactive history with separate root and child indexes, historical UNIQUE(categoria_id, atributo_id), globally case-insensitive attribute codes and active normalized attribute names. Applied revisions SHALL NOT be rewritten. Service validation and database conflicts SHALL expose consistent 409 errors.

#### Scenario: Concurrent sibling creates pass service validation
- **WHEN** concurrent transactions attempt equivalent normalized names under the same parent
- **THEN** at most one SHALL commit and the other SHALL receive CATEGORY_DUPLICATE_NAME, including root categories.

#### Scenario: Same name is used under different parents
- **WHEN** distinct branches contain the same normalized category name
- **THEN** both identities SHALL remain valid and readable with their distinct paths.

### Requirement: Product migration preserves one authoritative writer
The future destination SHALL be Producto.categoria_principal_id, not a principal boolean on ProductoCategoria. The future cutover SHALL copy only unambiguous categories, include valid B3 buckets, stage FK/check/read/write activation and retire the bridge only after consumer verification. Current deliveries SHALL document this sequence without implementing it.

#### Scenario: The old Product form is still deployed
- **WHEN** the catalog administrative contracts are upgraded
- **THEN** no constraint requiring the new Product FK SHALL be activated and no uncoordinated second source of truth SHALL be introduced.

### Requirement: Global permissions and authoritative audit apply to every delivery
Catalog data SHALL remain global without isolated empresa_id additions. Effective action permissions SHALL authorize reads and writes independently of role labels. JWT/request context SHALL determine audit actor. Mutations SHALL atomically persist business changes, snapshots and audit or roll everything back.

#### Scenario: Caller forges the audit actor
- **WHEN** an authenticated caller supplies usuario_auditoria different from the request identity
- **THEN** recorded actor SHALL be the authenticated identity and insufficient effective permissions SHALL return 403 with no writes.

#### Scenario: An audit write fails after a catalog mutation
- **WHEN** audit, flush or commit fails
- **THEN** definitions, assignments, Product attribute values and recovery snapshots SHALL all roll back.

### Requirement: Previews are bound to confirmed state and payload
Read-only previews SHALL return an authenticated opaque precondicion_preview binding operation, target, actor, normalized payload, full relevant state fingerprint, version and expiry. The final mutation SHALL revalidate under a common deterministic locking protocol, including new relationships, and reject stale or altered preconditions with 409 CATALOG_PREVIEW_STALE before writing.

#### Scenario: A new assignment appears after preview
- **WHEN** an actor confirms an otherwise valid preview after another actor creates an effective override
- **THEN** the final request SHALL reject the changed state and SHALL NOT partially apply the originally previewed operation.

#### Scenario: Payload differs from the confirmed preview
- **WHEN** a request reuses a preview precondition for another unit, default or target
- **THEN** the request SHALL fail without writes and require a new preview.

### Requirement: Migration verification preserves recoverable history
Migrations SHALL be rehearsed in isolated PostgreSQL schemas with legacy data and upgrade/downgrade/upgrade checks. Downgrade SHALL block when it would discard referenced units, codes or unreverted recovery history. Operational rollback SHALL preserve schema/data instead of enabling implicit defaults or deleting snapshots.

#### Scenario: Downgrade would lose a referenced unit
- **WHEN** a rollback attempts to remove catalog columns or rows containing historical unit references
- **THEN** it SHALL stop with a readable error and retain those references and values.
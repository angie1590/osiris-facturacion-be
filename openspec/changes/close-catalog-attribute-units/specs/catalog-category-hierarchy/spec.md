## ADDED Requirements

### Requirement: Parent status is derived from active children
Canonical category writes SHALL NOT use client-supplied es_padre as authority. Reads SHALL expose tiene_hijos derived from active children. A compatibility projection of the legacy column SHALL remain synchronized only during staged client transition. A node SHALL be allowed to be both child and parent.

#### Scenario: A nested leaf receives its first child
- **WHEN** Laptop is created under Computadores, itself under Tecnologia
- **THEN** Computadores SHALL retain its own parent and report tiene_hijos=true without a client parent flag.

#### Scenario: Last active child is deactivated
- **WHEN** a category no longer has any active children
- **THEN** reads SHALL report tiene_hijos=false independently of its legacy flag.

### Requirement: Hierarchy mutations reject invalid destinations
Create, move and reactivate SHALL validate active non-temporary parents, reject self-reference/cycles and lock relevant hierarchy state. Arbitrary hierarchy depth SHALL be supported without a fixed business-level limit or infinite traversal of corrupt cycles.

#### Scenario: A category is moved into its own subtree
- **WHEN** a target parent is a descendant of the moved category
- **THEN** the service SHALL return CATEGORY_CYCLE and retain all hierarchy and Product classifications.

#### Scenario: A category is moved to root
- **WHEN** parent_id is explicitly null
- **THEN** the service SHALL process a root move, validate root-name uniqueness and SHALL NOT invoke B3 with a null parent.

### Requirement: B3 is internal transactional reclassification
When a leaf with directly classified Products receives a child, B3 SHALL lock the parent, create or reactivate its unique historical Sin clasificar bucket, move direct classifications and audit within the same transaction. The bucket SHALL be a sibling of the new child. It SHALL deactivate when no active Products remain. No stock quantities or document history SHALL change.

#### Scenario: An inactive B3 bucket already exists
- **WHEN** direct Products require reclassification under that parent
- **THEN** B3 SHALL reuse the bucket ID instead of creating a historically duplicate name.

#### Scenario: Reclassification fails midway
- **WHEN** a write or audit failure occurs while adding the child and moving classifications
- **THEN** the child, bucket state, classifications and audit SHALL all roll back.

### Requirement: Temporary categories cannot be managed manually
Manual creation or mutation of system buckets, use as a parent, normal Product destination, reactivation or deletion SHALL fail with CATEGORY_DEFAULT_PROTECTED. Internal B3 is the only permitted lifecycle owner.

#### Scenario: Caller bypasses disabled UI controls
- **WHEN** a caller directly requests deletion or manual reactivation of Sin clasificar
- **THEN** backend SHALL reject it without modifying bucket or Products.

### Requirement: Category lifecycle preserves historical identity
Ordinary inactive categories SHALL be explicitly reactivated or renamed instead of replaced by equivalent sibling identities. Reactivation SHALL preserve ID, verify valid parent and resulting invariants, and SHALL NOT infer restoration of Products or mappings. Deletion SHALL reject active children, reject positive stock and require explicit confirmation for cascading active Products without stock.

#### Scenario: User recreates an inactive sibling name
- **WHEN** a normalized equivalent category already exists inactive
- **THEN** creation SHALL return CATEGORY_DUPLICATE_NAME with allowed recovery actions instead of inserting a second identity.

#### Scenario: Ordinary category is reactivated
- **WHEN** its parent and name are valid and actor is authorized
- **THEN** the same category ID SHALL become active with audit while Products and mappings retain their independent states.

### Requirement: Tree and selectable reads are canonical and ordered
GET /categorias/arbol SHALL return nested nodes with id, nombre, parent_id, tiene_hijos, is_default and own/effective attribute counts calculated by backend. Siblings SHALL be ordered by lower(trim(nombre)), id. GET /categorias/seleccionables SHALL return only active non-temporary leaves; read permissions SHALL apply to both.

#### Scenario: Tree is fetched after creating a category
- **WHEN** a new sibling sorts before an existing one
- **THEN** the first refreshed response SHALL already place it in its final alphabetical position with canonical effective counts.

#### Scenario: Category receives a child concurrently with selection
- **WHEN** selectable results become outdated before a classification mutation
- **THEN** backend SHALL recheck leaf status under lock and reject an invalid destination rather than trusting the previous read.
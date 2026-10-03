## ADDED Requirements

### Requirement: Products expose a canonical BIEN/SERVICIO catalog flow
The system SHALL expose one canonical product administration flow for create, read, update, category assignment, attribute values, and tax profile management. The product type SHALL be `BIEN` or `SERVICIO`; existing values SHALL be preserved. All canonical frontend routes and internal links SHALL use Spanish. Legacy English routes SHALL redirect to their Spanish canonical destination and SHALL NOT render duplicate pages. The migration SHALL cover login/password, inventory, catalog, product, reports, audit, admin, and forbidden routes, not only product URLs.

#### Scenario: Create a service through the canonical form
- **WHEN** an authorized user creates a product with type `SERVICIO`
- **THEN** the API stores `SERVICIO` and the canonical frontend can display and edit it without converting it to `BIEN`

#### Scenario: English product URL redirects to the sole canonical route
- **WHEN** a user opens `/products` or `/products/:id` during compatibility transition
- **THEN** the browser redirects to `/productos` or its Spanish detail route and only one page implementation serves the product catalog

#### Scenario: Internal application links use Spanish routes
- **WHEN** a user navigates through menus, actions, or breadcrumbs
- **THEN** links use Spanish paths such as `/productos`, `/categorias`, `/inventario`, `/reportes`, and `/auditoria`

### Requirement: Company tax configuration defaults to IVA zero
When a company is created or its tax configuration is saved without any IVA selection, the system SHALL add the unique active and currently valid catalog IVA record whose percentage is zero. The system SHALL resolve it from catalog data, never from a hardcoded ID. Product tax profiles SHALL use only IVA and ICE; IRBPNR SHALL NOT be assignable to products in this scope.

#### Scenario: Company omits IVA selection
- **WHEN** a company saves its tax configuration with no IVA selected, with or without selected ICE
- **THEN** the persisted `impuesto_catalogo_ids` includes the canonical currently valid IVA 0% record

#### Scenario: Existing company has no configured IVA
- **WHEN** the catalog migration is applied to an existing company whose `impuesto_catalogo_ids` has no IVA
- **THEN** the company configuration receives the canonical currently valid IVA 0% record before product tax profiles are enabled

#### Scenario: No unique valid IVA zero entry exists
- **WHEN** configuration requires the default but the active catalog has zero or multiple canonical IVA 0% records
- **THEN** save fails with an actionable configuration error and does not persist an arbitrary tax ID

#### Scenario: Product selector excludes unsupported tax types
- **WHEN** a user configures a product tax profile
- **THEN** selectable/assignable tax types are IVA and ICE only, even if the company has other tax catalog IDs

### Requirement: Company-scoped product tax profiles
The system SHALL resolve the active enterprise from authenticated company scope and store tax assignments independently for each `(empresa, producto)`. It SHALL NOT trust a company identifier supplied only by the browser. A product tax profile SHALL contain exactly one active, currently valid IVA and MAY contain one active ICE, both allowed by `Empresa.impuesto_catalogo_ids` and compatible with product type `BIEN/SERVICIO`. A product with no IVA selection SHALL be rejected; the company IVA 0% default is an available configured option, not a silent assignment to every product.

#### Scenario: Select only taxes configured for the active enterprise
- **WHEN** the product tax selector is opened under enterprise A
- **THEN** it shows only active, currently valid catalog IDs listed in enterprise A configuration and applicable to the product type

#### Scenario: Reject a tax not configured for the enterprise
- **WHEN** a client submits a tax ID that exists but is absent from the active enterprise allowed-tax list
- **THEN** the backend rejects the create/update/assignment and leaves the prior product profile unchanged

#### Scenario: Reject expired or incompatible taxes
- **WHEN** a submitted tax is inactive, outside its validity dates, or its `aplica_a` conflicts with `BIEN/SERVICIO`
- **THEN** the backend rejects it before persisting the product or tax relationship

#### Scenario: Keep profiles independent for a shared product
- **WHEN** the same product is assigned to warehouses in two enterprises with different allowed IVA IDs
- **THEN** each enterprise reads and updates only its own profile and neither profile changes when the other is edited

#### Scenario: Require IVA and reject duplicate or unsupported types
- **WHEN** a create or replacement tax list is empty, lacks IVA, contains more than one active IVA/ICE, or contains IRBPNR
- **THEN** the request is rejected with a stable field-level validation error

#### Scenario: Update product and tax profile atomically
- **WHEN** a user changes product type and tax IDs in one update
- **THEN** both product fields and its enterprise tax profile commit together, or neither changes

### Requirement: Preserve company tax profile in purchase and sale snapshots
Purchases and sales SHALL resolve product taxes using their already-resolved enterprise ID. They SHALL snapshot the selected enterprise’s tax codes and rates onto document details at transaction time. Later edits to company configuration or product tax profiles SHALL NOT alter existing document snapshots.

#### Scenario: Sale uses active enterprise profile
- **WHEN** a sale is hydrated from a shared product under enterprise A
- **THEN** only enterprise A’s compatible tax profile is copied into sale detail tax snapshots

#### Scenario: Purchase uses active enterprise profile
- **WHEN** a purchase is hydrated from a shared product under enterprise A
- **THEN** only enterprise A’s compatible tax profile is copied into purchase detail tax snapshots

#### Scenario: Historical document remains unchanged
- **WHEN** a product tax profile is changed after a purchase or sale is saved
- **THEN** prior document detail snapshots retain their original tax IDs, SRI codes, rates, and amounts

### Requirement: Category hierarchy and product assignment are valid
A category SHALL have at most one parent; parent and child roles SHALL coexist for intermediate nodes. A parent SHALL exist and be active, cycles SHALL be rejected, and products SHALL be assigned only to active leaf categories not marked as temporary defaults.

#### Scenario: Reject category cycles and inactive parents
- **WHEN** a category is moved below itself, a descendant, or an inactive/nonexistent parent
- **THEN** the update is rejected and the hierarchy remains unchanged

#### Scenario: Product requires an eligible leaf category
- **WHEN** a product is created, moved, reactivated, or recategorized into an inactive, non-leaf, or temporary-default category
- **THEN** the backend rejects the assignment

#### Scenario: Convert a populated leaf to a parent safely
- **WHEN** a category with direct products receives its first child
- **THEN** a marked temporary `Sin clasificar` child is created/reused under the original category, at the same level as the newly created child, those direct products move atomically into it, and the response reports the count moved

#### Scenario: Keep the temporary category as sibling of the new child
- **WHEN** `Laptops` is created with parent `Computadoras` while products are assigned directly to `Computadoras`
- **THEN** `Sin clasificar` has parent `Computadoras`, is a sibling of `Laptops`, and receives the products formerly assigned directly to `Computadoras`

#### Scenario: Temporary category is not a final destination
- **WHEN** a user attempts to create or move a product into a default temporary category
- **THEN** the operation is rejected; when the category has no active products, it is deactivated automatically

#### Scenario: Show persistent recategorization warning
- **WHEN** the active enterprise has one or more active products in `Sin clasificar`
- **THEN** the authenticated application layout shows `Hay {N} producto(s) sin recategorizar en categorías "Sin clasificar". Recategorizar ahora` with a link to `/recategorizar`

#### Scenario: Clear recategorization warning when complete
- **WHEN** no active products remain in temporary `Sin clasificar` categories for the active enterprise
- **THEN** the warning is hidden and the empty temporary categories are deactivated

#### Scenario: Delete category with active children or stock
- **WHEN** deletion is requested for a category with active child categories or active products with positive stock
- **THEN** deletion is rejected with a specific conflict and no products/categories are partially changed

#### Scenario: Delete only zero-stock products with explicit confirmation
- **WHEN** all active products in a leaf category have zero stock and the caller confirms product cascade
- **THEN** products and category are soft-deleted atomically; without confirmation the operation is rejected

#### Scenario: Moving a category preserves attributes unless collision is confirmed
- **WHEN** a move has no inherited attribute-name collision
- **THEN** product attribute values are preserved and no reset flag is sent

#### Scenario: Resolve a real attribute collision during a move
- **WHEN** moving a subtree introduces duplicate inherited attributes and an authorized user explicitly confirms reset
- **THEN** only values affected by that subtree move are removed atomically with the move and the audit records the destructive reset

### Requirement: Inherited attributes are typed and enforceable
Attributes SHALL support `string`, `integer`, `decimal`, `boolean`, `date`, `select`, and `catalog` values. A product inherits active attributes from category ancestors, with the most specific mapping winning. Backend writes SHALL validate applicability, type, options/catalog membership, negative-number policy, and required values. If a required mapping has no configured value, the system SHALL preserve its current type-specific default generation (`N/A`, `0`, `0.00`, `false`, or current date) and store that default in the matching typed field. Attribute names SHALL be unique within an inheritance branch while allowing the same name in independent branches.

#### Scenario: Inherit the most specific active mapping
- **WHEN** the same attribute is mapped at an ancestor and a child category
- **THEN** product forms and API reads use the child mapping and its order/default/required settings

#### Scenario: Reject values outside select or catalog options
- **WHEN** a product submits a select option not configured or a catalog value not active in its catalog
- **THEN** the backend rejects the value and preserves the previous value

#### Scenario: Preserve typed defaults for required attributes
- **WHEN** a required mapping has no explicit default
- **THEN** the current type-specific default is generated/backfilled in the corresponding typed value field and shown in product forms

#### Scenario: Allow duplicate names only in independent branches
- **WHEN** an attribute name is already present in the effective ancestor/descendant branch
- **THEN** the mapping/create is rejected; the same name in a disjoint branch remains allowed

#### Scenario: Migrate values when attribute type changes
- **WHEN** an attribute’s type changes
- **THEN** convertible product values are migrated, unconvertible values become auditable pending remaps, and invalid values are not silently discarded

### Requirement: Product catalog operations are authorized and audited
Category and attribute administration SHALL follow the agreed administrator/supervisor policy; product create, edit, status, and recategorization SHALL follow the agreed product RBAC matrix. Sensitive lifecycle and destructive category moves SHALL emit audit records with actor, enterprise scope where applicable, before/after state, and reason.

#### Scenario: Unauthorized user cannot mutate the catalog
- **WHEN** a user without the required role creates, edits, deactivates, reactivates, or recategorizes an entity
- **THEN** the backend returns 403 and makes no state change

#### Scenario: Record product tax profile changes
- **WHEN** an authorized user changes an enterprise-scoped product tax profile
- **THEN** the audit log records enterprise, product, prior tax set, new tax set, and actor

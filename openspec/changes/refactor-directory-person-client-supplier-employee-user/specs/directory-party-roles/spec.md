## ADDED Requirements

### Requirement: Canonical natural-person identity and independent roles

The system SHALL store identity/contact only in Persona and SHALL allow the same Persona to hold Cliente, Proveedor Persona, Empleado and Usuario simultaneously using composition. Each role SHALL be unique by persona_id in the database; Usuario SHALL NOT reference empleado_id. Proveedor Sociedad SHALL be a separate juridical entity with a required non-unique natural-person contact.

#### Scenario: Customer also becomes employee

- **WHEN** an active Cliente's Persona is registered as Empleado
- **THEN** the new Empleado and its Usuario SHALL reference that Persona without duplicating identity or changing Cliente.

#### Scenario: Duplicate role including inactive history

- **WHEN** an insert attempts a second role for a Persona with that role active or inactive
- **THEN** the API SHALL return 409 and the database SHALL prevent the duplicate.

### Requirement: Validated and normalized identity

The system SHALL normalize identification before uniqueness/search, require trimmed nonempty name/surname, validate optional email and field lengths, validate ten-digit cedula with the applicable Ecuadorian policy, restrict Persona RUC to natural persons and normalize passports consistently. Identification changes SHALL include type and full revalidation. Local structure SHALL NOT be presented as proof of SRI existence/activity.

#### Scenario: Identification normalization and passport

- **WHEN** a passport with surrounding spaces and lowercase letters is submitted
- **THEN** it SHALL be compared and stored in its trimmed uppercase canonical form subject to the documented length policy.

#### Scenario: Invalid or juridical identity

- **WHEN** an invalid cedula or a juridical RUC is submitted as Persona
- **THEN** the API SHALL reject it without creating Persona and SHALL explain the applicable identification rule.

#### Scenario: Partial identification update

- **WHEN** identificacion changes without tipo_identificacion
- **THEN** the API SHALL reject the payload and preserve the original identity.

### Requirement: Transactional contextual creation

Cliente, Proveedor Persona, Empleado and Usuario create requests SHALL accept exactly one of persona_id or persona_nueva. Sociedad create SHALL accept exactly one of persona_contacto_id or persona_contacto_nueva. The system SHALL atomically resolve/create Persona and persist all dependent records, with a single transaction owner and no independent intermediate commits.

#### Scenario: Invalid union payload

- **WHEN** both alternatives or neither valid alternative are supplied
- **THEN** the API SHALL return 422 and SHALL persist nothing.

#### Scenario: Parent validation or persistence fails

- **WHEN** a composite Cliente, Proveedor Persona, Sociedad, Usuario or Empleado request creates Persona but any subsequent validation, flush or commit fails
- **THEN** the new Persona and all records of that attempt SHALL roll back.

#### Scenario: Existing active Persona is reused

- **WHEN** persona_nueva matches an existing active normalized identification
- **THEN** the system SHALL reuse that Persona and SHALL NOT overwrite its personal data.

#### Scenario: Inactive Persona exists

- **WHEN** composite resolution finds an inactive Persona
- **THEN** the API SHALL return 409 with a reactivation reference and SHALL NOT create a duplicate or reactivate implicitly.

### Requirement: Safe concurrent identity resolution

The system SHALL protect normalized identity with a unique constraint and SHALL recover from a competing identity insert by freshly resolving the winning active Persona without silently overwriting it. Same-role races SHALL preserve role uniqueness.

#### Scenario: Competing transactions create the same Persona

- **WHEN** two PostgreSQL transactions submit different role requests for the same previously absent identification
- **THEN** only one Persona SHALL remain and both compatible roles SHALL reference it after bounded conflict recovery.

#### Scenario: Competing transactions create the same role

- **WHEN** two PostgreSQL transactions submit the same role for the same Persona
- **THEN** only one role SHALL persist and the losing request SHALL return 409 without partial records.

### Requirement: Explicit reactivation and soft deletion

Operational entities SHALL use soft deletion, retain historical IDs and audit changes. Inactive natural keys SHALL produce explicit conflicts rather than new records. Authorized reactivation SHALL revalidate active FKs and domain rules and SHALL NOT bypass lifecycle validation through generic activo updates.

#### Scenario: Reactivate an inactive customer

- **WHEN** an actor with update permission invokes reactivation for an inactive Cliente with active Persona and TipoCliente
- **THEN** the same Cliente ID SHALL become active with updated actor/timestamp.

#### Scenario: Reactivation has inactive reference

- **WHEN** reactivation requires an inactive Persona, Rol, Empresa or catalog entry
- **THEN** the API SHALL return 409 and SHALL leave the entity inactive.

#### Scenario: Commercial role is deactivated

- **WHEN** Cliente, Proveedor Persona or Proveedor Sociedad is deactivated
- **THEN** its Persona/contact and any Usuario SHALL remain unchanged.

### Requirement: Persona deactivation protects active dependencies

Persona deactivation SHALL be rejected with 409 while active Cliente, Proveedor Persona, Empleado, Usuario or contact usage by active Sociedad exists. Dependency checks and dependent creation SHALL remain consistent under concurrency.

#### Scenario: Active employee and contact dependencies

- **WHEN** an actor attempts Persona deactivation with an active Empleado or an active Sociedad contact usage
- **THEN** the API SHALL identify the blocking dependencies and SHALL preserve Persona active.

#### Scenario: Deactivation competes with role creation

- **WHEN** role creation and Persona deactivation compete in separate transactions
- **THEN** the system SHALL NOT commit an active role referencing an inactive Persona.

### Requirement: TipoCliente commercial classification

TipoCliente SHALL have a trimmed case-insensitive unique name and decimal discount in inclusive range 0..100. Cliente SHALL require an active TipoCliente and active Persona, allow audited TipoCliente change, prohibit effective persona_id change and preserve the role on reactivation.

#### Scenario: Invalid discount or duplicate normalized name

- **WHEN** a discount is outside 0..100 or a name collides after normalization
- **THEN** the API SHALL reject the request without persisting the invalid classification.

#### Scenario: Classification in use is deactivated

- **WHEN** an actor deactivates TipoCliente referenced by active Clientes
- **THEN** the API SHALL return 409 and require reassignment first.

#### Scenario: Customer classification changes

- **WHEN** Cliente is updated to another active TipoCliente
- **THEN** only classification and audit metadata SHALL change, preserving Persona and Cliente ID.

### Requirement: Natural-person supplier fiscal compatibility

Proveedor Persona SHALL require an active Persona with compatible natural-person RUC and an active applicable TipoContribuyente. Catalog applicability SHALL use explicit semantic metadata, not free-text names or scattered hard-coded lists. The current exclusion of Gran Contribuyente for natural suppliers SHALL be represented by approved catalog data.

#### Scenario: Persona uses cedula or incompatible catalog

- **WHEN** a supplier references Persona with CEDULA or a taxpayer category not applicable to natural suppliers
- **THEN** the API SHALL reject the operation with readable detail and no partial persistence.

#### Scenario: Catalog display name changes

- **WHEN** the display name of a TipoContribuyente changes while applicability metadata remains unchanged
- **THEN** provider eligibility SHALL remain unchanged.

### Requirement: Society supplier and mutable contact

Proveedor Sociedad SHALL have unique compatible juridical RUC, nonempty razon_social/direccion, valid required email, normalized optional phone and active applicable taxpayer type/contact. Contact SHALL be replaceable and SHALL support embedded new contact creation atomically with create or update.

#### Scenario: Change to existing contact

- **WHEN** an authorized actor changes the contact from active Persona A to active Persona B
- **THEN** Sociedad SHALL reference B, audit the change and leave A unchanged.

#### Scenario: New contact with failed society update

- **WHEN** an update creates a new contact but Sociedad validation or persistence fails
- **THEN** both the contact creation and Sociedad changes SHALL roll back.

#### Scenario: Natural RUC or duplicate RUC in society

- **WHEN** Sociedad is submitted with a natural-person RUC or an already registered RUC
- **THEN** the API SHALL reject it and SHALL NOT bypass existing inactive history.

### Requirement: Explicit immutable role identity

Updates SHALL reject effective changes to persona_id in Cliente, Proveedor Persona, Empleado and Usuario, and username in Usuario, with 409 or structural 422 and readable detail. DTO parsing and service filtering SHALL NOT silently discard these attempts.

#### Scenario: Role identity replacement attempted

- **WHEN** an update supplies a different persona_id for any existing role
- **THEN** the API SHALL reject it explicitly and SHALL preserve the original relationship.

#### Scenario: User username replacement attempted

- **WHEN** normal Usuario update supplies a different username
- **THEN** the API SHALL reject it explicitly rather than ignore the field.

### Requirement: Employee labor validation and atomic provisioning

Empleado SHALL require active Persona/Empresa, globally unique persona_id, decimal nonnegative salario, fecha_ingreso not in the future, fecha_salida strictly after ingreso when present and configurable minimum age EMP_MIN_AGE default 16 when birth date exists. Operational creation SHALL provision Usuario with the same Persona atomically.

#### Scenario: Labor dates and salary invalid

- **WHEN** salary is negative, ingreso is future, salida is not after ingreso or age is below configured minimum
- **THEN** the API SHALL reject the request without committing Persona, Empleado or Usuario of that attempt.

#### Scenario: User creation fails

- **WHEN** the requested username conflicts during Empleado creation
- **THEN** no new Empleado or contextual Persona SHALL remain persisted.

#### Scenario: Employee persistence fails after user flush

- **WHEN** Usuario has been flushed but Empleado persistence fails
- **THEN** the new Usuario and contextual Persona SHALL roll back.

#### Scenario: Employee Persona already has Usuario

- **WHEN** operational creation references a Persona with an existing Usuario
- **THEN** the API SHALL return an explicit administrative conflict without creating a second Usuario or changing its credentials silently.

### Requirement: Employee deactivation revokes access atomically

Empleado deactivation SHALL deactivate the Usuario sharing persona_id and set session invalidation in the same transaction, leaving Persona unchanged. Employee reactivation SHALL NOT automatically reactivate Usuario.

#### Scenario: Employee leaves

- **WHEN** an active Empleado is deactivated
- **THEN** Empleado and its Usuario SHALL be inactive, prior access/refresh sessions SHALL be invalid and Persona SHALL remain unchanged.

#### Scenario: Revocation persistence fails

- **WHEN** any write in the employee deactivation operation fails
- **THEN** employee status, user status and invalidation timestamp SHALL all roll back.

#### Scenario: Employee returns

- **WHEN** Empleado is reactivated
- **THEN** its existing Usuario SHALL remain inactive until a separate authorized administrative decision.

### Requirement: User credentials and access lifecycle

Usuario SHALL require active Persona/Rol, unique persona_id and database-enforced case-insensitive trimmed username. A single policy of at least eight characters SHALL govern all password writes. Creation/reset SHALL require initial password change; successful change SHALL clear the flag. Hashes SHALL never be returned. Direct Usuario creation SHALL NOT require Empleado.

#### Scenario: Username differs only by case and spaces

- **WHEN** `Andrea` is submitted while `andrea` exists, including inactive accounts
- **THEN** the API SHALL return 409 and the unique constraint SHALL block a second account.

#### Scenario: Short password through any write path

- **WHEN** direct user create, employee create, credential update, reset generation or change-password uses a password below the unified policy
- **THEN** the system SHALL prevent storing it and SHALL apply the same policy across paths.

#### Scenario: Reset and change password

- **WHEN** an authorized actor resets a password
- **THEN** only its hash SHALL persist, a temporary password SHALL be returned once to that actor, previous sessions SHALL be invalidated and requiere_cambio_password SHALL be true until successful change.

#### Scenario: User without employee

- **WHEN** an authorized administrator creates Usuario with valid Persona and Rol
- **THEN** the account SHALL be created without requiring an Empleado relationship.

#### Scenario: User deactivation or logout

- **WHEN** Usuario is deactivated or logout invalidates its session
- **THEN** inactive login and prior access/refresh tokens SHALL be rejected without changing Persona or Empleado.

### Requirement: Authoritative audit and server-side RBAC

The system SHALL enforce read/create/update/delete permissions on all Directory endpoints and actions, tenant access for Empleado and required permissions for embedded Persona writes. Authoritative audit actor SHALL derive from authenticated context; legacy usuario_auditoria SHALL NOT override it. All create/update/deactivate/reactivate/reset operations SHALL be audited without credential secrets.

#### Scenario: Spoofed audit actor

- **WHEN** authenticated Usuario A submits usuario_auditoria naming B
- **THEN** authoritative persisted audit actor SHALL remain A.

#### Scenario: Direct unauthorized operation

- **WHEN** an actor without create Empleado permission calls its endpoint directly
- **THEN** the backend SHALL return 403 and SHALL persist no records from that attempt.

#### Scenario: Role permission without embedded Persona permission

- **WHEN** an actor may create the role but lacks permission to create a required new Persona
- **THEN** the composite request SHALL return 403 with no partial persistence.

#### Scenario: Wrong company employee action

- **WHEN** an actor attempts an Empleado operation for an Empresa outside authorized scope
- **THEN** the API SHALL return 403 without leaking protected data or modifying records.

### Requirement: Efficient directory queries and readable contracts

Directory lists SHALL be paginated, searchable and sortable by allowed relevant columns, show active records by default and allow explicit inactive views. Persona SHALL support exact normalized identification and text search over identification/name/surname/email/phone. Role search SHALL include related Persona fields via queries, not stored copies. Persona links SHALL include roles and contact usages with permitted readable data and no hashes.

#### Scenario: Standard list and inactive view

- **WHEN** list filters are omitted
- **THEN** only active items SHALL be returned with filtered total; an explicit include-inactive or inactive-only view SHALL expose historical items without changing IDs.

#### Scenario: Search beyond first page

- **WHEN** a matching Persona is not in the previously loaded page
- **THEN** server identification/text search SHALL resolve it and return correct filtered pagination rather than search a truncated client-side set.

#### Scenario: Links reveal active dependencies

- **WHEN** an authorized actor requests `/personas/{id}/vinculos`
- **THEN** the response SHALL identify role states and society contact usages within permitted visibility and SHALL NOT expose passwords or hashes.

### Requirement: Safe migrations and declared scope boundaries

Schema evolution SHALL use Alembic with duplicate/collision preflight and PostgreSQL tests of real constraints. Migrations SHALL NOT silently delete or merge conflicting history. Persona/commercial masters SHALL remain global in this change; Consumidor Final SHALL remain a document condition with cliente_id null, not fictitious Persona. Cliente Sociedad and commercial company enablement SHALL be recorded as subsequent capabilities.

#### Scenario: Duplicate data prevents new constraint

- **WHEN** preflight detects conflicting provider roles or normalized usernames/identifications
- **THEN** deployment SHALL stop with a conflict report pending approved resolution and SHALL preserve all data.

#### Scenario: Consumer-final sale or juridical customer

- **WHEN** a sale uses Consumidor Final or requests a juridical customer unsupported by this model
- **THEN** Consumidor Final SHALL NOT create a fake Persona and the juridical gap SHALL NOT be hidden by registering a society as a natural person.

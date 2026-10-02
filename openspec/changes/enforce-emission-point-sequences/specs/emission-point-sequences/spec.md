## ADDED Requirements

### Requirement: Format invoice series from establishment, point and nine-digit sequence
The system SHALL format an issued invoice number as exactly `EEE-PPP-SSSSSSSSS`, where EEE is the three-digit registered establishment code, PPP is the three-digit emission point code, and S is a nine-digit positive consecutive number. The point SHALL expose its next authorized initial sequence at creation, defaulting to 1, and SHALL reject values outside 1..999999999.

#### Scenario: First invoice uses sequence 1
- **WHEN** a new point is configured with initial sequence 1 and its first sale is issued
- **THEN** the invoice number ends in `000000001`

#### Scenario: Preserve configured authorized starting number
- **WHEN** a new point is configured with an explicitly authorized initial sequence N
- **THEN** its first issued invoice ends in N padded to nine digits

#### Scenario: Reject invalid series blocks or overflow
- **WHEN** a point code or establishment code is not three digits, or the next sequence exceeds 999999999
- **THEN** the system rejects issuance rather than generating a malformed or ten-digit number

### Requirement: Commit sequential numbering atomically when issuing a sale
The system SHALL allocate an invoice sequence only while emitting the sale, using a row lock on that point/document counter in the same database transaction as sale status, inventory outflow, receivable, invoice document and SRI queue changes. Draft creation and sequence preview SHALL NOT increment or commit the counter. Failed emission SHALL roll back the counter update.

#### Scenario: Saving a draft does not consume a number
- **WHEN** a sale with a point is saved with automatic emission disabled
- **THEN** it remains without a committed invoice number and the point counter does not advance

#### Scenario: Concurrent emissions receive consecutive distinct numbers
- **WHEN** two transactions issue sales concurrently at the same point and document type
- **THEN** each commits a unique number in strict order without skipped allocations

#### Scenario: Failed emission does not leave a gap
- **WHEN** stock validation, receivable creation, or SRI queue creation fails before commit
- **THEN** both the sale transaction and its counter increment roll back

#### Scenario: Preview does not reserve
- **WHEN** one or more clients request the next-number preview without issuing a sale
- **THEN** no counter is changed and the next issued sale receives the current next sequence

#### Scenario: Reject counter overflow
- **WHEN** the point's last issued number is 999999999
- **THEN** emission fails with an actionable error and creates no partially emitted sale

### Requirement: Maintain independent, immutable physical and electronic point series
Each emission point SHALL own an independent sequence for each document type and have a physical/electronic modality fixed at creation. Updating a point SHALL NOT change its modality. A migration from a physical series to electronic invoicing SHALL use a newly created electronic point/series with an authorized initial sequence; the same point ID and counter SHALL NOT be reused across modalities. Electronic sales SHALL use an electronic point, and physical notes SHALL use a physical point, subject only to explicitly defined tax-law exceptions.

#### Scenario: Points have independent counters
- **WHEN** two points under one establishment issue invoices
- **THEN** each point advances its own sequence independently

#### Scenario: A modality change requires a new point
- **WHEN** an administrator needs to move from a physical to electronic series
- **THEN** the old point retains its modality and the administrator creates a new electronic point with its authorized starting sequence

#### Scenario: Prevent issue through the wrong modality
- **WHEN** a sale's effective emission type does not match the selected point modality
- **THEN** the backend rejects issuance before inventory, receivable or sequence changes

### Requirement: Prevent duplicate invoice numbers and sequence skipping by adjustment
The system SHALL enforce uniqueness for a formatted invoice number within an enterprise and emission point. Manual counter adjustments SHALL NOT create a forward gap or reissue a number after any sale has used that point. A series already used SHALL be immutable; an authorized new start SHALL be represented by a new point/series and recorded for audit.

#### Scenario: Duplicate formatted number is rejected
- **WHEN** a second sale attempts to persist a formatted number already used for the same company and point
- **THEN** the database/API rejects the transaction and no inventory or receivable effects remain

#### Scenario: Used point sequence cannot be manually changed
- **WHEN** an administrator requests a counter change after a sale has used the point
- **THEN** the request is rejected with guidance to open a new authorized point/series

#### Scenario: Initial sequence can be corrected before first issue
- **WHEN** an authorized administrator configures a point's initial number before any sale is issued
- **THEN** the next issue uses that initial number and the change is audited

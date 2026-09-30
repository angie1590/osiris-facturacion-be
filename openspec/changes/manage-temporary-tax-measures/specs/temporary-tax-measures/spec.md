## ADDED Requirements

### Requirement: Administrators manage temporary tax measures
The system SHALL allow an authorized administrator to create, read, update, deactivate, and audit a temporary tax measure scoped to one company, with a name, official legal reference, tax type, component, inclusive effective dates, confirmed SRI tax and percentage codes, rate, and one or more eligible products. A specific ICE component SHALL also define its taxable unit and product-specific conversion factor. Measures SHALL default to draft and SHALL NOT affect sales until explicitly activated after validation.

#### Scenario: Create draft measure
- **WHEN** an authorized administrator saves a complete but inactive measure
- **THEN** the system stores it as draft and regular catalog rates remain in effect

#### Scenario: Reject measure without authoritative tax code
- **WHEN** an administrator attempts to activate a measure without a confirmed SRI percentage code, official reference, dates, or eligible product scope
- **THEN** the system rejects activation and explains the missing required data

#### Scenario: Reject specific ICE scope without conversion
- **WHEN** an administrator activates an ICE-specific measure with an eligible product missing its positive conversion to the taxable unit
- **THEN** the system rejects activation and does not apply that measure to any sale

#### Scenario: Enforce administrative authorization
- **WHEN** a user without the existing administrative permission requests a measure mutation
- **THEN** the API returns forbidden and leaves the measure unchanged

### Requirement: Apply active measures only to eligible sale lines
The system SHALL resolve temporary measures server-side using the sale's company, issue date, product, tax type, and component. Effective start and end dates SHALL be inclusive. A measure SHALL apply only when active and all scope conditions match; otherwise the regular product tax configuration SHALL be used. The client SHALL NOT select or override the effective measure, rate, tax code, unit conversion, or resulting tax amount.

#### Scenario: Apply temporary IVA to eligible tourism service
- **WHEN** an electronic or physical sale is issued within an active measure's inclusive dates by its scoped company and contains an explicitly eligible service product
- **THEN** the backend calculates that line's IVA using the configured temporary rate and confirmed SRI percentage code

#### Scenario: Keep regular IVA outside measure scope
- **WHEN** a sale date is outside the effective dates, the company differs, or a line's product is not explicitly eligible
- **THEN** that line uses its regular product IVA without a temporary override

#### Scenario: Apply temporary ICE components
- **WHEN** an eligible beer product is sold during an active company measure
- **THEN** each configured ICE component is calculated independently using its configured basis (ad valorem on the monetary base or specific rate on the converted taxable quantity)

#### Scenario: Reject overlapping active measures
- **WHEN** a change would make two active measures overlap for the same company, product, tax type, and component on any date
- **THEN** the system rejects activation/update and identifies the conflict instead of choosing one implicitly

#### Scenario: Preserve non-applicable activity and unaffected taxes
- **WHEN** a measure targets only a subset of a sale's products or one ICE component
- **THEN** all other products and tax components retain their regular configured calculations

### Requirement: Freeze tax measure application in sale snapshots
The system SHALL persist, for every calculated sale tax component, its tax type, component/basis, confirmed SRI codes, rate, taxable base or quantity, calculated value, and the applied measure reference/code when applicable. Later measure edits, deactivation, or expiration SHALL NOT change saved sale totals or snapshots.

#### Scenario: Record the applied measure
- **WHEN** a temporary measure changes a line's tax calculation
- **THEN** the persisted snapshot records the exact rate, SRI codes, basis/conversion, value, and measure identifier/code used

#### Scenario: Historical sale is stable after measure update
- **WHEN** an administrator edits or deactivates a measure after a sale has been recorded
- **THEN** the recorded sale, invoice payload, totals, receivable, and tax snapshots remain unchanged

#### Scenario: Regular tax snapshot has no measure reference
- **WHEN** a sale line is calculated without an eligible temporary measure
- **THEN** the regular tax snapshot is stored with a null temporary-measure reference and the existing regular amount

### Requirement: Manage measures from the administrative frontend
The frontend SHALL provide authorized administrators a responsive shared-component interface to list, search, create, edit, review, activate, and deactivate measures. It SHALL display dates, current status, legal reference, company, eligible product names, tax component, confirmed SRI code, rate and taxable unit using human-readable labels rather than identifiers.

#### Scenario: Find a measure by product or decree
- **WHEN** an administrator searches the measure list by legal reference, company name, or eligible product name
- **THEN** matching measures are shown with their status and effective period

#### Scenario: Review incomplete or expired measure
- **WHEN** a draft lacks required data or a measure's end date has passed
- **THEN** the UI clearly indicates that it is not currently applicable and prevents accidental activation of incomplete data

#### Scenario: Frontend mutation error
- **WHEN** the API rejects activation due to invalid scope, code, or overlap
- **THEN** the UI preserves entered data and displays the backend validation message without reporting success

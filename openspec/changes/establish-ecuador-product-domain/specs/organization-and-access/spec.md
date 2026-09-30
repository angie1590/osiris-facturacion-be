## ADDED Requirements

### Requirement: Organización ecuatoriana configurable
El sistema SHALL administrar empresa, sucursales, puntos de emisión y secuenciales con datos tributarios ecuatorianos validados.

#### Scenario: Configuración apta para emitir
- **WHEN** una empresa guarda RUC, régimen, establecimiento y punto de emisión válidos
- **THEN** el sistema dispone del contexto necesario para numerar comprobantes

### Requirement: Aislamiento y autorización
El sistema MUST aislar datos por empresa y MUST autorizar acciones sensibles por usuario y rol.

#### Scenario: Acceso cruzado
- **WHEN** un usuario solicita una entidad de otra empresa
- **THEN** la API rechaza la operación sin revelar datos ajenos
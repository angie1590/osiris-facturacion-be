## ADDED Requirements

### Requirement: Emisión electrónica real
El sistema SHALL generar, firmar, enviar y consultar comprobantes con el ambiente SRI configurado y MUST impedir autorización simulada en producción.

#### Scenario: Dependencia FE ausente en producción
- **WHEN** falta una dependencia de firma o transmisión
- **THEN** la emisión falla de forma visible y auditable

### Requirement: Recuperación y documentos autorizados
El sistema SHALL persistir intentos y estados, reintentar errores recuperables y entregar XML y RIDE solo con reglas compatibles con el estado del documento.

#### Scenario: Reintento exitoso
- **WHEN** un documento pendiente es autorizado tras un reintento
- **THEN** se actualiza su historial y quedan disponibles XML y RIDE
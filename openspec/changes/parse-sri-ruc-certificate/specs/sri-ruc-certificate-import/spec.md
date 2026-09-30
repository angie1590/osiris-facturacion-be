## ADDED Requirements

### Requirement: Vista previa sin persistencia
El sistema SHALL recibir un certificado RUC PDF y devolver datos estructurados sin guardar el archivo ni modificar la empresa.

#### Scenario: Certificado válido
- **WHEN** el usuario carga un PDF SRI válido de hasta 5 MB
- **THEN** se devuelve RUC, nombre, régimen, tipo, indicadores tributarios, dirección y datos informativos detectados

### Requirement: Validación defensiva
El sistema MUST rechazar archivos que no sean PDF, excedan el límite, estén cifrados, no contengan texto reconocible o incluyan un RUC inválido.

#### Scenario: Archivo inválido
- **WHEN** el contenido no inicia con firma PDF o no contiene un certificado RUC reconocible
- **THEN** la API responde 400 con un mensaje legible y no conserva el contenido

### Requirement: Trazabilidad de datos no mapeados
La vista previa SHALL separar campos aplicables al modelo Empresa de información detectada sin destino persistente.

#### Scenario: Certificado contiene artesano y actividades
- **WHEN** se detectan artesano, actividades u obligaciones tributarias
- **THEN** se devuelven como información adicional y no se asignan silenciosamente a campos incorrectos
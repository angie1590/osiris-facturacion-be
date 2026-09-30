## Why

La configuración inicial de empresa exige transcribir datos que ya constan en el certificado RUC oficial. La captura manual aumenta errores y tiempo de onboarding.

## What Changes

- Añadir un endpoint multipart que reciba un certificado RUC PDF y devuelva una vista previa estructurada.
- Extraer únicamente en memoria y no persistir el archivo ni los datos detectados.
- Validar tipo, firma PDF, tamaño, número de páginas y RUC ecuatoriano.
- Informar campos no persistibles y ambigüedades mediante advertencias.

## Capabilities

### New Capabilities
- `sri-ruc-certificate-import`: extracción segura y normalizada de certificados RUC.

### Modified Capabilities

## Impact

- Router y servicios del módulo empresa.
- Nueva dependencia `pypdf`.
- Nuevo contrato de vista previa consumido por frontend.
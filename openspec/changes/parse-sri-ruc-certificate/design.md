## Context

El certificado SRI contiene texto seleccionable y etiquetas relativamente estables. El backend es la autoridad para validar documentos y normalizar valores antes de exponerlos al formulario.

## Goals / Non-Goals

**Goals:**
- Extraer certificados oficiales con validación defensiva.
- Mantener el archivo solo en memoria.
- Producir una vista previa tipada y testeable.

**Non-Goals:**
- OCR para PDFs escaneados en esta primera versión.
- Verificar en línea el código QR o código de verificación.
- Guardar automáticamente la empresa.

## Decisions

- Usar `pypdf` para extracción local sin servicios externos.
- Separar `parse_text` de `extract_pdf` para probar reglas con texto oficial anonimizable.
- Limitar a 5 MB y 5 páginas; rechazar documentos cifrados.
- Inferir PERSONA_NATURAL/SOCIEDAD únicamente desde la etiqueta Tipo.

## Risks / Trade-offs

- Cambios futuros del formato SRI -> parser por etiquetas, advertencias y fixtures de regresión.
- PDF imagen sin texto -> error explícito y captura manual.
- Orden de extracción variable -> normalización de espacios y expresiones acotadas por etiquetas.
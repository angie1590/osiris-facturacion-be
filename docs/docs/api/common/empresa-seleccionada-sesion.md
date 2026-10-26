---
id: empresa-seleccionada-sesion
title: "Empresa Seleccionada por Sesión (Multiempresa)"
sidebar_position: 3
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Common - Empresa Seleccionada por Sesión

Este apartado define el contrato obligatorio para frontend cuando un usuario trabaja con varias empresas en la misma plataforma.

## Objetivo Operativo

- El usuario inicia sesión.
- Selecciona una empresa activa.
- Desde ese momento, los recursos con ámbito empresarial restringen operaciones y listados a la empresa seleccionada.
- Si intenta operar recursos de otra empresa, responde `403`.

## Fuentes de Contexto de Empresa

### Canal principal (recomendado)

- `Authorization: Bearer <JWT>`
- El backend extrae `empresa_id` desde alguno de estos claims:
  - `empresa_id`
  - `company_id`
  - `tenant_id`

### Canal auxiliar (solo no productivo)

- `X-User-Id: <uuid>`
- `X-Empresa-Id: <uuid>`

Este canal auxiliar se habilita únicamente con `ENVIRONMENT` en:

- `development`
- `dev`
- `test`
- `testing`
- `local`
- `ci`

En `production`, el backend ignora `X-User-Id` y `X-Empresa-Id`; se debe usar `Authorization`.

## Regla de Seguridad Aplicada por Backend

### Límite del Directorio Global

Persona natural, Cliente, TipoCliente, Proveedor Persona y Proveedor Sociedad siguen globales. La Empresa seleccionada no agrega aislamiento ni habilitación comercial por tenant a estos maestros. Sociedad es una identidad jurídica separada con contacto natural mutable; no equivale a Cliente Sociedad. No declarar B2B ni aislamiento comercial completos.

Empleado valida `empresa_id`, Empresa activa y contexto autorizado en listados/escrituras/acciones, pero mantiene un único Empleado global por Persona: no soporta multiempleo. Usuario es una cuenta global por Persona/Rol; la baja Empleado revoca la cuenta asociada y sus sesiones sin desactivar Persona o roles comerciales. Reactivar Empleado no restablece Usuario. Habilitación comercial por Empresa, relaciones laborales múltiples y portal son deuda posterior.

Cuando existe empresa seleccionada en sesión:

1. Los listados filtrados por empresa se acotan automáticamente al contexto actual.
2. Las operaciones sobre recursos con ámbito empresarial de otra empresa retornan `403`; no aplicar esta promesa a maestros globales.
3. Si el request intenta forzar una empresa distinta a la seleccionada, retorna `403`.

Cuando no existe empresa seleccionada en sesión:

- Se mantiene comportamiento legacy (sin aislamiento por empresa en esa solicitud).

## Flujo Recomendado para Frontend

1. Autenticar usuario y obtener JWT.
2. Mostrar selector de empresa al iniciar la sesión.
3. Al elegir empresa, solicitar/renovar JWT con claim `empresa_id` de la empresa elegida.
4. Enviar siempre `Authorization` en cada request.
5. Si backend responde `403` por empresa, forzar cambio de empresa o reautenticación de contexto.

## Contrato de Error para Frontend

<Tabs>
<TabItem value="mismatch" label="403 empresa distinta">

```json
{
  "detail": "La empresa solicitada no coincide con la empresa seleccionada en la sesión."
}
```

</TabItem>
<TabItem value="cross-company" label="403 recurso de otra empresa">

```json
{
  "detail": "No autorizado para operar recursos de otra empresa."
}
```

</TabItem>
<TabItem value="invalid-context" label="403 contexto inválido">

```json
{
  "detail": "Empresa seleccionada inválida en el contexto de sesión."
}
```

</TabItem>
</Tabs>

## Ejemplos de Uso

<Tabs>
<TabItem value="prod" label="Producción (JWT)">

```bash
curl -X GET "http://localhost:8000/api/v1/reportes/ventas/resumen" \
  -H "Authorization: Bearer <JWT_CON_EMPRESA_ID>"
```

</TabItem>
<TabItem value="dev" label="Desarrollo/QA (auxiliar)">

```bash
curl -X GET "http://localhost:8000/api/v1/reportes/ventas/resumen" \
  -H "X-User-Id: 8dd6c39e-c8f3-4ff4-bf31-8f9a70866d0f" \
  -H "X-Empresa-Id: 2dcf92f9-31ab-4cf8-b004-415a911fd7c1"
```

</TabItem>
</Tabs>

## Checklist de Implementación Frontend

- Mostrar empresa activa en cabecera de la aplicación.
- Renovar token al cambiar empresa (no solo refrescar vista).
- No enviar `empresa_id` editable en formularios críticos si la API ya lo deriva por contexto.
- Tratar `403` de empresa como error de contexto de sesión, no como error genérico.
- En ambientes no productivos, usar `X-Empresa-Id` solo para smoke/soporte técnico.

## Implementación Rápida (Frontend)

### 1) Interceptor HTTP para adjuntar contexto

<Tabs>
<TabItem value="axios" label="Axios">

```ts
import axios from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("auth_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;

  // Solo para dev/test si se usa canal auxiliar.
  if (import.meta.env.MODE !== "production") {
    const userId = localStorage.getItem("debug_user_id");
    const empresaId = localStorage.getItem("debug_empresa_id");
    if (userId) config.headers["X-User-Id"] = userId;
    if (empresaId) config.headers["X-Empresa-Id"] = empresaId;
  }
  return config;
});
```

</TabItem>
<TabItem value="fetch" label="Fetch Wrapper">

```ts
export async function apiFetch(path: string, init: RequestInit = {}) {
  const token = localStorage.getItem("auth_token");
  const headers = new Headers(init.headers ?? {});
  if (token) headers.set("Authorization", `Bearer ${token}`);

  if (import.meta.env.MODE !== "production") {
    const userId = localStorage.getItem("debug_user_id");
    const empresaId = localStorage.getItem("debug_empresa_id");
    if (userId) headers.set("X-User-Id", userId);
    if (empresaId) headers.set("X-Empresa-Id", empresaId);
  }

  const res = await fetch(`${import.meta.env.VITE_API_URL}${path}`, {
    ...init,
    headers,
  });
  return res;
}
```

</TabItem>
</Tabs>

### 2) Manejo de `403` por contexto de empresa

```ts
function isCompanyContextError(detail?: string): boolean {
  if (!detail) return false;
  return ["empresa seleccionada", "otra empresa", "contexto de sesión"].some(
    (x) => detail.toLowerCase().includes(x),
  );
}

// En interceptor de respuesta:
// - abrir modal "cambiar empresa"
// - limpiar token/contexto inválido
// - redirigir a selección de empresa
```

### 3) Cambio de empresa (flujo recomendado)

1. Usuario selecciona empresa en UI.
2. Front solicita nuevo token con claim `empresa_id` de la empresa elegida.
3. Reemplaza `auth_token` en storage.
4. Invalida cache de queries (React Query/SWR) y recarga catálogos.
5. Reintenta la última navegación ya con el contexto actualizado.

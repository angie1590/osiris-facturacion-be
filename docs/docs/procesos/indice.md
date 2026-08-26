---
id: procesos-indice
title: "Procesos Operativos ERP (Inicio a Producción)"
sidebar_position: 1
---

# Procesos Operativos ERP (Inicio a Producción)

Esta sección describe el flujo de implementación y operación para arrancar una empresa desde cero en Osiris ERP, con enfoque en front-office y administración.

## Orden recomendado de ejecución

1. [Onboarding y Gobierno Inicial](./procesos-onboarding-gobierno-inicial)
2. [Maestros Comerciales y Directorio](./procesos-maestros-comerciales-directorio)
3. [Inventario y Bodegas](./procesos-inventario-y-bodegas)
4. [Compras, CxP y Retenciones Emitidas](./procesos-compras-cxp-retenciones)
5. [Ventas, CxC y Facturación Electrónica](./procesos-ventas-cxc-facturacion-electronica)
6. [Impresión de Comprobantes](./procesos-impresion-comprobantes)
7. [Reportería y Control Gerencial](./procesos-reporteria-control-gerencial)

## Formato estándar de cada caso de uso

Cada proceso se documenta con:

- `CU`: identificador de caso de uso.
- `Actores`: roles que ejecutan el proceso.
- `Descripción`: objetivo de negocio.
- `Precondiciones`: requisitos de seguridad, datos y configuración.
- `Flujo de Eventos Básico`: pasos operativos para front y administrador.
- `Flujos Alternativos`: validaciones, errores y desvíos.
- `Postcondiciones`: estado esperado de datos y operación.
- `APIs involucradas`: endpoints y enlace directo a la documentación API.

## Regla transversal de sesión multiempresa

Todos los procesos asumen que la empresa activa de sesión está correctamente definida.

- Referencia técnica: [Empresa Seleccionada por Sesión](../api/common/empresa-seleccionada-sesion)

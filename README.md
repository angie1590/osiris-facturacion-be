# Osiris Facturación — Backend

API de facturación electrónica para PyMEs (Ecuador). Basado en la arquitectura de
[osiris-inventario-be](https://github.com/angie1590/osiris-inventario-be): FastAPI + SQLAlchemy async + Alembic.

## Stack
- FastAPI, SQLAlchemy 2.0 (async), Alembic, PostgreSQL, Redis, JWT (access + refresh).
- Multiempresa/multi-sucursal desde el modelo de datos (`empresas` → `sucursales` → `puntos_emision`).
- Firma y envío de comprobantes al SRI vía librería externa [fe-ec](https://github.com/angie1590/fe_ec).

## Desarrollo
```bash
docker compose up --build
```
API en `http://localhost:8001`, docs en `http://localhost:8001/docs`.

## Estructura
```
app/{api,core,models,repositories,schemas,services,utils}/
alembic/
scripts/  (entrypoint.sh, seed.py)
tests/
```

## Roadmap
Ver plan de módulos (empresa/sucursal, personas, SRI/impuestos, inventario, compras, ventas/facturación, reportes)
en el histórico de conversación del proyecto / issues del repo.

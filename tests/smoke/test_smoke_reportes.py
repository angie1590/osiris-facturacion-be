from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest
from sqlmodel import SQLModel, select

from osiris.modules.common.persona.entity import Persona
from osiris.modules.common.proveedor_sociedad.entity import ProveedorSociedad
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.common.usuario.entity import Usuario
from osiris.modules.compras.models import (
    Compra,
    CuentaPorPagar,
    Retencion,
    RetencionDetalle,
)
from osiris.modules.ventas.models import (
    RetencionRecibida,
    RetencionRecibidaDetalle,
    Venta,
)
from osiris.modules.inventario.producto.entity import Producto


pytestmark = pytest.mark.smoke


def _uuid_or_random(value: UUID | None) -> UUID:
    return value if value is not None else uuid4()


@pytest.mark.smoke
def test_smoke_reporteria_endpoints(client, db_session):
    # Asegura tablas requeridas por joins de reportes para evitar 500 por "no such table".
    SQLModel.metadata.create_all(
        db_session.get_bind(),
        tables=[
            Persona.__table__,
            Usuario.__table__,
            ProveedorSociedad.__table__,
            Compra.__table__,
            CuentaPorPagar.__table__,
            Retencion.__table__,
            RetencionDetalle.__table__,
            RetencionRecibida.__table__,
            RetencionRecibidaDetalle.__table__,
        ],
    )

    producto_id_db = db_session.exec(
        select(Producto.id).where(Producto.activo.is_(True))
    ).first()
    sucursal_id_db = db_session.exec(
        select(Sucursal.id).where(Sucursal.activo.is_(True), Sucursal.es_matriz.is_(True))
    ).first()
    if sucursal_id_db is None:
        sucursal_id_db = db_session.exec(
            select(Sucursal.id).where(Sucursal.activo.is_(True))
        ).first()
    cliente_id_db = db_session.exec(
        select(Venta.cliente_id).where(Venta.activo.is_(True), Venta.cliente_id.is_not(None))
    ).first()

    producto_id = _uuid_or_random(producto_id_db)
    sucursal_id = _uuid_or_random(sucursal_id_db)
    cliente_id = _uuid_or_random(cliente_id_db)
    assert isinstance(cliente_id, UUID)

    fecha_fin = date.today()
    fecha_inicio = fecha_fin - timedelta(days=365)

    requests = [
        ("/api/v1/reportes/ventas/resumen", {"fecha_inicio": fecha_inicio.isoformat(), "fecha_fin": fecha_fin.isoformat(), "sucursal_id": str(sucursal_id)}),
        ("/api/v1/reportes/ventas/top-productos", None),
        ("/api/v1/reportes/ventas/tendencias", {"fecha_inicio": fecha_inicio.isoformat(), "fecha_fin": fecha_fin.isoformat(), "agrupacion": "DIARIA"}),
        ("/api/v1/reportes/ventas/por-vendedor", {"fecha_inicio": fecha_inicio.isoformat(), "fecha_fin": fecha_fin.isoformat()}),
        ("/api/v1/reportes/impuestos/mensual", {"mes": 2, "anio": 2026}),
        ("/api/v1/reportes/inventario/valoracion", None),
        ("/api/v1/reportes/cartera/cobrar", None),
        ("/api/v1/reportes/cartera/pagar", None),
        ("/api/v1/reportes/caja/cierre-diario", {"fecha": fecha_fin.isoformat()}),
        (f"/api/v1/reportes/inventario/kardex/{producto_id}", None),
        ("/api/v1/reportes/compras/por-proveedor", {"fecha_inicio": fecha_inicio.isoformat(), "fecha_fin": fecha_fin.isoformat()}),
        ("/api/v1/reportes/sri/monitor-estados", {"fecha_inicio": fecha_inicio.isoformat(), "fecha_fin": fecha_fin.isoformat()}),
        ("/api/v1/reportes/rentabilidad/por-cliente", {"fecha_inicio": fecha_inicio.isoformat(), "fecha_fin": fecha_fin.isoformat()}),
        ("/api/v1/reportes/rentabilidad/transacciones", {"fecha_inicio": fecha_inicio.isoformat(), "fecha_fin": fecha_fin.isoformat()}),
    ]

    for path, params in requests:
        response = client.get(path, params=params)
        assert response.status_code in (200, 404), f"{path} -> {response.status_code}: {response.text}"

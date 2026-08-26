from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.modules.reportes.schemas import (
    AgrupacionTendencia,
    ReporteCajaCierreDiarioRead,
    ReporteCarteraCobrarItemRead,
    ReporteCarteraPagarItemRead,
    ReporteComprasPorProveedorRead,
    ReporteImpuestosMensualRead,
    ReporteInventarioKardexRead,
    ReporteInventarioValoracionRead,
    ReporteMonitorSRIEstadoRead,
    ReporteRentabilidadClienteRead,
    ReporteRentabilidadTransaccionRead,
    ReporteTopProductoRead,
    ReporteVentasPorVendedorRead,
    ReporteVentasResumenRead,
    ReporteVentasTendenciaRead,
)
from osiris.modules.reportes.services.reporte_caja_service import ReporteCajaService
from osiris.modules.reportes.services.reporte_cartera_service import ReporteCarteraService
from osiris.modules.reportes.services.reporte_compras_service import ReporteComprasService
from osiris.modules.reportes.services.reporte_inventario_service import ReporteInventarioService
from osiris.modules.reportes.services.reporte_monitor_sri_service import ReporteMonitorSRIService
from osiris.modules.reportes.services.reporte_tributario_service import ReporteTributarioService
from osiris.modules.reportes.services.reportes_service import ReportesVentasService


REPORT_RESPONSES = {
    400: {"description": "Parámetros inválidos para la consulta del reporte."},
    422: {"description": "Error de validación de parámetros de entrada."},
}

router = APIRouter(prefix="/api/v1/reportes", tags=["Reportes"])
reportes_ventas_service = ReportesVentasService()
reporte_tributario_service = ReporteTributarioService()
reporte_inventario_service = ReporteInventarioService()
reporte_cartera_service = ReporteCarteraService()
reporte_caja_service = ReporteCajaService()
reporte_compras_service = ReporteComprasService()
reporte_monitor_sri_service = ReporteMonitorSRIService()


@router.get("/ventas/resumen", response_model=ReporteVentasResumenRead, summary="Resumen de ventas", responses=REPORT_RESPONSES)
def obtener_reporte_ventas_resumen(
    fecha_inicio: date = Query(..., description="Fecha inicial del rango"),
    fecha_fin: date = Query(..., description="Fecha final del rango"),
    punto_emision_id: UUID | None = Query(default=None),
    sucursal_id: UUID | None = Query(default=None),
    session: Session = Depends(get_session),
):
    return reportes_ventas_service.obtener_resumen_ventas(
        session,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        punto_emision_id=punto_emision_id,
        sucursal_id=sucursal_id,
    )


@router.get("/ventas/top-productos", response_model=list[ReporteTopProductoRead], summary="Top productos vendidos", responses=REPORT_RESPONSES)
def obtener_reporte_top_productos_ventas(
    fecha_inicio: date | None = Query(default=None, description="Fecha inicial opcional"),
    fecha_fin: date | None = Query(default=None, description="Fecha final opcional"),
    punto_emision_id: UUID | None = Query(default=None),
    limite: int = Query(default=10, ge=1, le=100),
    session: Session = Depends(get_session),
):
    return reportes_ventas_service.obtener_top_productos(
        session,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        punto_emision_id=punto_emision_id,
        limite=limite,
    )


@router.get("/ventas/tendencias", response_model=list[ReporteVentasTendenciaRead], summary="Tendencias de ventas", responses=REPORT_RESPONSES)
def obtener_reporte_tendencias_ventas(
    fecha_inicio: date = Query(..., description="Fecha inicial del rango"),
    fecha_fin: date = Query(..., description="Fecha final del rango"),
    agrupacion: AgrupacionTendencia = Query(default=AgrupacionTendencia.DIARIA),
    session: Session = Depends(get_session),
):
    return reportes_ventas_service.obtener_tendencias_ventas(
        session,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        agrupacion=agrupacion,
    )


@router.get("/ventas/por-vendedor", response_model=list[ReporteVentasPorVendedorRead], summary="Rendimiento por vendedor", responses=REPORT_RESPONSES)
def obtener_reporte_ventas_por_vendedor(
    fecha_inicio: date | None = Query(default=None, description="Fecha inicial opcional"),
    fecha_fin: date | None = Query(default=None, description="Fecha final opcional"),
    session: Session = Depends(get_session),
):
    return reportes_ventas_service.obtener_ventas_por_vendedor(
        session,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )


@router.get("/compras/por-proveedor", response_model=list[ReporteComprasPorProveedorRead], summary="Volumen de compras por proveedor", responses=REPORT_RESPONSES)
def obtener_reporte_compras_por_proveedor(
    fecha_inicio: date = Query(..., description="Fecha inicial del rango"),
    fecha_fin: date = Query(..., description="Fecha final del rango"),
    sucursal_id: UUID | None = Query(default=None),
    session: Session = Depends(get_session),
):
    return reporte_compras_service.obtener_compras_por_proveedor(
        session,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        sucursal_id=sucursal_id,
    )


@router.get("/sri/monitor-estados", response_model=list[ReporteMonitorSRIEstadoRead], summary="Monitor de estados SRI", responses=REPORT_RESPONSES)
def obtener_reporte_monitor_estados_sri(
    fecha_inicio: date = Query(..., description="Fecha inicial del rango"),
    fecha_fin: date = Query(..., description="Fecha final del rango"),
    sucursal_id: UUID | None = Query(default=None),
    session: Session = Depends(get_session),
):
    return reporte_monitor_sri_service.obtener_monitor_estados(
        session,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        sucursal_id=sucursal_id,
    )


@router.get("/rentabilidad/por-cliente", response_model=list[ReporteRentabilidadClienteRead], summary="Rentabilidad por cliente", responses=REPORT_RESPONSES)
def obtener_reporte_rentabilidad_por_cliente(
    fecha_inicio: date = Query(..., description="Fecha inicial del rango"),
    fecha_fin: date = Query(..., description="Fecha final del rango"),
    session: Session = Depends(get_session),
):
    return reportes_ventas_service.obtener_rentabilidad_por_cliente(
        session,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )


@router.get("/rentabilidad/transacciones", response_model=list[ReporteRentabilidadTransaccionRead], summary="Rentabilidad transaccional", responses=REPORT_RESPONSES)
def obtener_reporte_rentabilidad_transaccional(
    fecha_inicio: date = Query(..., description="Fecha inicial del rango"),
    fecha_fin: date = Query(..., description="Fecha final del rango"),
    session: Session = Depends(get_session),
):
    return reportes_ventas_service.obtener_rentabilidad_transaccional(
        session,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )


@router.get("/impuestos/mensual", response_model=ReporteImpuestosMensualRead, summary="Resumen mensual tributario (Pre-104)", responses=REPORT_RESPONSES)
def obtener_reporte_impuestos_mensual(
    mes: int = Query(..., ge=1, le=12, description="Mes fiscal (1-12)"),
    anio: int = Query(..., ge=2000, le=2100, description="Anio fiscal"),
    sucursal_id: UUID | None = Query(default=None),
    session: Session = Depends(get_session),
):
    return reporte_tributario_service.obtener_reporte_mensual_impuestos(
        session,
        mes=mes,
        anio=anio,
        sucursal_id=sucursal_id,
    )


@router.get("/inventario/valoracion", response_model=ReporteInventarioValoracionRead, summary="Valoración de inventario", responses=REPORT_RESPONSES)
def obtener_reporte_valoracion_inventario(session: Session = Depends(get_session)):
    return reporte_inventario_service.obtener_valoracion_inventario(session)


@router.get("/inventario/kardex/{producto_id}", response_model=ReporteInventarioKardexRead, summary="Kárdex histórico NIIF", responses=REPORT_RESPONSES)
def obtener_reporte_kardex_inventario(
    producto_id: UUID,
    fecha_inicio: date | None = Query(default=None, description="Fecha inicial opcional"),
    fecha_fin: date | None = Query(default=None, description="Fecha final opcional"),
    sucursal_id: UUID | None = Query(default=None, description="Filtro opcional por sucursal"),
    session: Session = Depends(get_session),
):
    return reporte_inventario_service.obtener_kardex_historico(
        session,
        producto_id=producto_id,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        sucursal_id=sucursal_id,
    )


@router.get("/cartera/cobrar", response_model=list[ReporteCarteraCobrarItemRead], summary="Cartera por cobrar", responses=REPORT_RESPONSES)
def obtener_reporte_cartera_cobrar(session: Session = Depends(get_session)):
    return reporte_cartera_service.obtener_cartera_cobrar(session)


@router.get("/cartera/pagar", response_model=list[ReporteCarteraPagarItemRead], summary="Cartera por pagar", responses=REPORT_RESPONSES)
def obtener_reporte_cartera_pagar(session: Session = Depends(get_session)):
    return reporte_cartera_service.obtener_cartera_pagar(session)


@router.get("/caja/cierre-diario", response_model=ReporteCajaCierreDiarioRead, summary="Cierre diario de caja", responses=REPORT_RESPONSES)
def obtener_reporte_cierre_caja_diario(
    fecha: date = Query(default_factory=date.today, description="Fecha del arqueo"),
    usuario_id: UUID | None = Query(default=None, description="Filtro opcional por usuario"),
    sucursal_id: UUID | None = Query(default=None),
    session: Session = Depends(get_session),
):
    return reporte_caja_service.obtener_cierre_diario(
        session,
        fecha=fecha,
        usuario_id=usuario_id,
        sucursal_id=sucursal_id,
    )

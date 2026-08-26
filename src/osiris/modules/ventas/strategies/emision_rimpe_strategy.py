from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session

from osiris.modules.common.empresa.entity import Empresa, RegimenTributario
from osiris.modules.common.punto_emision.entity import PuntoEmision
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.sri.core_sri.models import TipoEmisionVenta
from osiris.modules.sri.core_sri.all_schemas import VentaCreate, q2


class EmisionRimpeStrategy:
    @staticmethod
    def validar_iva_rimpe_negocio_popular(
        payload: VentaCreate,
        *,
        tipo_emision: TipoEmisionVenta,
    ) -> None:
        for detalle in payload.detalles:
            if detalle.es_actividad_excluida:
                continue
            iva = detalle.iva_impuesto()
            if iva and q2(iva.tarifa) > Decimal("0.00"):
                if tipo_emision == TipoEmisionVenta.ELECTRONICA:
                    raise HTTPException(
                        status_code=400,
                        detail="Los Negocios Populares solo pueden facturar electrónicamente con tarifa 0%",
                    )
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Los Negocios Populares solo pueden facturar con tarifa 0% "
                        "de IVA para sus actividades incluyentes"
                    ),
                )

    def resolver_contexto_tributario(
        self,
        session: Session,
        payload: VentaCreate,
    ) -> tuple[UUID | None, RegimenTributario, TipoEmisionVenta]:
        empresa_id = payload.empresa_id
        regimen_emisor = payload.regimen_emisor

        if empresa_id is None and payload.punto_emision_id is not None:
            punto = session.get(PuntoEmision, payload.punto_emision_id)
            if not punto or not punto.activo:
                raise HTTPException(status_code=404, detail="Punto de emisión no encontrado o inactivo.")
            sucursal = session.get(Sucursal, punto.sucursal_id)
            if not sucursal or not sucursal.activo:
                raise HTTPException(status_code=404, detail="Sucursal del punto de emisión no encontrada o inactiva.")
            empresa_id = sucursal.empresa_id

        if empresa_id is not None:
            empresa = session.get(Empresa, empresa_id)
            if not empresa or not empresa.activo:
                raise HTTPException(status_code=404, detail="Empresa no encontrada o inactiva.")
            regimen_emisor = empresa.regimen

        tipo_emision = payload.tipo_emision
        if regimen_emisor == RegimenTributario.RIMPE_NEGOCIO_POPULAR:
            tiene_actividad_excluida = any(d.es_actividad_excluida for d in payload.detalles)
            tipo_emision_explicito = "tipo_emision" in payload.model_fields_set
            if not tipo_emision_explicito or tipo_emision is None:
                tipo_emision = (
                    TipoEmisionVenta.ELECTRONICA if tiene_actividad_excluida else TipoEmisionVenta.NOTA_VENTA_FISICA
                )
            self.validar_iva_rimpe_negocio_popular(payload, tipo_emision=tipo_emision)
        else:
            if tipo_emision == TipoEmisionVenta.NOTA_VENTA_FISICA:
                raise HTTPException(
                    status_code=400,
                    detail="NOTA_VENTA_FISICA solo está permitido para régimen RIMPE_NEGOCIO_POPULAR.",
                )
            tipo_emision = tipo_emision or TipoEmisionVenta.ELECTRONICA

        return empresa_id, regimen_emisor, tipo_emision

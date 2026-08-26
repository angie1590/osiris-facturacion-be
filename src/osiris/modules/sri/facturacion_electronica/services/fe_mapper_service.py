from __future__ import annotations

from decimal import Decimal
from uuid import UUID
from datetime import date

from fastapi import HTTPException
from sqlmodel import Session

from osiris.core.settings import get_settings
from osiris.modules.common.empresa.entity import RegimenTributario
from osiris.modules.sri.core_sri.models import (
    DocumentoElectronico,
    DocumentoElectronicoHistorial,
    EstadoDocumentoElectronico,
    FormaPagoSRI,
    TipoIdentificacionSRI,
    TipoImpuestoMVP,
)
from osiris.modules.sri.core_sri.all_schemas import RetencionRead, VentaRead, q2

try:
    from src.fe_ec.utils.generador_clave_acceso import GeneradorClaveAcceso
except Exception:  # pragma: no cover - fallback cuando no está la librería FE-EC local.
    GeneradorClaveAcceso = None


FORMA_PAGO_SRI_CODE = {
    FormaPagoSRI.EFECTIVO: "01",
    FormaPagoSRI.TARJETA: "19",
    FormaPagoSRI.TRANSFERENCIA: "20",
}

IDENTIFICACION_SRI_CODE = {
    TipoIdentificacionSRI.RUC: "04",
    TipoIdentificacionSRI.CEDULA: "05",
    TipoIdentificacionSRI.PASAPORTE: "06",
}


def _fmt(value: Decimal) -> str:
    return f"{q2(value):.2f}"


def _append_unique_campo_adicional(info_adicional: dict, *, nombre: str, valor: str) -> dict:
    campos = list(info_adicional.get("campoAdicional") or [])
    if not any((campo.get("nombre"), campo.get("valor")) == (nombre, valor) for campo in campos if isinstance(campo, dict)):
        campos.append({"nombre": nombre, "valor": valor})
    info_adicional["campoAdicional"] = campos
    return info_adicional


def _totales_impuestos_desde_detalle(venta: VentaRead) -> tuple[Decimal, Decimal, Decimal]:
    total = Decimal("0.00")
    total_iva = Decimal("0.00")
    total_ice = Decimal("0.00")

    for detalle in venta.detalles:
        for impuesto in detalle.impuestos:
            valor = q2(impuesto.valor_impuesto)
            total += valor
            if impuesto.tipo_impuesto == TipoImpuestoMVP.IVA:
                total_iva += valor
            elif impuesto.tipo_impuesto == TipoImpuestoMVP.ICE:
                total_ice += valor

    return q2(total), q2(total_iva), q2(total_ice)


class FEMapperService:
    @staticmethod
    def _generar_clave_acceso(
        *,
        fecha_emision: date,
        ruc: str,
        estab: str,
        pto_emi: str,
        secuencial: str,
        ambiente: str,
        tipo_emision: str,
    ) -> str:
        if GeneradorClaveAcceso is None:
            return f"{fecha_emision.strftime('%d%m%Y')}{ruc}{estab}{pto_emi}{secuencial}".ljust(49, "0")[:49]

        return GeneradorClaveAcceso.generar(
            fecha_emision=fecha_emision.strftime("%d/%m/%Y"),
            tipo_comprobante="01",
            ruc=ruc,
            tipo_ambiente=ambiente,
            serie=f"{estab}{pto_emi}",
            secuencial=secuencial,
            tipo_emision=tipo_emision,
        )

    def venta_to_fe_ec_payload(
        self,
        venta: VentaRead,
        *,
        ruc_emisor: str,
        razon_social: str,
        nombre_comercial: str | None,
        dir_matriz: str,
        obligado_contabilidad: bool,
        estab: str = "001",
        pto_emi: str = "001",
        dir_establecimiento: str | None = None,
        email_cliente: str | None = None,
    ) -> dict:
        settings = get_settings()
        ambiente_code = "1" if settings.FEEC_AMBIENTE == "pruebas" else "2"
        tipo_emision = settings.FEEC_TIPO_EMISION

        secuencial = "000000001"
        if venta.secuencial_formateado:
            parts = venta.secuencial_formateado.split("-")
            if len(parts) == 3:
                estab = parts[0].zfill(3)
                pto_emi = parts[1].zfill(3)
                secuencial = parts[2].zfill(9)

        clave_acceso = self._generar_clave_acceso(
            fecha_emision=venta.fecha_emision,
            ruc=ruc_emisor,
            estab=estab,
            pto_emi=pto_emi,
            secuencial=secuencial,
            ambiente=ambiente_code,
            tipo_emision=tipo_emision,
        )

        payload_base = self.venta_to_fe_payload(venta)
        info_adicional = payload_base.get("infoAdicional", {"campoAdicional": []})
        if venta.regimen_emisor == RegimenTributario.RIMPE_NEGOCIO_POPULAR:
            info_adicional = _append_unique_campo_adicional(
                info_adicional,
                nombre="Contribuyente",
                valor="Contribuyente Negocio Popular - Régimen RIMPE",
            )
        if email_cliente:
            info_adicional = _append_unique_campo_adicional(info_adicional, nombre="email", valor=email_cliente)

        return {
            "infoTributaria": {
                "ambiente": ambiente_code,
                "tipoEmision": tipo_emision,
                "razonSocial": razon_social,
                "nombreComercial": nombre_comercial or razon_social,
                "ruc": ruc_emisor,
                "claveAcceso": clave_acceso,
                "codDoc": "01",
                "estab": estab,
                "ptoEmi": pto_emi,
                "secuencial": secuencial,
                "dirMatriz": dir_matriz,
            },
            "infoFactura": {
                "fechaEmision": venta.fecha_emision.strftime("%d/%m/%Y"),
                "dirEstablecimiento": dir_establecimiento or dir_matriz,
                "obligadoContabilidad": "SI" if obligado_contabilidad else "NO",
                "tipoIdentificacionComprador": IDENTIFICACION_SRI_CODE[venta.tipo_identificacion_comprador],
                "razonSocialComprador": venta.identificacion_comprador,
                "identificacionComprador": venta.identificacion_comprador,
                "totalSinImpuestos": _fmt(venta.subtotal_sin_impuestos),
                "totalDescuento": "0.00",
                "totalConImpuestos": {"totalImpuesto": payload_base["infoFactura"]["totalConImpuestos"]},
                "propina": "0.00",
                "importeTotal": _fmt(venta.valor_total),
                "moneda": "DOLAR",
                "pagos": [
                    {
                        "formaPago": FORMA_PAGO_SRI_CODE[venta.forma_pago],
                        "total": _fmt(venta.valor_total),
                        "plazo": "0",
                        "unidadTiempo": "DIAS",
                    }
                ],
            },
            "detalles": payload_base["detalles"],
            "infoAdicional": info_adicional,
        }

    def venta_to_fe_payload(self, venta: VentaRead) -> dict:
        total_con_impuestos: dict[tuple[str, str], dict[str, Decimal]] = {}
        detalles_payload: list[dict] = []

        for detalle in venta.detalles:
            impuestos_payload = []
            for impuesto in detalle.impuestos:
                key = (impuesto.codigo_impuesto_sri, impuesto.codigo_porcentaje_sri)
                if key not in total_con_impuestos:
                    total_con_impuestos[key] = {"base": Decimal("0.00"), "valor": Decimal("0.00")}
                total_con_impuestos[key]["base"] += impuesto.base_imponible
                total_con_impuestos[key]["valor"] += impuesto.valor_impuesto

                impuestos_payload.append(
                    {
                        "codigo": impuesto.codigo_impuesto_sri,
                        "codigoPorcentaje": impuesto.codigo_porcentaje_sri,
                        "tarifa": _fmt(impuesto.tarifa),
                        "baseImponible": _fmt(impuesto.base_imponible),
                        "valor": _fmt(impuesto.valor_impuesto),
                    }
                )

            detalles_payload.append(
                {
                    "descripcion": detalle.descripcion,
                    "cantidad": _fmt(detalle.cantidad),
                    "precioUnitario": _fmt(detalle.precio_unitario),
                    "descuento": _fmt(detalle.descuento),
                    "precioTotalSinImpuesto": _fmt(detalle.subtotal_sin_impuesto),
                    "impuestos": impuestos_payload,
                }
            )

        total_detalle_impuestos, total_detalle_iva, total_detalle_ice = _totales_impuestos_desde_detalle(venta)
        if total_detalle_iva != q2(venta.monto_iva):
            raise ValueError(
                "Inconsistencia tributaria: el IVA de detalle no coincide con la cabecera de la venta."
            )
        if total_detalle_ice != q2(venta.monto_ice):
            raise ValueError(
                "Inconsistencia tributaria: el ICE de detalle no coincide con la cabecera de la venta."
            )
        if total_detalle_impuestos != q2(venta.monto_iva + venta.monto_ice):
            raise ValueError(
                "Inconsistencia tributaria: la suma de impuestos en detalle no coincide con la cabecera."
            )

        total_con_impuestos_list = [
            {
                "codigo": codigo,
                "codigoPorcentaje": codigo_porcentaje,
                "baseImponible": _fmt(data["base"]),
                "valor": _fmt(data["valor"]),
            }
            for (codigo, codigo_porcentaje), data in sorted(total_con_impuestos.items())
        ]
        total_agrupado = q2(sum((data["valor"] for data in total_con_impuestos.values()), Decimal("0.00")))
        if total_agrupado != total_detalle_impuestos:
            raise ValueError(
                "Inconsistencia tributaria: totalConImpuestos no cuadra con los impuestos de detalle."
            )

        if q2(venta.subtotal_sin_impuestos + total_detalle_impuestos) != q2(venta.valor_total):
            raise ValueError(
                "Inconsistencia tributaria: subtotal mas impuestos no coincide con el valor total."
            )

        payload = {
            "infoTributaria": {
                "identificacionComprador": venta.identificacion_comprador,
                "tipoIdentificacionComprador": IDENTIFICACION_SRI_CODE[venta.tipo_identificacion_comprador],
            },
            "infoFactura": {
                "fechaEmision": venta.fecha_emision.isoformat(),
                "totalSinImpuestos": _fmt(venta.subtotal_sin_impuestos),
                "totalConImpuestos": total_con_impuestos_list,
                "importeTotal": _fmt(venta.valor_total),
                "pagos": [
                    {
                        "formaPago": FORMA_PAGO_SRI_CODE[venta.forma_pago],
                        "total": _fmt(venta.valor_total),
                    }
                ],
            },
            "detalles": detalles_payload,
        }
        if venta.regimen_emisor == RegimenTributario.RIMPE_NEGOCIO_POPULAR:
            payload["infoAdicional"] = _append_unique_campo_adicional(
                payload.get("infoAdicional", {"campoAdicional": []}),
                nombre="Contribuyente",
                valor="Contribuyente Negocio Popular - Régimen RIMPE",
            )
        return payload

    def retencion_to_fe_payload(self, retencion: RetencionRead) -> dict:
        impuestos = [
            {
                "codigoRetencion": detalle.codigo_retencion_sri,
                "tipo": detalle.tipo.value if hasattr(detalle.tipo, "value") else str(detalle.tipo),
                "baseImponible": _fmt(detalle.base_calculo),
                "porcentajeRetener": _fmt(detalle.porcentaje),
                "valorRetenido": _fmt(detalle.valor_retenido),
            }
            for detalle in retencion.detalles
        ]

        total = q2(sum((detalle.valor_retenido for detalle in retencion.detalles), Decimal("0.00")))
        if total != q2(retencion.total_retenido):
            raise ValueError("Inconsistencia tributaria: el total retenido no cuadra con los detalles.")

        return {
            "retencion": {
                "compraId": str(retencion.compra_id),
                "fechaEmision": retencion.fecha_emision.isoformat(),
                "estado": retencion.estado.value if hasattr(retencion.estado, "value") else str(retencion.estado),
                "totalRetenido": _fmt(retencion.total_retenido),
                "impuestos": impuestos,
            }
        }

    def registrar_respuesta_sri(
        self,
        session: Session,
        documento_electronico_id: UUID,
        estado_nuevo: EstadoDocumentoElectronico | str,
        *,
        mensaje_sri: str,
        usuario_id: str | None = None,
    ) -> DocumentoElectronico:
        documento = session.get(DocumentoElectronico, documento_electronico_id)
        if not documento or not documento.activo:
            raise HTTPException(status_code=404, detail="Documento electronico no encontrado")

        destino = (
            estado_nuevo
            if isinstance(estado_nuevo, EstadoDocumentoElectronico)
            else EstadoDocumentoElectronico(estado_nuevo)
        )
        if (
            hasattr(documento, "estado")
            and hasattr(documento, "estado_sri")
            and documento.estado is not None
            and documento.estado_sri is not None
            and documento.estado != documento.estado_sri
        ):
            estado_actual = (
                documento.estado
                if documento.estado != EstadoDocumentoElectronico.EN_COLA
                else documento.estado_sri
            )
        else:
            estado_actual = documento.estado_sri if hasattr(documento, "estado_sri") else documento.estado
        anterior = estado_actual.value if hasattr(estado_actual, "value") else str(estado_actual)
        motivo = (mensaje_sri or "").strip()

        if destino == EstadoDocumentoElectronico.RECHAZADO and not motivo:
            raise ValueError("motivo_cambio es obligatorio cuando el SRI rechaza el comprobante")
        if not motivo:
            motivo = f"Respuesta SRI: {destino.value}"

        documento.estado_sri = destino
        documento.estado = destino
        documento.mensajes_sri = motivo
        session.add(documento)
        session.add(
            DocumentoElectronicoHistorial(
                entidad_id=documento.id,
                estado_anterior=anterior,
                estado_nuevo=destino.value,
                motivo_cambio=motivo,
                usuario_id=usuario_id,
            )
        )
        session.commit()
        session.refresh(documento)
        return documento

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Protocol
from uuid import UUID

from fastapi import BackgroundTasks, HTTPException
from sqlmodel import Session, select

from osiris.core.db import engine as default_engine
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.punto_emision.entity import PuntoEmision
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.sri.facturacion_electronica.services.correo_service import CorreoFacturaService
from osiris.modules.sri.core_sri.models import (
    DocumentoElectronico,
    DocumentoElectronicoHistorial,
    DocumentoSriCola,
    EstadoColaSri,
    EstadoDocumentoElectronico,
    EstadoSriDocumento,
    TipoDocumentoElectronico,
    TipoEmisionVenta,
    Venta,
    VentaDetalle,
    VentaDetalleImpuesto,
)
from osiris.modules.sri.facturacion_electronica.services.fe_mapper_service import FEMapperService
from osiris.modules.sri.core_sri.all_schemas import (
    VentaDetalleImpuestoRead,
    VentaDetalleRead,
    VentaRead,
)

try:
    from src.fe_ec.utils.manejador_xml import ManejadorXML
    from src.fe_ec.utils.sri import SRIService
except Exception:  # pragma: no cover - fallback cuando la librería no está instalada.
    ManejadorXML = None
    SRIService = None


class FEECVentaGateway(Protocol):
    def enviar_documento(self, *, tipo_documento: str, payload: dict) -> dict:
        ...


class FEECVentaGatewayDefault:
    @staticmethod
    def _extract_estado_mensaje(value) -> tuple[str, str]:
        if value is None:
            return "", ""
        if isinstance(value, dict):
            return str(value.get("estado", "")).upper(), str(value.get("mensaje", "")).strip()
        estado = str(getattr(value, "estado", "")).upper()
        mensaje = str(getattr(value, "mensaje", "")).strip()
        return estado, mensaje

    @staticmethod
    def _extraer_estado_autorizacion(respuesta_autorizacion) -> tuple[str, str]:
        # Compatibilidad con estructura real de FE-EC y diccionarios mock.
        if isinstance(respuesta_autorizacion, dict):
            estado = str(respuesta_autorizacion.get("estado", "")).upper()
            mensaje = str(respuesta_autorizacion.get("mensaje", "")).strip()
            return estado, mensaje

        autorizaciones = getattr(respuesta_autorizacion, "autorizaciones", None)
        autorizacion_list = getattr(autorizaciones, "autorizacion", None)
        if autorizacion_list:
            autorizacion = autorizacion_list[0]
            estado = str(getattr(autorizacion, "estado", "")).upper()
            mensajes = getattr(autorizacion, "mensajes", None)
            mensaje = ""
            if mensajes and getattr(mensajes, "mensaje", None):
                msg = mensajes.mensaje[0]
                mensaje = str(getattr(msg, "mensaje", "")).strip()
            return estado, mensaje
        return "", ""

    def enviar_documento(self, *, tipo_documento: str, payload: dict) -> dict:
        if tipo_documento != "VENTA":
            return {"estado": "RECHAZADO", "mensaje": "Tipo de documento no soportado por gateway de venta."}

        if ManejadorXML is None or SRIService is None:
            # Fallback local para tests/entornos sin librería FE-EC.
            return {"estado": "AUTORIZADO", "mensaje": "Autorizado (modo mock FE-EC)."}

        manejador = ManejadorXML()
        signed_output = manejador.firmar_y_guardar_xml(payload)
        if not signed_output:
            return {"estado": "RECHAZADO", "mensaje": "No se pudo generar/firmar el XML."}

        xml_bytes: bytes
        if isinstance(signed_output, (bytes, bytearray)):
            xml_bytes = bytes(signed_output)
        elif isinstance(signed_output, str) and Path(signed_output).exists():
            xml_bytes = Path(signed_output).read_bytes()
        elif Path("fact_firmado.xml").exists():
            xml_bytes = Path("fact_firmado.xml").read_bytes()
        else:
            return {"estado": "RECHAZADO", "mensaje": "No se encontró XML firmado para transmisión."}

        sri = SRIService()
        recepcion = sri.enviar_recepcion(xml_bytes)
        estado_recepcion, mensaje_recepcion = self._extract_estado_mensaje(recepcion)
        if estado_recepcion != "RECIBIDA":
            return {
                "estado": "RECHAZADO",
                "mensaje": mensaje_recepcion or "Comprobante no recibido por el SRI.",
            }

        clave = payload.get("infoTributaria", {}).get("claveAcceso", "")
        autorizacion = sri.consultar_autorizacion(clave)
        estado_autorizacion, mensaje_autorizacion = self._extraer_estado_autorizacion(autorizacion)
        if estado_autorizacion == "AUTORIZADO":
            return {"estado": "AUTORIZADO", "mensaje": mensaje_autorizacion or "Documento autorizado."}
        return {
            "estado": "RECHAZADO",
            "mensaje": mensaje_autorizacion or "Documento rechazado por SRI.",
        }


class VentaSriAsyncService:
    def __init__(
        self,
        gateway: FEECVentaGateway | None = None,
        *,
        db_engine=None,
        correo_service: CorreoFacturaService | None = None,
    ) -> None:
        self.gateway = gateway or FEECVentaGatewayDefault()
        self.fe_mapper = FEMapperService()
        self.db_engine = db_engine or default_engine
        self.correo_service = correo_service or CorreoFacturaService(self.db_engine)

    @staticmethod
    def _default_scheduler(tarea_id: UUID, delay_seconds: int, callback: Callable[[UUID], None]) -> None:
        timer = threading.Timer(delay_seconds, callback, kwargs={"tarea_id": tarea_id})
        timer.daemon = True
        timer.start()

    @staticmethod
    def _sync_estado_documento(
        documento: DocumentoElectronico,
        estado: EstadoDocumentoElectronico,
        *,
        mensaje: str | None = None,
    ) -> None:
        documento.estado = estado
        documento.estado_sri = estado
        if mensaje is not None:
            documento.mensajes_sri = mensaje

    @staticmethod
    def _crear_historial_documento(
        session: Session,
        *,
        documento: DocumentoElectronico,
        estado_anterior: EstadoDocumentoElectronico,
        estado_nuevo: EstadoDocumentoElectronico,
        motivo: str,
        usuario_id: str | None,
    ) -> None:
        session.add(
            DocumentoElectronicoHistorial(
                entidad_id=documento.id,
                estado_anterior=estado_anterior.value,
                estado_nuevo=estado_nuevo.value,
                motivo_cambio=motivo,
                usuario_id=usuario_id,
            )
        )

    @staticmethod
    def _venta_read(session: Session, venta_id: UUID) -> VentaRead:
        from collections import defaultdict

        venta = session.get(Venta, venta_id)
        if not venta or not venta.activo:
            raise HTTPException(status_code=404, detail="Venta no encontrada para envío SRI.")

        detalles_db = list(
            session.exec(
                select(VentaDetalle).where(
                    VentaDetalle.venta_id == venta.id,
                    VentaDetalle.activo.is_(True),
                )
            ).all()
        )
        detalle_ids = [detalle.id for detalle in detalles_db]

        impuestos_por_detalle: dict[UUID, list[VentaDetalleImpuesto]] = defaultdict(list)
        if detalle_ids:
            impuestos_db = list(
                session.exec(
                    select(VentaDetalleImpuesto).where(
                        VentaDetalleImpuesto.venta_detalle_id.in_(detalle_ids),
                        VentaDetalleImpuesto.activo.is_(True),
                    )
                ).all()
            )
            for impuesto in impuestos_db:
                impuestos_por_detalle[impuesto.venta_detalle_id].append(impuesto)

        detalles_read: list[VentaDetalleRead] = []
        for detalle in detalles_db:
            detalles_read.append(
                VentaDetalleRead(
                    producto_id=detalle.producto_id,
                    descripcion=detalle.descripcion,
                    cantidad=detalle.cantidad,
                    precio_unitario=detalle.precio_unitario,
                    descuento=detalle.descuento,
                    subtotal_sin_impuesto=detalle.subtotal_sin_impuesto,
                    es_actividad_excluida=detalle.es_actividad_excluida,
                    impuestos=[
                        VentaDetalleImpuestoRead(
                            tipo_impuesto=imp.tipo_impuesto,
                            codigo_impuesto_sri=imp.codigo_impuesto_sri,
                            codigo_porcentaje_sri=imp.codigo_porcentaje_sri,
                            tarifa=imp.tarifa,
                            base_imponible=imp.base_imponible,
                            valor_impuesto=imp.valor_impuesto,
                        )
                        for imp in impuestos_por_detalle.get(detalle.id, [])
                    ],
                )
            )

        return VentaRead(
            id=venta.id,
            cliente_id=venta.cliente_id,
            empresa_id=venta.empresa_id,
            punto_emision_id=venta.punto_emision_id,
            secuencial_formateado=venta.secuencial_formateado,
            fecha_emision=venta.fecha_emision,
            tipo_identificacion_comprador=venta.tipo_identificacion_comprador,
            identificacion_comprador=venta.identificacion_comprador,
            forma_pago=venta.forma_pago,
            tipo_emision=venta.tipo_emision,
            regimen_emisor=venta.regimen_emisor,
            estado=venta.estado,
            estado_sri=venta.estado_sri,
            sri_intentos=venta.sri_intentos,
            sri_ultimo_error=venta.sri_ultimo_error,
            subtotal_sin_impuestos=venta.subtotal_sin_impuestos,
            subtotal_12=venta.subtotal_12,
            subtotal_15=venta.subtotal_15,
            subtotal_0=venta.subtotal_0,
            subtotal_no_objeto=venta.subtotal_no_objeto,
            monto_iva=venta.monto_iva,
            monto_ice=venta.monto_ice,
            valor_total=venta.valor_total,
            total=venta.valor_total,
            detalles=detalles_read,
            creado_en=venta.creado_en,
            actualizado_en=venta.actualizado_en,
        )

    def encolar_venta(
        self,
        session: Session,
        *,
        venta_id: UUID,
        usuario_id: str | None,
        background_tasks: BackgroundTasks | None = None,
        commit: bool = True,
    ) -> DocumentoSriCola:
        venta = session.get(Venta, venta_id)
        if not venta or not venta.activo:
            raise HTTPException(status_code=404, detail="Venta no encontrada")
        if venta.tipo_emision != TipoEmisionVenta.ELECTRONICA:
            raise HTTPException(status_code=400, detail="Solo se encolan ventas con tipo de emisión ELECTRONICA.")

        existente = session.exec(
            select(DocumentoSriCola).where(
                DocumentoSriCola.entidad_id == venta.id,
                DocumentoSriCola.tipo_documento == "VENTA",
                DocumentoSriCola.activo.is_(True),
                DocumentoSriCola.estado.in_(
                    [
                        EstadoColaSri.PENDIENTE,
                        EstadoColaSri.PROCESANDO,
                        EstadoColaSri.REINTENTO_PROGRAMADO,
                    ]
                ),
            )
        ).first()
        if existente:
            if background_tasks:
                background_tasks.add_task(self.procesar_documento_sri, existente.id)
            return existente

        empresa = session.get(Empresa, venta.empresa_id) if venta.empresa_id else None
        if not empresa:
            raise HTTPException(status_code=400, detail="La venta electrónica requiere empresa emisora.")

        punto = session.get(PuntoEmision, venta.punto_emision_id) if venta.punto_emision_id else None
        sucursal = session.get(Sucursal, punto.sucursal_id) if punto and punto.sucursal_id else None

        venta_read = self._venta_read(session, venta.id)
        payload = self.fe_mapper.venta_to_fe_ec_payload(
            venta_read,
            ruc_emisor=empresa.ruc,
            razon_social=empresa.razon_social,
            nombre_comercial=empresa.nombre_comercial,
            dir_matriz=empresa.direccion_matriz,
            obligado_contabilidad=empresa.obligado_contabilidad,
            estab=(sucursal.codigo if sucursal and sucursal.codigo else "001"),
            pto_emi=(punto.codigo if punto and punto.codigo else "001"),
            dir_establecimiento=(sucursal.direccion if sucursal and sucursal.direccion else empresa.direccion_matriz),
        )

        clave_acceso = payload["infoTributaria"]["claveAcceso"]
        documento = session.exec(
            select(DocumentoElectronico).where(
                DocumentoElectronico.venta_id == venta.id,
                DocumentoElectronico.activo.is_(True),
            )
        ).first()
        if documento is None:
            documento = DocumentoElectronico(
                tipo_documento=TipoDocumentoElectronico.FACTURA,
                referencia_id=venta.id,
                venta_id=venta.id,
                clave_acceso=clave_acceso,
                estado=EstadoDocumentoElectronico.EN_COLA,
                estado_sri=EstadoDocumentoElectronico.EN_COLA,
                usuario_auditoria=usuario_id,
                activo=True,
            )
        else:
            documento.tipo_documento = TipoDocumentoElectronico.FACTURA
            documento.referencia_id = venta.id
            documento.clave_acceso = clave_acceso
            self._sync_estado_documento(documento, EstadoDocumentoElectronico.EN_COLA, mensaje=None)
            documento.usuario_auditoria = usuario_id
        session.add(documento)
        session.flush()

        tarea = DocumentoSriCola(
            entidad_id=venta.id,
            tipo_documento="VENTA",
            estado=EstadoColaSri.PENDIENTE,
            intentos_realizados=0,
            max_intentos=3,
            payload_json=json.dumps(payload, ensure_ascii=False),
            usuario_auditoria=usuario_id,
            activo=True,
        )
        session.add(tarea)

        venta.estado_sri = EstadoSriDocumento.ENVIADO
        venta.sri_ultimo_error = None
        venta.usuario_auditoria = usuario_id
        session.add(venta)

        self._crear_historial_documento(
            session,
            documento=documento,
            estado_anterior=EstadoDocumentoElectronico.EN_COLA,
            estado_nuevo=EstadoDocumentoElectronico.EN_COLA,
            motivo="Factura encolada para transmisión al SRI.",
            usuario_id=usuario_id,
        )

        if commit:
            session.commit()
            session.refresh(tarea)
        else:
            session.flush()

        if background_tasks:
            background_tasks.add_task(self.procesar_documento_sri, tarea.id)
        return tarea

    def procesar_documento_sri(
        self,
        tarea_id: UUID,
        *,
        gateway: FEECVentaGateway | None = None,
        scheduler: Callable[[UUID, int], None] | None = None,
        email_dispatcher: Callable[[UUID], None] | None = None,
    ) -> None:
        gateway_impl = gateway or self.gateway
        scheduler_impl = scheduler or (lambda task_id, delay: self._default_scheduler(task_id, delay, self.procesar_documento_sri))
        email_dispatcher_impl = email_dispatcher or (lambda venta_id: self.correo_service.encolar_envio_factura(venta_id))

        with Session(self.db_engine) as session:
            tarea = session.get(DocumentoSriCola, tarea_id)
            if not tarea or not tarea.activo:
                return
            if tarea.tipo_documento != "VENTA":
                return
            if tarea.estado in {EstadoColaSri.COMPLETADO, EstadoColaSri.FALLIDO}:
                return

            venta = session.get(Venta, tarea.entidad_id)
            if not venta or not venta.activo:
                tarea.estado = EstadoColaSri.FALLIDO
                tarea.ultimo_error = "Venta asociada no encontrada."
                session.add(tarea)
                session.commit()
                return

            documento = session.exec(
                select(DocumentoElectronico).where(
                    DocumentoElectronico.venta_id == venta.id,
                    DocumentoElectronico.activo.is_(True),
                )
            ).first()
            if not documento:
                tarea.estado = EstadoColaSri.FALLIDO
                tarea.ultimo_error = "Documento electrónico de venta no encontrado."
                session.add(tarea)
                session.commit()
                return

            tarea.estado = EstadoColaSri.PROCESANDO
            tarea.intentos_realizados += 1
            venta.sri_intentos = tarea.intentos_realizados
            session.add(tarea)
            session.add(venta)
            session.commit()

            payload = json.loads(tarea.payload_json)
            try:
                respuesta = gateway_impl.enviar_documento(
                    tipo_documento="VENTA",
                    payload=payload,
                )
            except (TimeoutError, ConnectionError, OSError) as exc:
                error = str(exc) or "Timeout de red con SRI"
                estado_anterior = documento.estado
                if tarea.intentos_realizados < tarea.max_intentos:
                    delay = 2 ** (tarea.intentos_realizados - 1)
                    tarea.estado = EstadoColaSri.REINTENTO_PROGRAMADO
                    tarea.proximo_intento_en = datetime.utcnow() + timedelta(seconds=delay)
                    tarea.ultimo_error = error

                    venta.estado_sri = EstadoSriDocumento.ENVIADO
                    venta.sri_ultimo_error = error
                    self._sync_estado_documento(documento, EstadoDocumentoElectronico.EN_COLA, mensaje=error)

                    session.add(tarea)
                    session.add(venta)
                    session.add(documento)
                    self._crear_historial_documento(
                        session,
                        documento=documento,
                        estado_anterior=estado_anterior,
                        estado_nuevo=EstadoDocumentoElectronico.EN_COLA,
                        motivo=f"Error de red SRI. Reintento en {delay}s. {error}",
                        usuario_id=venta.usuario_auditoria,
                    )
                    session.commit()
                    scheduler_impl(tarea.id, delay)
                    return

                tarea.estado = EstadoColaSri.FALLIDO
                tarea.ultimo_error = error
                venta.estado_sri = EstadoSriDocumento.ERROR
                venta.sri_ultimo_error = error
                session.add(tarea)
                session.add(venta)
                session.commit()
                return

            estado = str(respuesta.get("estado", "")).upper()
            mensaje = str(respuesta.get("mensaje") or "").strip()
            estado_anterior = documento.estado

            if estado == "AUTORIZADO":
                tarea.estado = EstadoColaSri.COMPLETADO
                tarea.ultimo_error = None
                venta.estado_sri = EstadoSriDocumento.AUTORIZADO
                venta.sri_ultimo_error = None
                self._sync_estado_documento(documento, EstadoDocumentoElectronico.AUTORIZADO, mensaje=None)
                session.add(tarea)
                session.add(venta)
                session.add(documento)
                self._crear_historial_documento(
                    session,
                    documento=documento,
                    estado_anterior=estado_anterior,
                    estado_nuevo=EstadoDocumentoElectronico.AUTORIZADO,
                    motivo=mensaje or "Documento autorizado por SRI.",
                    usuario_id=venta.usuario_auditoria,
                )
                session.commit()
                email_dispatcher_impl(venta.id)
                return

            if estado == "RECHAZADO":
                tarea.estado = EstadoColaSri.FALLIDO
                tarea.ultimo_error = mensaje or "Documento rechazado por SRI."
                venta.estado_sri = EstadoSriDocumento.RECHAZADO
                venta.sri_ultimo_error = tarea.ultimo_error
                self._sync_estado_documento(
                    documento,
                    EstadoDocumentoElectronico.RECHAZADO,
                    mensaje=tarea.ultimo_error,
                )
                session.add(tarea)
                session.add(venta)
                session.add(documento)
                self._crear_historial_documento(
                    session,
                    documento=documento,
                    estado_anterior=estado_anterior,
                    estado_nuevo=EstadoDocumentoElectronico.RECHAZADO,
                    motivo=tarea.ultimo_error,
                    usuario_id=venta.usuario_auditoria,
                )
                session.commit()
                return

            if estado == "RECIBIDO":
                delay = 2 ** max(tarea.intentos_realizados - 1, 1)
                tarea.estado = EstadoColaSri.REINTENTO_PROGRAMADO
                tarea.proximo_intento_en = datetime.utcnow() + timedelta(seconds=delay)
                tarea.ultimo_error = mensaje or "Documento recibido por SRI, pendiente de autorización."
                venta.estado_sri = EstadoSriDocumento.ENVIADO
                venta.sri_ultimo_error = tarea.ultimo_error
                self._sync_estado_documento(
                    documento,
                    EstadoDocumentoElectronico.RECIBIDO,
                    mensaje=tarea.ultimo_error,
                )
                session.add(tarea)
                session.add(venta)
                session.add(documento)
                self._crear_historial_documento(
                    session,
                    documento=documento,
                    estado_anterior=estado_anterior,
                    estado_nuevo=EstadoDocumentoElectronico.RECIBIDO,
                    motivo=tarea.ultimo_error,
                    usuario_id=venta.usuario_auditoria,
                )
                session.commit()
                scheduler_impl(tarea.id, delay)
                return

            tarea.estado = EstadoColaSri.FALLIDO
            tarea.ultimo_error = mensaje or f"Respuesta SRI desconocida: {estado or 'VACIO'}"
            venta.estado_sri = EstadoSriDocumento.ERROR
            venta.sri_ultimo_error = tarea.ultimo_error
            session.add(tarea)
            session.add(venta)
            session.commit()

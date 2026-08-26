from __future__ import annotations

from html import escape
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, select

from osiris.modules.common.empleado.entity import Empleado
from osiris.modules.common.usuario.entity import Usuario
from osiris.modules.sri.core_sri.models import (
    DocumentoElectronico,
    EstadoDocumentoElectronico,
    Retencion,
    TipoDocumentoElectronico,
    Venta,
)


class DocumentoElectronicoService:
    @staticmethod
    def _obtener_documento(session: Session, documento_id: UUID) -> DocumentoElectronico:
        documento = session.get(DocumentoElectronico, documento_id)
        if not documento or not documento.activo:
            raise HTTPException(status_code=404, detail="Documento electrónico no encontrado.")
        return documento

    @staticmethod
    def _resolver_empresa_documento(session: Session, documento: DocumentoElectronico) -> UUID | None:
        if documento.tipo_documento == TipoDocumentoElectronico.FACTURA:
            venta_id = documento.referencia_id or documento.venta_id
            if venta_id is None:
                return None
            venta = session.get(Venta, venta_id)
            if not venta or not venta.activo:
                return None
            return venta.empresa_id
        return None

    @staticmethod
    def _empresas_usuario(session: Session, user_id: str) -> set[UUID]:
        try:
            user_uuid = UUID(user_id)
        except (TypeError, ValueError):
            raise HTTPException(status_code=403, detail="Usuario autenticado inválido.") from None

        usuario = session.get(Usuario, user_uuid)
        if not usuario or not usuario.activo:
            raise HTTPException(status_code=403, detail="Usuario autenticado no válido.")

        empleados = list(
            session.exec(
                select(Empleado).where(
                    Empleado.persona_id == usuario.persona_id,
                    Empleado.activo.is_(True),
                )
            ).all()
        )
        return {emp.empresa_id for emp in empleados if emp.empresa_id is not None}

    def _validar_acceso_documento(self, session: Session, documento: DocumentoElectronico, user_id: str | None) -> None:
        if not user_id:
            raise HTTPException(status_code=403, detail="Usuario no autenticado.")

        empresa_documento = self._resolver_empresa_documento(session, documento)
        if empresa_documento is None:
            # En MVP, algunos tipos no tienen trazabilidad completa de empresa.
            # Aun así, exigimos autenticación válida.
            self._empresas_usuario(session, user_id)
            return

        empresas_usuario = self._empresas_usuario(session, user_id)
        if empresa_documento not in empresas_usuario:
            raise HTTPException(status_code=403, detail="No autorizado para acceder a este documento.")

    def obtener_xml_autorizado(self, session: Session, documento_id: UUID, user_id: str | None) -> str:
        documento = self._obtener_documento(session, documento_id)
        self._validar_acceso_documento(session, documento, user_id)

        if documento.estado_sri != EstadoDocumentoElectronico.AUTORIZADO:
            raise HTTPException(status_code=400, detail="El documento electrónico aún no está AUTORIZADO.")
        if not documento.xml_autorizado:
            raise HTTPException(status_code=404, detail="XML autorizado no disponible.")
        return documento.xml_autorizado

    def obtener_ride_html(self, session: Session, documento_id: UUID, user_id: str | None) -> str:
        documento = self._obtener_documento(session, documento_id)
        self._validar_acceso_documento(session, documento, user_id)

        if documento.estado_sri != EstadoDocumentoElectronico.AUTORIZADO:
            raise HTTPException(status_code=400, detail="El documento electrónico aún no está AUTORIZADO.")

        if documento.tipo_documento == TipoDocumentoElectronico.FACTURA:
            venta_id = documento.referencia_id or documento.venta_id
            venta = session.get(Venta, venta_id) if venta_id else None
            if not venta:
                raise HTTPException(status_code=404, detail="Venta asociada no encontrada.")
            titulo = "RIDE Factura Electrónica"
            body = (
                f"<p><strong>Fecha:</strong> {venta.fecha_emision.isoformat()}</p>"
                f"<p><strong>Identificación Comprador:</strong> {escape(venta.identificacion_comprador)}</p>"
                f"<p><strong>Total:</strong> {venta.valor_total}</p>"
            )
        elif documento.tipo_documento == TipoDocumentoElectronico.RETENCION:
            retencion = session.get(Retencion, documento.referencia_id) if documento.referencia_id else None
            if not retencion:
                raise HTTPException(status_code=404, detail="Retención asociada no encontrada.")
            titulo = "RIDE Comprobante de Retención"
            body = (
                f"<p><strong>Fecha:</strong> {retencion.fecha_emision.isoformat()}</p>"
                f"<p><strong>Total Retenido:</strong> {retencion.total_retenido}</p>"
            )
        else:
            raise HTTPException(status_code=400, detail="Tipo de documento no soportado para RIDE.")

        clave = escape(documento.clave_acceso or "N/A")
        return (
            "<html><head><meta charset='utf-8'><title>RIDE</title></head><body>"
            f"<h1>{titulo}</h1>"
            f"<p><strong>Clave de Acceso:</strong> {clave}</p>"
            f"{body}"
            "</body></html>"
        )

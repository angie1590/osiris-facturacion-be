from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, select

from osiris.core.settings import get_settings
from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.common.punto_emision.entity import PuntoEmision
from osiris.modules.common.rol.entity import Rol
from osiris.modules.common.usuario.entity import Usuario
from osiris.modules.sri.core_sri.models import (
    DocumentoElectronico,
    EstadoDocumentoElectronico,
    TipoDocumentoElectronico,
    Venta,
    VentaDetalle,
)
from osiris.modules.sri.core_sri.types import FormaPagoSRI
from osiris.modules.ventas.models import CuentaPorCobrar, PagoCxC
from osiris.modules.impresion.strategies.plantilla_preimpresa_strategy import (
    PlantillaPreimpresaStrategy,
)
from osiris.modules.impresion.strategies.render_strategy import RenderStrategy
from osiris.modules.impresion.strategies.ride_a4_strategy import RideA4Strategy
from osiris.modules.impresion.strategies.ticket_termico_strategy import TicketTermicoStrategy


class ImpresionService:
    def __init__(self, strategy: RenderStrategy | None = None) -> None:
        self.strategy = strategy or RideA4Strategy()
        self.ticket_strategy = TicketTermicoStrategy(Path(__file__).resolve().parents[1] / "templates")
        self.preimpresa_strategy = PlantillaPreimpresaStrategy(Path(__file__).resolve().parents[1] / "templates")
        self.templates_dir = Path(__file__).resolve().parents[1] / "templates"

    @staticmethod
    def _barcode_data_uri(clave_acceso: str) -> str:
        try:
            from io import BytesIO

            import barcode  # type: ignore
            from barcode.writer import SVGWriter  # type: ignore

            output = BytesIO()
            code128 = barcode.get("code128", clave_acceso, writer=SVGWriter())
            code128.write(output)
            svg_bytes = output.getvalue()
        except ModuleNotFoundError:
            svg = (
                "<svg xmlns='http://www.w3.org/2000/svg' width='560' height='65'>"
                "<rect width='100%' height='100%' fill='white'/>"
                "<text x='8' y='35' font-size='14' fill='black'>"
                f"{clave_acceso}"
                "</text>"
                "</svg>"
            )
            svg_bytes = svg.encode("utf-8")

        encoded = base64.b64encode(svg_bytes).decode("ascii")
        return f"data:image/svg+xml;base64,{encoded}"

    def _render_html(self, context: dict) -> str:
        template_path = self.templates_dir / "ride_a4.html"
        if not template_path.exists():
            raise HTTPException(status_code=500, detail="Plantilla RIDE A4 no encontrada.")

        try:
            from jinja2 import Environment, FileSystemLoader, select_autoescape  # type: ignore

            env = Environment(
                loader=FileSystemLoader(str(self.templates_dir)),
                autoescape=select_autoescape(["html", "xml"]),
            )
            template = env.get_template("ride_a4.html")
            return template.render(**context)
        except ModuleNotFoundError:
            # Fallback para entornos sin Jinja2 instalado.
            template = template_path.read_text(encoding="utf-8")
            html = template
            html = html.replace("{{ razon_social }}", str(context["razon_social"]))
            html = html.replace("{{ ruc }}", str(context["ruc"]))
            html = html.replace("{{ clave_acceso }}", str(context["clave_acceso"]))
            html = html.replace("{{ ambiente }}", str(context["ambiente"]))
            html = html.replace("{{ fecha_emision }}", str(context["fecha_emision"]))
            html = html.replace("{{ subtotal }}", str(context["subtotal"]))
            html = html.replace("{{ iva_total }}", str(context["iva_total"]))
            html = html.replace("{{ total }}", str(context["total"]))
            html = html.replace("{{ barcode_data_uri }}", str(context["barcode_data_uri"]))
            html = html.replace("{{ logo_url }}", str(context["logo_url"]))
            return html

    def _payload_from_documento(self, session: Session, documento: DocumentoElectronico) -> dict:
        venta = None
        if documento.tipo_documento == TipoDocumentoElectronico.FACTURA:
            venta_id = documento.referencia_id or documento.venta_id
            if venta_id is not None:
                venta = session.get(Venta, venta_id)

        empresa = session.get(Empresa, venta.empresa_id) if venta and venta.empresa_id else None
        settings = get_settings()
        ambiente = "Pruebas" if settings.FEEC_AMBIENTE.lower() == "pruebas" else "Produccion"

        subtotal = "0.00"
        iva_total = "0.00"
        total = "0.00"
        fecha_emision = ""
        if venta is not None:
            subtotal = str(venta.subtotal_sin_impuestos)
            iva_total = str(venta.monto_iva)
            total = str(venta.valor_total)
            fecha_emision = venta.fecha_emision.isoformat()

        clave = documento.clave_acceso or "SIN_CLAVE_ACCESO"
        return {
            "logo_url": empresa.logo if empresa and empresa.logo else "",
            "razon_social": empresa.razon_social if empresa else "RAZON SOCIAL",
            "ruc": empresa.ruc if empresa else "RUC_NO_DISPONIBLE",
            "clave_acceso": clave,
            "ambiente": ambiente,
            "subtotal": subtotal,
            "iva_total": iva_total,
            "total": total,
            "fecha_emision": fecha_emision,
            "barcode_data_uri": self._barcode_data_uri(clave),
        }

    def generar_ride_a4(self, session: Session, *, documento_id: UUID) -> bytes:
        documento = session.get(DocumentoElectronico, documento_id)
        if not documento or not documento.activo:
            raise HTTPException(status_code=404, detail="Documento electrónico no encontrado.")
        if documento.estado_sri != EstadoDocumentoElectronico.AUTORIZADO:
            raise HTTPException(status_code=400, detail="Solo se puede imprimir RIDE de documentos AUTORIZADOS.")

        payload = self._payload_from_documento(session, documento)
        html = self._render_html(payload)
        return self.strategy.render_pdf(html)

    def generar_ticket_termico_html(
        self,
        session: Session,
        *,
        documento_id: UUID,
        ancho: str = "80mm",
    ) -> str:
        if ancho not in {"58mm", "80mm"}:
            raise HTTPException(status_code=400, detail="El parámetro 'ancho' debe ser '58mm' o '80mm'.")

        documento = session.get(DocumentoElectronico, documento_id)
        if not documento or not documento.activo:
            raise HTTPException(status_code=404, detail="Documento electrónico no encontrado.")
        if documento.estado_sri != EstadoDocumentoElectronico.AUTORIZADO:
            raise HTTPException(status_code=400, detail="Solo se puede imprimir ticket de documentos AUTORIZADOS.")

        venta = None
        if documento.tipo_documento == TipoDocumentoElectronico.FACTURA:
            venta_id = documento.referencia_id or documento.venta_id
            if venta_id is not None:
                venta = session.get(Venta, venta_id)
        if venta is None:
            raise HTTPException(status_code=404, detail="Venta asociada al documento no encontrada.")

        empresa = session.get(Empresa, venta.empresa_id) if venta.empresa_id else None
        cxc = session.exec(
            select(CuentaPorCobrar).where(
                CuentaPorCobrar.venta_id == venta.id,
                CuentaPorCobrar.activo.is_(True),
            )
        ).first()
        pagos = []
        if cxc is not None:
            pagos = list(
                session.exec(
                    select(PagoCxC).where(
                        PagoCxC.cuenta_por_cobrar_id == cxc.id,
                        PagoCxC.activo.is_(True),
                    )
                ).all()
            )

        total_pagado = sum((pago.monto for pago in pagos), start=0)
        total_efectivo = sum(
            (pago.monto for pago in pagos if pago.forma_pago_sri == FormaPagoSRI.EFECTIVO),
            start=0,
        )
        cambio = total_efectivo - venta.valor_total
        if cambio < 0:
            cambio = 0

        context = {
            "ticket_template": ancho,
            "razon_social": empresa.razon_social if empresa else "RAZON SOCIAL",
            "ruc": empresa.ruc if empresa else "RUC_NO_DISPONIBLE",
            "fecha_emision": venta.fecha_emision.isoformat(),
            "clave_acceso": documento.clave_acceso or "SIN_CLAVE_ACCESO",
            "subtotal": str(venta.subtotal_sin_impuestos),
            "iva_total": str(venta.monto_iva),
            "total": str(venta.valor_total),
            "total_pagado": str(total_pagado),
            "efectivo": str(total_efectivo),
            "cambio": str(cambio),
            "width_mm": ancho,
        }
        return self.ticket_strategy.render_ticket_html(context, ancho=ancho)

    @staticmethod
    def _cm_as_string(value: float) -> str:
        if float(value).is_integer():
            return str(int(value))
        return str(value).rstrip("0").rstrip(".")

    @staticmethod
    def _leer_config_impresion(punto_emision: PuntoEmision | None) -> tuple[str, int]:
        default_margen = 5.0
        default_max_items = 15
        config = punto_emision.config_impresion if punto_emision and isinstance(punto_emision.config_impresion, dict) else {}

        margen_superior = default_margen
        max_items_por_pagina = default_max_items

        try:
            margen_superior = float(config.get("margen_superior_cm", default_margen))
            if margen_superior <= 0:
                margen_superior = default_margen
        except (TypeError, ValueError):
            margen_superior = default_margen

        try:
            max_items_por_pagina = int(config.get("max_items_por_pagina", default_max_items))
            if max_items_por_pagina <= 0:
                max_items_por_pagina = default_max_items
        except (TypeError, ValueError):
            max_items_por_pagina = default_max_items

        return ImpresionService._cm_as_string(margen_superior), max_items_por_pagina

    def generar_preimpresa_html(
        self,
        session: Session,
        *,
        documento_id: UUID,
    ) -> dict[str, str | None]:
        documento = session.get(DocumentoElectronico, documento_id)
        if not documento or not documento.activo:
            raise HTTPException(status_code=404, detail="Documento electrónico no encontrado.")
        if documento.estado_sri != EstadoDocumentoElectronico.AUTORIZADO:
            raise HTTPException(status_code=400, detail="Solo se puede imprimir preimpresa de documentos AUTORIZADOS.")

        venta = None
        if documento.tipo_documento == TipoDocumentoElectronico.FACTURA:
            venta_id = documento.referencia_id or documento.venta_id
            if venta_id is not None:
                venta = session.get(Venta, venta_id)
        if venta is None:
            raise HTTPException(status_code=404, detail="Venta asociada al documento no encontrada.")

        punto_emision = session.get(PuntoEmision, venta.punto_emision_id) if venta.punto_emision_id else None
        margen_superior_cm, max_items_por_pagina = self._leer_config_impresion(punto_emision)

        detalles = list(
            session.exec(
                select(VentaDetalle)
                .where(
                    VentaDetalle.venta_id == venta.id,
                    VentaDetalle.activo.is_(True),
                )
                .order_by(VentaDetalle.creado_en.asc())
            ).all()
        )
        if not detalles:
            raise HTTPException(status_code=400, detail="No se puede imprimir una venta sin detalles.")

        items = [
            {
                "cantidad": str(detalle.cantidad),
                "descripcion": detalle.descripcion,
                "valor_unitario": str(detalle.precio_unitario),
                "valor_total": str(detalle.subtotal_sin_impuesto),
            }
            for detalle in detalles
        ]

        paginas = [
            items[i : i + max_items_por_pagina]
            for i in range(0, len(items), max_items_por_pagina)
        ]

        warning = None
        if len(items) > max_items_por_pagina:
            warning = (
                "La venta excede el máximo de ítems por página configurado "
                f"({max_items_por_pagina}). Se dividió en {len(paginas)} páginas."
            )

        html = self.preimpresa_strategy.render_html(
            {
                "margen_superior_cm": margen_superior_cm,
                "paginas": paginas,
                "total": str(venta.valor_total),
            }
        )
        return {"html": html, "warning": warning}

    def generar_preimpresa_pdf(
        self,
        session: Session,
        *,
        documento_id: UUID,
    ) -> dict[str, bytes | str | None]:
        resultado_html = self.generar_preimpresa_html(session, documento_id=documento_id)
        return {
            "pdf": self.preimpresa_strategy.render_pdf(str(resultado_html["html"])),
            "warning": resultado_html["warning"],
        }

    @staticmethod
    def _require_cajero_admin(session: Session, user_id: str | None) -> UUID:
        if not user_id:
            raise HTTPException(status_code=403, detail="Usuario no autenticado.")
        try:
            user_uuid = UUID(str(user_id))
        except (TypeError, ValueError):
            raise HTTPException(status_code=403, detail="Usuario autenticado inválido.") from None

        row = session.exec(
            select(Usuario, Rol)
            .join(Rol, Rol.id == Usuario.rol_id)
            .where(
                Usuario.id == user_uuid,
                Usuario.activo.is_(True),
                Rol.activo.is_(True),
            )
        ).first()
        if not row:
            raise HTTPException(status_code=403, detail="Usuario no autorizado para reimpresión.")

        _, rol = row
        if rol.nombre.strip().upper() not in {"CAJERO", "ADMIN", "ADMINISTRADOR"}:
            raise HTTPException(status_code=403, detail="Solo Cajero o Administrador pueden reimprimir.")
        return user_uuid

    def reimprimir_documento(
        self,
        session: Session,
        *,
        documento_id: UUID,
        motivo: str,
        formato: str,
        user_id: str | None,
    ) -> dict:
        user_uuid = self._require_cajero_admin(session, user_id)

        documento = session.get(DocumentoElectronico, documento_id)
        if not documento or not documento.activo:
            raise HTTPException(status_code=404, detail="Documento electrónico no encontrado.")
        if documento.estado_sri != EstadoDocumentoElectronico.AUTORIZADO:
            raise HTTPException(status_code=400, detail="Solo se puede reimprimir un documento AUTORIZADO.")

        motivo_limpio = (motivo or "").strip()
        if not motivo_limpio:
            raise HTTPException(status_code=400, detail="El motivo de reimpresión es obligatorio.")

        venta = None
        if documento.tipo_documento == TipoDocumentoElectronico.FACTURA:
            venta_id = documento.referencia_id or documento.venta_id
            if venta_id is not None:
                venta = session.get(Venta, venta_id)

        before = {
            "documento_id": str(documento.id),
            "documento_cantidad_impresiones": documento.cantidad_impresiones,
            "venta_id": str(venta.id) if venta else None,
            "venta_cantidad_impresiones": venta.cantidad_impresiones if venta else None,
        }

        documento.cantidad_impresiones = int(documento.cantidad_impresiones or 0) + 1
        session.add(documento)
        if venta is not None:
            venta.cantidad_impresiones = int(venta.cantidad_impresiones or 0) + 1
            session.add(venta)

        after = {
            "documento_id": str(documento.id),
            "documento_cantidad_impresiones": documento.cantidad_impresiones,
            "venta_id": str(venta.id) if venta else None,
            "venta_cantidad_impresiones": venta.cantidad_impresiones if venta else None,
            "motivo": motivo_limpio,
            "formato": formato,
        }
        actor = str(user_uuid)
        session.add(
            AuditLog(
                tabla_afectada="tbl_documento_electronico",
                registro_id=str(documento.id),
                entidad="DocumentoElectronico",
                entidad_id=documento.id,
                accion="REIMPRESION_DOCUMENTO",
                estado_anterior=before,
                estado_nuevo=after,
                before_json=before,
                after_json=after,
                usuario_id=actor,
                usuario_auditoria=actor,
                created_by=actor,
                updated_by=actor,
                fecha=datetime.utcnow(),
                creado_en=datetime.utcnow(),
            )
        )
        session.commit()
        session.refresh(documento)
        if venta is not None:
            session.refresh(venta)

        formato_normalizado = formato.strip().upper()
        if formato_normalizado == "A4":
            pdf = self.generar_ride_a4(session, documento_id=documento.id)
            return {
                "content": pdf,
                "media_type": "application/pdf",
                "filename": f"ride-{documento.id}.pdf",
            }
        if formato_normalizado == "TICKET_58MM":
            html = self.generar_ticket_termico_html(session, documento_id=documento.id, ancho="58mm")
            return {
                "content": html,
                "media_type": "text/html",
                "filename": f"ticket-{documento.id}-58mm.html",
            }
        if formato_normalizado == "TICKET_80MM":
            html = self.generar_ticket_termico_html(session, documento_id=documento.id, ancho="80mm")
            return {
                "content": html,
                "media_type": "text/html",
                "filename": f"ticket-{documento.id}-80mm.html",
            }

        raise HTTPException(status_code=400, detail="Formato no soportado para reimpresión.")

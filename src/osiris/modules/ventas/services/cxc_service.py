from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlmodel import Session, select

from osiris.core.company_scope import resolve_company_scope
from osiris.modules.sri.core_sri.models import (
    CuentaPorCobrar,
    EstadoCuentaPorCobrar,
    PagoCxC,
    Venta,
)
from osiris.modules.sri.core_sri.all_schemas import PagoCxCCreate, q2
from osiris.utils.pagination import build_pagination_meta
from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION


class CuentaPorCobrarService:
    @staticmethod
    def _empresa_scope() -> UUID | None:
        return resolve_company_scope()

    def listar_cxc(
        self,
        session: Session,
        *,
        limit: int,
        offset: int,
        only_active: bool = True,
        estado: EstadoCuentaPorCobrar | None = None,
        texto: str | None = None,
    ):
        stmt = select(CuentaPorCobrar, Venta).join(Venta, Venta.id == CuentaPorCobrar.venta_id)
        empresa_scope = self._empresa_scope()
        if empresa_scope is not None:
            stmt = stmt.where(Venta.empresa_id == empresa_scope)
        if only_active:
            stmt = stmt.where(
                CuentaPorCobrar.activo.is_(True),
                Venta.activo.is_(True),
            )
        else:
            stmt = stmt.execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})

        if estado is not None:
            stmt = stmt.where(CuentaPorCobrar.estado == estado)

        if texto:
            pattern = f"%{texto.strip()}%"
            stmt = stmt.where(
                or_(
                    Venta.identificacion_comprador.ilike(pattern),
                    Venta.secuencial_formateado.ilike(pattern),
                )
            )

        total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
        rows = list(
            session.exec(
                stmt.order_by(Venta.fecha_emision.desc(), CuentaPorCobrar.creado_en.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        )
        items = [
            {
                "id": cxc.id,
                "venta_id": cxc.venta_id,
                "cliente_id": venta.cliente_id,
                "cliente": venta.identificacion_comprador,
                "numero_factura": venta.secuencial_formateado,
                "fecha_emision": venta.fecha_emision,
                "valor_total_factura": cxc.valor_total_factura,
                "valor_retenido": cxc.valor_retenido,
                "pagos_acumulados": cxc.pagos_acumulados,
                "saldo_pendiente": cxc.saldo_pendiente,
                "estado": cxc.estado,
            }
            for cxc, venta in rows
        ]
        return items, build_pagination_meta(total=total, limit=limit, offset=offset)

    @staticmethod
    def _recalcular_saldo_y_estado(cxc: CuentaPorCobrar) -> None:
        nuevo_saldo = q2(cxc.valor_total_factura - cxc.valor_retenido - cxc.pagos_acumulados)
        if nuevo_saldo < Decimal("0.00"):
            raise ValueError("La retención supera el saldo de la factura")

        cxc.saldo_pendiente = nuevo_saldo
        if nuevo_saldo == Decimal("0.00"):
            cxc.estado = EstadoCuentaPorCobrar.PAGADA
        elif q2(cxc.pagos_acumulados) > Decimal("0.00") or q2(cxc.valor_retenido) > Decimal("0.00"):
            cxc.estado = EstadoCuentaPorCobrar.PARCIAL
        else:
            cxc.estado = EstadoCuentaPorCobrar.PENDIENTE

    @staticmethod
    def aplicar_retencion_en_cxc(cxc: CuentaPorCobrar, valor_aplicar: Decimal) -> None:
        valor = q2(valor_aplicar)
        if valor > q2(cxc.saldo_pendiente):
            raise ValueError("La retención supera el saldo de la factura")

        cxc.valor_retenido = q2(cxc.valor_retenido + valor)
        CuentaPorCobrarService._recalcular_saldo_y_estado(cxc)

    @staticmethod
    def revertir_retencion_en_cxc(cxc: CuentaPorCobrar, valor_reverso: Decimal) -> None:
        valor = q2(valor_reverso)
        if valor > q2(cxc.valor_retenido):
            raise ValueError("La retención supera el saldo de la factura")

        cxc.valor_retenido = q2(cxc.valor_retenido - valor)
        CuentaPorCobrarService._recalcular_saldo_y_estado(cxc)

    @staticmethod
    def aplicar_pago_en_cxc(cxc: CuentaPorCobrar, monto_pago: Decimal) -> None:
        monto = q2(monto_pago)
        if monto > q2(cxc.saldo_pendiente):
            raise HTTPException(
                status_code=400,
                detail="El monto del pago no puede ser mayor al saldo pendiente.",
            )

        cxc.pagos_acumulados = q2(cxc.pagos_acumulados + monto)
        CuentaPorCobrarService._recalcular_saldo_y_estado(cxc)

    def obtener_cxc_por_venta(self, session: Session, venta_id: UUID) -> CuentaPorCobrar:
        empresa_scope = self._empresa_scope()
        cxc = session.exec(
            select(CuentaPorCobrar)
            .join(Venta, Venta.id == CuentaPorCobrar.venta_id)
            .where(
                CuentaPorCobrar.venta_id == venta_id,
                CuentaPorCobrar.activo.is_(True),
                Venta.activo.is_(True),
            )
        ).one_or_none()
        if not cxc:
            raise HTTPException(status_code=404, detail="Cuenta por cobrar no encontrada para la venta")
        if empresa_scope is not None:
            venta = session.get(Venta, cxc.venta_id)
            if not venta or venta.empresa_id != empresa_scope:
                raise HTTPException(status_code=403, detail="No autorizado para acceder a CxC de otra empresa.")
        return cxc

    def registrar_pago_cxc(
        self,
        session: Session,
        cuenta_por_cobrar_id: UUID,
        payload: PagoCxCCreate,
        *,
        commit: bool = True,
        rollback_on_error: bool = True,
    ) -> PagoCxC:
        try:
            empresa_scope = self._empresa_scope()
            cxc = session.exec(
                select(CuentaPorCobrar)
                .join(Venta, Venta.id == CuentaPorCobrar.venta_id)
                .where(
                    CuentaPorCobrar.id == cuenta_por_cobrar_id,
                    CuentaPorCobrar.activo.is_(True),
                    Venta.activo.is_(True),
                )
                .with_for_update()
            ).one_or_none()
            if not cxc:
                raise HTTPException(status_code=404, detail="Cuenta por cobrar no encontrada")
            if empresa_scope is not None:
                venta = session.get(Venta, cxc.venta_id)
                if not venta or venta.empresa_id != empresa_scope:
                    raise HTTPException(status_code=403, detail="No autorizado para registrar pagos en otra empresa.")

            if cxc.estado == EstadoCuentaPorCobrar.ANULADA:
                raise HTTPException(status_code=400, detail="No se puede registrar pagos en una CxC ANULADA.")

            self.aplicar_pago_en_cxc(cxc, payload.monto)
            cxc.usuario_auditoria = payload.usuario_auditoria

            pago = PagoCxC(
                cuenta_por_cobrar_id=cxc.id,
                monto=q2(payload.monto),
                fecha=payload.fecha,
                forma_pago_sri=payload.forma_pago_sri,
                usuario_auditoria=payload.usuario_auditoria,
                activo=True,
            )
            session.add(pago)
            session.add(cxc)

            if commit:
                session.commit()
                session.refresh(pago)
            else:
                session.flush()
            return pago
        except Exception:
            if rollback_on_error:
                session.rollback()
            raise

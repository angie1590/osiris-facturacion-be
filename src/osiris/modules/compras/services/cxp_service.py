from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlmodel import Session, select

from osiris.core.company_scope import resolve_company_scope
from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.sri.core_sri.models import Compra, CuentaPorPagar, EstadoCuentaPorPagar, PagoCxP
from osiris.modules.sri.core_sri.all_schemas import PagoCxPCreate, q2
from osiris.utils.pagination import build_pagination_meta


class CuentaPorPagarService:
    @staticmethod
    def _empresa_scope() -> UUID | None:
        return resolve_company_scope()

    def _validar_compra_scope(self, session: Session, compra: Compra) -> None:
        empresa_scope = self._empresa_scope()
        if empresa_scope is None:
            return
        if compra.sucursal_id is None:
            raise HTTPException(status_code=403, detail="No autorizado para operar CxP de otra empresa.")
        sucursal = session.get(Sucursal, compra.sucursal_id)
        if not sucursal or not sucursal.activo or sucursal.empresa_id != empresa_scope:
            raise HTTPException(status_code=403, detail="No autorizado para operar CxP de otra empresa.")

    def listar_cxp(
        self,
        session: Session,
        *,
        limit: int,
        offset: int,
        only_active: bool = True,
        estado: EstadoCuentaPorPagar | None = None,
        texto: str | None = None,
    ):
        stmt = select(CuentaPorPagar, Compra).join(Compra, Compra.id == CuentaPorPagar.compra_id)
        empresa_scope = self._empresa_scope()

        if empresa_scope is not None:
            stmt = stmt.join(Sucursal, Sucursal.id == Compra.sucursal_id).where(
                Sucursal.activo.is_(True),
                Sucursal.empresa_id == empresa_scope,
            )

        if only_active:
            stmt = stmt.where(
                CuentaPorPagar.activo.is_(True),
                Compra.activo.is_(True),
            )
        else:
            stmt = stmt.execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})

        if estado is not None:
            stmt = stmt.where(CuentaPorPagar.estado == estado)

        if texto:
            pattern = f"%{texto.strip()}%"
            stmt = stmt.where(
                or_(
                    Compra.identificacion_proveedor.ilike(pattern),
                    Compra.secuencial_factura.ilike(pattern),
                )
            )

        total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
        rows = list(
            session.exec(
                stmt.order_by(Compra.fecha_emision.desc(), CuentaPorPagar.creado_en.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        )
        items = [
            {
                "id": cxp.id,
                "compra_id": cxp.compra_id,
                "proveedor_id": compra.proveedor_id,
                "proveedor": compra.identificacion_proveedor,
                "numero_factura": compra.secuencial_factura,
                "fecha_emision": compra.fecha_emision,
                "valor_total_factura": cxp.valor_total_factura,
                "valor_retenido": cxp.valor_retenido,
                "pagos_acumulados": cxp.pagos_acumulados,
                "saldo_pendiente": cxp.saldo_pendiente,
                "estado": cxp.estado,
            }
            for cxp, compra in rows
        ]
        return items, build_pagination_meta(total=total, limit=limit, offset=offset)

    def obtener_cxp_por_compra(self, session: Session, compra_id: UUID) -> CuentaPorPagar:
        row = session.exec(
            select(CuentaPorPagar, Compra)
            .join(Compra, Compra.id == CuentaPorPagar.compra_id)
            .where(
                CuentaPorPagar.compra_id == compra_id,
                CuentaPorPagar.activo.is_(True),
                Compra.activo.is_(True),
            )
        ).one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Cuenta por pagar no encontrada para la compra")
        cxp, compra = row
        self._validar_compra_scope(session, compra)
        return cxp

    def registrar_pago_cxp(
        self,
        session: Session,
        cuenta_por_pagar_id: UUID,
        payload: PagoCxPCreate,
        *,
        commit: bool = True,
        rollback_on_error: bool = True,
    ) -> PagoCxP:
        try:
            row = session.exec(
                select(CuentaPorPagar, Compra)
                .join(Compra, Compra.id == CuentaPorPagar.compra_id)
                .where(
                    CuentaPorPagar.id == cuenta_por_pagar_id,
                    CuentaPorPagar.activo.is_(True),
                    Compra.activo.is_(True),
                )
                .with_for_update()
            ).one_or_none()
            if not row:
                raise HTTPException(status_code=404, detail="Cuenta por pagar no encontrada")
            cxp, compra = row
            self._validar_compra_scope(session, compra)

            if cxp.estado == EstadoCuentaPorPagar.ANULADA:
                raise ValueError("No se puede registrar pagos en una cuenta por pagar ANULADA.")

            monto_pago = q2(payload.monto)
            saldo_actual = q2(cxp.saldo_pendiente)
            if monto_pago > saldo_actual:
                raise HTTPException(
                    status_code=400,
                    detail="El monto del pago no puede ser mayor al saldo pendiente.",
                )

            pago = PagoCxP(
                cuenta_por_pagar_id=cxp.id,
                monto=monto_pago,
                fecha=payload.fecha,
                forma_pago=payload.forma_pago,
                usuario_auditoria=payload.usuario_auditoria,
                activo=True,
            )
            session.add(pago)

            cxp.pagos_acumulados = q2(cxp.pagos_acumulados + monto_pago)
            nuevo_saldo = q2(cxp.valor_total_factura - cxp.valor_retenido - cxp.pagos_acumulados)
            if nuevo_saldo < Decimal("0.00"):
                raise ValueError("Saldo pendiente invalido luego de aplicar el pago.")

            cxp.saldo_pendiente = nuevo_saldo
            if nuevo_saldo == Decimal("0.00"):
                cxp.estado = EstadoCuentaPorPagar.PAGADA
            elif cxp.pagos_acumulados > Decimal("0.00"):
                cxp.estado = EstadoCuentaPorPagar.PARCIAL
            else:
                cxp.estado = EstadoCuentaPorPagar.PENDIENTE
            session.add(cxp)

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

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import inspect
from sqlalchemy import func
from sqlmodel import Session, select

from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.inventario.producto.entity import Producto
from osiris.modules.sri.core_sri.schemas import ImpuestoAplicadoInput, VentaCompraDetalleCreate
from osiris.modules.sri.core_sri.types import TipoImpuestoMVP
from .entity import (
    EstadoMedidaTemporal,
    MedidaTributariaProducto,
    MedidaTributariaTemporal,
    TipoComponenteTributario,
)
from .models import MedidaProductoInput, MedidaTributariaCreate, MedidaTributariaUpdate
from osiris.modules.ventas.schemas import VentaCreate


class MedidaTributariaService:
    @staticmethod
    def _validate_scope(session: Session, *, empresa_id: UUID, productos: list[MedidaProductoInput], componente: TipoComponenteTributario) -> None:
        empresa = session.get(Empresa, empresa_id)
        if not empresa or not empresa.activo:
            raise HTTPException(status_code=404, detail="Empresa no encontrada o inactiva.")
        product_ids = [item.producto_id for item in productos]
        found = list(
            session.exec(
                select(Producto.id).where(Producto.id.in_(product_ids), Producto.activo.is_(True))  # type: ignore[attr-defined]
            ).all()
        )
        if len(found) != len(set(product_ids)):
            raise HTTPException(status_code=400, detail="Todos los productos deben existir y estar activos.")
        if componente == TipoComponenteTributario.ESPECIFICO:
            if any(item.factor_cantidad is None or not item.unidad_gravable for item in productos):
                raise HTTPException(status_code=400, detail="Cada producto requiere factor y unidad gravable.")

    @staticmethod
    def _replace_targets(session: Session, measure_id: UUID, products: list[MedidaProductoInput], actor: str | None) -> None:
        current = list(
            session.exec(
                select(MedidaTributariaProducto).where(
                    MedidaTributariaProducto.medida_id == measure_id,
                    MedidaTributariaProducto.activo.is_(True),  # type: ignore[attr-defined]
                )
            ).all()
        )
        for target in current:
            target.activo = False
            target.usuario_auditoria = actor
            session.add(target)
        for product in products:
            session.add(
                MedidaTributariaProducto(
                    medida_id=measure_id,
                    producto_id=product.producto_id,
                    factor_cantidad=product.factor_cantidad,
                    unidad_gravable=product.unidad_gravable,
                    usuario_auditoria=actor,
                    activo=True,
                )
            )

    def create(self, session: Session, payload: MedidaTributariaCreate) -> MedidaTributariaTemporal:
        self._validate_scope(
            session,
            empresa_id=payload.empresa_id,
            productos=payload.productos,
            componente=payload.componente,
        )
        measure = MedidaTributariaTemporal(
            empresa_id=payload.empresa_id,
            nombre=payload.nombre.strip(),
            referencia_legal=payload.referencia_legal.strip(),
            tipo_impuesto=payload.tipo_impuesto.value,
            componente=payload.componente,
            fecha_inicio=payload.fecha_inicio,
            fecha_fin=payload.fecha_fin,
            codigo_impuesto_sri=payload.codigo_impuesto_sri,
            codigo_porcentaje_sri=payload.codigo_porcentaje_sri,
            codigo_sri_confirmado=payload.codigo_sri_confirmado,
            tarifa=payload.tarifa,
            estado=EstadoMedidaTemporal.BORRADOR,
            usuario_auditoria=payload.usuario_auditoria,
        )
        session.add(measure)
        session.flush()
        self._replace_targets(session, measure.id, payload.productos, payload.usuario_auditoria)
        session.commit()
        session.refresh(measure)
        return measure

    def update(self, session: Session, measure_id: UUID, payload: MedidaTributariaUpdate) -> MedidaTributariaTemporal:
        measure = session.exec(
            select(MedidaTributariaTemporal)
            .where(MedidaTributariaTemporal.id == measure_id, MedidaTributariaTemporal.activo.is_(True))  # type: ignore[attr-defined]
            .with_for_update()
        ).one_or_none()
        if not measure:
            raise HTTPException(status_code=404, detail="Medida temporal no encontrada.")
        if measure.estado == EstadoMedidaTemporal.ACTIVA:
            raise HTTPException(status_code=409, detail="Desactive la medida antes de modificar sus reglas.")
        changes = payload.model_dump(exclude_unset=True, exclude={"productos", "usuario_auditoria"})
        for key, value in changes.items():
            setattr(measure, key, value.strip() if isinstance(value, str) else value)
        reviewed_fields = {"referencia_legal", "fecha_inicio", "fecha_fin", "codigo_porcentaje_sri", "tarifa"}
        if reviewed_fields.intersection(changes) and "codigo_sri_confirmado" not in changes:
            measure.codigo_sri_confirmado = False
        if payload.productos is not None:
            self._validate_scope(
                session,
                empresa_id=measure.empresa_id,
                productos=payload.productos,
                componente=measure.componente,
            )
            self._replace_targets(session, measure.id, payload.productos, payload.usuario_auditoria)
        measure.usuario_auditoria = payload.usuario_auditoria
        session.add(measure)
        session.commit()
        session.refresh(measure)
        return measure

    def set_state(
        self,
        session: Session,
        measure_id: UUID,
        estado: EstadoMedidaTemporal,
        *,
        actor: str | None,
    ) -> MedidaTributariaTemporal:
        measure = session.exec(
            select(MedidaTributariaTemporal)
            .where(MedidaTributariaTemporal.id == measure_id, MedidaTributariaTemporal.activo.is_(True))  # type: ignore[attr-defined]
            .with_for_update()
        ).one_or_none()
        if not measure:
            raise HTTPException(status_code=404, detail="Medida temporal no encontrada.")
        if estado == EstadoMedidaTemporal.BORRADOR:
            raise HTTPException(status_code=400, detail="Una medida no puede volver a borrador.")
        if estado == EstadoMedidaTemporal.ACTIVA:
            if (
                measure.fecha_fin < measure.fecha_inicio
                or not measure.referencia_legal.strip()
                or not measure.codigo_porcentaje_sri.strip()
                or measure.tarifa < 0
            ):
                raise HTTPException(status_code=400, detail="La medida tiene datos de activación incompletos.")
            expected_tax_code = {"IVA": "2", "ICE": "3"}.get(measure.tipo_impuesto)
            if measure.codigo_impuesto_sri != expected_tax_code:
                raise HTTPException(status_code=400, detail="El código de impuesto no corresponde al tipo tributario.")
            if measure.tipo_impuesto == "IVA" and measure.componente != TipoComponenteTributario.PORCENTUAL:
                raise HTTPException(status_code=400, detail="Las medidas de IVA deben ser porcentuales.")
            if measure.tipo_impuesto == "ICE" and measure.componente == TipoComponenteTributario.PORCENTUAL:
                raise HTTPException(status_code=400, detail="El ICE debe definir componente ad valorem o específico.")
            if not measure.codigo_sri_confirmado:
                raise HTTPException(
                    status_code=400,
                    detail="Confirme el código de porcentaje con la publicación oficial del SRI antes de activar.",
                )
            targets = self._targets(session, measure.id)
            session.exec(
                select(Empresa.id).where(Empresa.id == measure.empresa_id).with_for_update()
            ).first()
            self._validate_scope(
                session,
                empresa_id=measure.empresa_id,
                productos=[
                    MedidaProductoInput(
                        producto_id=item.producto_id,
                        factor_cantidad=item.factor_cantidad,
                        unidad_gravable=item.unidad_gravable,
                    )
                    for item in targets
                ],
                componente=measure.componente,
            )
            if not targets:
                raise HTTPException(status_code=400, detail="La medida requiere al menos un producto elegible.")
            self._validate_no_overlap(session, measure, targets)
        measure.estado = estado
        measure.usuario_auditoria = actor
        session.add(measure)
        session.commit()
        session.refresh(measure)
        return measure

    @staticmethod
    def _targets(session: Session, measure_id: UUID) -> list[MedidaTributariaProducto]:
        return list(
            session.exec(
                select(MedidaTributariaProducto).where(
                    MedidaTributariaProducto.medida_id == measure_id,
                    MedidaTributariaProducto.activo.is_(True),  # type: ignore[attr-defined]
                )
            ).all()
        )

    def _validate_no_overlap(
        self,
        session: Session,
        measure: MedidaTributariaTemporal,
        targets: list[MedidaTributariaProducto],
    ) -> None:
        active_measures = list(
            session.exec(
                select(MedidaTributariaTemporal)
                .where(
                    MedidaTributariaTemporal.empresa_id == measure.empresa_id,
                    MedidaTributariaTemporal.tipo_impuesto == measure.tipo_impuesto,
                    MedidaTributariaTemporal.componente == measure.componente,
                    MedidaTributariaTemporal.estado == EstadoMedidaTemporal.ACTIVA,
                    MedidaTributariaTemporal.activo == True,  # noqa: E712
                    MedidaTributariaTemporal.codigo_sri_confirmado == True,  # noqa: E712
                    MedidaTributariaTemporal.id != measure.id,
                    MedidaTributariaTemporal.fecha_inicio <= measure.fecha_fin,
                    MedidaTributariaTemporal.fecha_fin >= measure.fecha_inicio,
                )
                .with_for_update()
            ).all()
        )
        target_ids = {item.producto_id for item in targets}
        for active in active_measures:
            overlap_ids = {
                item.producto_id for item in self._targets(session, active.id)
            }.intersection(target_ids)
            if overlap_ids:
                raise HTTPException(
                    status_code=409,
                    detail="Existe una medida activa superpuesta para uno o más productos y componentes.",
                )

    def list(self, session: Session, *, empresa_id: UUID | None, limit: int, offset: int) -> tuple[list[MedidaTributariaTemporal], int]:
        stmt = select(MedidaTributariaTemporal).where(MedidaTributariaTemporal.activo.is_(True))  # type: ignore[attr-defined]
        if empresa_id:
            stmt = stmt.where(MedidaTributariaTemporal.empresa_id == empresa_id)
        count = session.exec(select(func.count()).select_from(stmt.subquery())).one()
        rows = list(
            session.exec(
                stmt.order_by(MedidaTributariaTemporal.fecha_inicio.desc(), MedidaTributariaTemporal.creado_en.desc())  # type: ignore[attr-defined]
                .offset(offset)
                .limit(limit)
            ).all()
        )
        return rows, count

    def resolve_sale(self, session: Session, payload: VentaCreate, *, empresa_id: UUID | None) -> VentaCreate:
        if empresa_id is None:
            return payload
        if not inspect(session.get_bind()).has_table(MedidaTributariaTemporal.__tablename__):
            return payload
        active_measures = list(
            session.exec(
                select(MedidaTributariaTemporal)
                .where(
                    MedidaTributariaTemporal.empresa_id == empresa_id,
                    MedidaTributariaTemporal.estado == EstadoMedidaTemporal.ACTIVA,
                    MedidaTributariaTemporal.activo.is_(True),  # type: ignore[attr-defined]
                    MedidaTributariaTemporal.fecha_inicio <= payload.fecha_emision,
                    MedidaTributariaTemporal.fecha_fin >= payload.fecha_emision,
                )
                .order_by(MedidaTributariaTemporal.id)  # type: ignore[arg-type]
            ).all()
        )
        if not active_measures:
            return payload

        products_by_measure = {measure.id: self._targets(session, measure.id) for measure in active_measures}
        details: list[VentaCompraDetalleCreate] = []
        for detail in payload.detalles:
            taxes = list(detail.impuestos)
            for measure in active_measures:
                target = next(
                    (item for item in products_by_measure[measure.id] if item.producto_id == detail.producto_id),
                    None,
                )
                if target is None:
                    continue
                tax_type = TipoImpuestoMVP(measure.tipo_impuesto)
                component = measure.componente
                if component == TipoComponenteTributario.ESPECIFICO:
                    existing_index = next(
                        (index for index, tax in enumerate(taxes) if tax.tipo_impuesto == tax_type and tax.componente == component),
                        None,
                    )
                else:
                    existing_index = next(
                        (index for index, tax in enumerate(taxes) if tax.tipo_impuesto == tax_type and tax.componente in {TipoComponenteTributario.PORCENTUAL, TipoComponenteTributario.AD_VALOREM}),
                        None,
                    )
                replacement = ImpuestoAplicadoInput(
                    tipo_impuesto=tax_type,
                    codigo_impuesto_sri=measure.codigo_impuesto_sri,
                    codigo_porcentaje_sri=measure.codigo_porcentaje_sri,
                    tarifa=measure.tarifa,
                    componente=component,
                    unidad_gravable=target.unidad_gravable,
                    factor_cantidad=target.factor_cantidad or Decimal("1"),
                    medida_temporal_id=measure.id,
                    referencia_legal_temporal=measure.referencia_legal,
                )
                if existing_index is None:
                    taxes.append(replacement)
                else:
                    taxes[existing_index] = replacement
            details.append(
                detail.model_copy(update={"impuestos": taxes})
            )
        return payload.model_copy(update={"detalles": details, "empresa_id": empresa_id})

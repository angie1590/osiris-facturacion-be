from __future__ import annotations

from typing import List
from datetime import date
from decimal import Decimal
from uuid import UUID
from sqlmodel import Session, col, select
from fastapi import HTTPException
from osiris.core.audit import record_domain_change

from osiris.domain.service import BaseService
from osiris.modules.inventario.producto_impuesto.repository import ProductoImpuestoRepository
from osiris.modules.inventario.producto.entity import ProductoImpuesto, Producto, TipoProducto
from osiris.modules.sri.impuesto_catalogo.entity import ImpuestoCatalogo, AplicaA, TipoImpuesto
from osiris.modules.sri.impuesto_catalogo.repository import ImpuestoCatalogoRepository
from osiris.modules.inventario.producto_impuesto.scope import resolve_product_tax_company


class ProductoImpuestoService(BaseService[ProductoImpuesto]):
    repo = ProductoImpuestoRepository()
    impuesto_repo = ImpuestoCatalogoRepository()

    @staticmethod
    def _resolver_tarifa_principal(impuesto: ImpuestoCatalogo) -> Decimal:
        if impuesto.tipo_impuesto.value == "IVA":
            return Decimal(str(impuesto.porcentaje_iva or 0))
        if impuesto.tipo_impuesto.value == "ICE":
            return Decimal(str(impuesto.tarifa_ad_valorem or 0))
        return Decimal("0")

    def listar_impuestos_permitidos(
        self,
        session: Session,
        tipo_producto: TipoProducto,
    ) -> List[ImpuestoCatalogo]:
        empresa = resolve_product_tax_company(session)
        try:
            impuesto_ids = [UUID(str(item)) for item in (empresa.impuesto_catalogo_ids or [])]
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=409,
                detail="La configuración tributaria empresarial es inválida.",
            ) from None
        if not impuesto_ids:
            return []

        impuestos = session.exec(
            select(ImpuestoCatalogo).where(
                col(ImpuestoCatalogo.id).in_(impuesto_ids),
                col(ImpuestoCatalogo.tipo_impuesto).in_([TipoImpuesto.IVA, TipoImpuesto.ICE]),
                col(ImpuestoCatalogo.activo).is_(True),
                col(ImpuestoCatalogo.vigente_desde) <= date.today(),
                col(ImpuestoCatalogo.vigente_hasta).is_(None)
                | (col(ImpuestoCatalogo.vigente_hasta) >= date.today()),
            )
        ).all()
        allowed_ids = set(impuesto_ids)
        compatibles = [
            impuesto
            for impuesto in impuestos
            if impuesto.id in allowed_ids
            and impuesto.tipo_impuesto in {TipoImpuesto.IVA, TipoImpuesto.ICE}
            and self.impuesto_repo.es_vigente(impuesto)
            and impuesto.aplica_a in {AplicaA.AMBOS, AplicaA(tipo_producto.value)}
        ]
        compatibles.sort(
            key=lambda impuesto: (
                0
                if impuesto.tipo_impuesto == TipoImpuesto.IVA
                and impuesto.porcentaje_iva == 0
                and impuesto.clasificacion_iva is None
                and impuesto.aplica_a == AplicaA.AMBOS
                else 1,
                impuesto.descripcion.lower(),
            )
        )
        return compatibles

    def asignar_impuesto(
        self,
        session: Session,
        producto_id: UUID,
        impuesto_catalogo_id: UUID,
        usuario_auditoria: str
    ) -> ProductoImpuesto:
        """
        Asigna un impuesto a un producto con todas las validaciones de negocio.
        """
        try:
            # 1. Validar que el producto existe
            producto = session.get(Producto, producto_id)
            if not producto or not producto.activo:
                raise HTTPException(status_code=404, detail="Producto no encontrado o inactivo")

            # 2. Validar que el impuesto existe y está activo
            impuesto = session.get(ImpuestoCatalogo, impuesto_catalogo_id)
            if not impuesto or not impuesto.activo:
                raise HTTPException(status_code=404, detail="Impuesto no encontrado o inactivo")

            empresa = resolve_product_tax_company(session, producto_id)
            if str(impuesto.id) not in {str(item) for item in (empresa.impuesto_catalogo_ids or [])}:
                raise HTTPException(
                    status_code=400,
                    detail="El impuesto no está configurado para la empresa seleccionada.",
                )
            if impuesto.tipo_impuesto not in {TipoImpuesto.IVA, TipoImpuesto.ICE}:
                raise HTTPException(
                    status_code=400,
                    detail="Solo se permiten impuestos IVA e ICE en productos.",
                )

            # 3. Validar que el impuesto está vigente
            if not self.impuesto_repo.es_vigente(impuesto, date.today()):
                raise HTTPException(
                    status_code=400,
                    detail=f"El impuesto '{impuesto.codigo_sri}' no está vigente actualmente"
                )

            # 4. Validar compatibilidad tipo producto vs aplica_a del impuesto
            self._validar_compatibilidad_tipo(producto.tipo, impuesto.aplica_a)

            # 5. Validar que no se duplique la asignación exacta (mismo impuesto)
            self.repo.validar_duplicado(session, producto_id, impuesto_catalogo_id, empresa.id)

            # 6. Si ya existe un impuesto del mismo tipo, eliminarlo primero (actualización)
            # Esto permite cambiar IVA 0% -> IVA 15%, o actualizar ICE, etc.
            impuestos_existentes = self.list_by_producto(session, producto_id, empresa.id)
            for pi in impuestos_existentes:
                imp_existente = session.get(ImpuestoCatalogo, pi.impuesto_catalogo_id)
                if imp_existente and imp_existente.tipo_impuesto == impuesto.tipo_impuesto:
                    # Marcar como inactivo (soft delete)
                    pi.activo = False
                    session.add(pi)

            # 7. Crear la nueva asignación
            producto_impuesto = ProductoImpuesto(
                producto_id=producto_id,
                empresa_id=empresa.id,
                impuesto_catalogo_id=impuesto_catalogo_id,
                codigo_impuesto_sri=impuesto.codigo_tipo_impuesto,
                codigo_porcentaje_sri=impuesto.codigo_sri,
                tarifa=self._resolver_tarifa_principal(impuesto),
                usuario_auditoria=usuario_auditoria
            )

            creado: ProductoImpuesto = self.repo.create(session, producto_impuesto)
            if isinstance(session, Session):
                remaining_tax_ids = []
                for row in impuestos_existentes:
                    existing_tax = session.get(ImpuestoCatalogo, row.impuesto_catalogo_id)
                    if existing_tax is not None and existing_tax.tipo_impuesto != impuesto.tipo_impuesto:
                        remaining_tax_ids.append(str(row.impuesto_catalogo_id))
                record_domain_change(
                    session,
                    entity="tbl_producto_impuesto",
                    entity_id=producto_id,
                    action="ASSIGN_PRODUCT_TAX",
                    before={
                        "empresa_id": str(empresa.id),
                        "impuesto_catalogo_ids": [str(row.impuesto_catalogo_id) for row in impuestos_existentes],
                    },
                    after={
                        "empresa_id": str(empresa.id),
                        "impuesto_catalogo_ids": remaining_tax_ids + [str(impuesto_catalogo_id)],
                    },
                )
            session.commit()
            session.refresh(creado)
            return creado
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    def _validar_compatibilidad_tipo(self, tipo_producto: TipoProducto, aplica_a: AplicaA) -> None:
        """
        Valida que el tipo de producto sea compatible con el aplica_a del impuesto.
        """
        if aplica_a == AplicaA.AMBOS:
            return  # Compatible con cualquier tipo

        if tipo_producto == TipoProducto.BIEN and aplica_a != AplicaA.BIEN:
            raise HTTPException(
                status_code=400,
                detail="Este impuesto no aplica para productos de tipo BIEN"
            )

        if tipo_producto == TipoProducto.SERVICIO and aplica_a != AplicaA.SERVICIO:
            raise HTTPException(
                status_code=400,
                detail="Este impuesto no aplica para productos de tipo SERVICIO"
            )

    def list_by_producto(
        self,
        session: Session,
        producto_id: UUID,
        empresa_id: UUID | None = None,
    ) -> List[ProductoImpuesto]:
        """Lista todos los impuestos activos de un producto."""
        if empresa_id is None:
            empresa_id = resolve_product_tax_company(session, producto_id).id
        return self.repo.list_by_producto(session, producto_id, empresa_id)

    def eliminar_impuesto(self, session: Session, producto_impuesto_id: UUID) -> bool:
        """
        Elimina (soft delete) una asignación de impuesto.
        NO se puede eliminar el impuesto IVA ya que es obligatorio (requerimiento SRI).
        Para cambiar el IVA, usar asignar_impuesto que reemplaza automáticamente.
        """
        from osiris.modules.sri.impuesto_catalogo.entity import TipoImpuesto

        # Obtener la asignación a eliminar
        producto_impuesto = session.get(ProductoImpuesto, producto_impuesto_id)
        if not producto_impuesto or not producto_impuesto.activo:
            raise HTTPException(status_code=404, detail="Asignación de impuesto no encontrada")

        empresa = resolve_product_tax_company(session, producto_impuesto.producto_id)
        if producto_impuesto.empresa_id != empresa.id:
            raise HTTPException(status_code=404, detail="Asignación de impuesto no encontrada")

        # Obtener el impuesto para verificar si es IVA
        impuesto = session.get(ImpuestoCatalogo, producto_impuesto.impuesto_catalogo_id)

        # No se puede eliminar IVA - solo se puede actualizar/reemplazar
        if impuesto and impuesto.tipo_impuesto == TipoImpuesto.IVA:
            raise HTTPException(
                status_code=400,
                detail="No se puede eliminar el impuesto IVA. El IVA es obligatorio para todos los productos (requerimiento SRI). Para cambiar el IVA, asigne un nuevo IVA que reemplazará automáticamente el anterior."
            )

        try:
            before = {
                "empresa_id": str(empresa.id),
                "producto_id": str(producto_impuesto.producto_id),
                "impuesto_catalogo_id": str(producto_impuesto.impuesto_catalogo_id),
            }
            deleted = self.repo.delete_by_id(session, producto_impuesto_id)
            if deleted and isinstance(session, Session):
                record_domain_change(
                    session,
                    entity="tbl_producto_impuesto",
                    entity_id=producto_impuesto.producto_id,
                    action="DELETE_PRODUCT_TAX",
                    before=before,
                    after={"empresa_id": str(empresa.id), "activo": False},
                )
            session.commit()
            return deleted
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    def get_impuestos_completos(self, session: Session, producto_id: UUID) -> List[ImpuestoCatalogo]:
        """
        Obtiene la lista completa de impuestos (con toda su información del catálogo)
        asignados a un producto.
        """
        empresa = resolve_product_tax_company(session, producto_id)
        producto_impuestos = self.list_by_producto(session, producto_id, empresa.id)

        impuestos = []
        for pi in producto_impuestos:
            impuesto = session.get(ImpuestoCatalogo, pi.impuesto_catalogo_id)
            if impuesto and impuesto.activo:
                impuestos.append(impuesto)

        return impuestos

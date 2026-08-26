from __future__ import annotations

from typing import List
from datetime import date
from decimal import Decimal
from uuid import UUID
from sqlmodel import Session
from fastapi import HTTPException

from osiris.domain.service import BaseService
from osiris.modules.inventario.producto_impuesto.repository import ProductoImpuestoRepository
from osiris.modules.inventario.producto.entity import ProductoImpuesto, Producto, TipoProducto
from osiris.modules.sri.impuesto_catalogo.entity import ImpuestoCatalogo, AplicaA
from osiris.modules.sri.impuesto_catalogo.repository import ImpuestoCatalogoRepository


class ProductoImpuestoService(BaseService):
    repo = ProductoImpuestoRepository()
    impuesto_repo = ImpuestoCatalogoRepository()

    @staticmethod
    def _resolver_tarifa_principal(impuesto: ImpuestoCatalogo) -> Decimal:
        if impuesto.tipo_impuesto.value == "IVA":
            return Decimal(str(impuesto.porcentaje_iva or 0))
        if impuesto.tipo_impuesto.value == "ICE":
            return Decimal(str(impuesto.tarifa_ad_valorem or 0))
        return Decimal("0")

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

            # 3. Validar que el impuesto está vigente
            if not self.impuesto_repo.es_vigente(impuesto, date.today()):
                raise HTTPException(
                    status_code=400,
                    detail=f"El impuesto '{impuesto.codigo_sri}' no está vigente actualmente"
                )

            # 4. Validar compatibilidad tipo producto vs aplica_a del impuesto
            self._validar_compatibilidad_tipo(producto.tipo, impuesto.aplica_a)

            # 5. Validar que no se duplique la asignación exacta (mismo impuesto)
            self.repo.validar_duplicado(session, producto_id, impuesto_catalogo_id)

            # 6. Si ya existe un impuesto del mismo tipo, eliminarlo primero (actualización)
            # Esto permite cambiar IVA 0% -> IVA 15%, o actualizar ICE, etc.
            impuestos_existentes = self.list_by_producto(session, producto_id)
            for pi in impuestos_existentes:
                imp_existente = session.get(ImpuestoCatalogo, pi.impuesto_catalogo_id)
                if imp_existente and imp_existente.tipo_impuesto == impuesto.tipo_impuesto:
                    # Marcar como inactivo (soft delete)
                    pi.activo = False
                    session.add(pi)

            # 7. Crear la nueva asignación
            producto_impuesto = ProductoImpuesto(
                producto_id=producto_id,
                impuesto_catalogo_id=impuesto_catalogo_id,
                codigo_impuesto_sri=impuesto.codigo_tipo_impuesto,
                codigo_porcentaje_sri=impuesto.codigo_sri,
                tarifa=self._resolver_tarifa_principal(impuesto),
                usuario_auditoria=usuario_auditoria
            )

            creado = self.repo.create(session, producto_impuesto)
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

    def list_by_producto(self, session: Session, producto_id: UUID) -> List[ProductoImpuesto]:
        """Lista todos los impuestos activos de un producto."""
        return self.repo.list_by_producto(session, producto_id)

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

        # Obtener el impuesto para verificar si es IVA
        impuesto = session.get(ImpuestoCatalogo, producto_impuesto.impuesto_catalogo_id)

        # No se puede eliminar IVA - solo se puede actualizar/reemplazar
        if impuesto and impuesto.tipo_impuesto == TipoImpuesto.IVA:
            raise HTTPException(
                status_code=400,
                detail="No se puede eliminar el impuesto IVA. El IVA es obligatorio para todos los productos (requerimiento SRI). Para cambiar el IVA, asigne un nuevo IVA que reemplazará automáticamente el anterior."
            )

        try:
            deleted = self.repo.delete_by_id(session, producto_impuesto_id)
            session.commit()
            return deleted
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    def get_impuestos_completos(self, session: Session, producto_id: UUID) -> List[ImpuestoCatalogo]:
        """
        Obtiene la lista completa de impuestos (con toda su información del catálogo)
        asignados a un producto.
        """
        producto_impuestos = self.list_by_producto(session, producto_id)

        impuestos = []
        for pi in producto_impuestos:
            impuesto = session.get(ImpuestoCatalogo, pi.impuesto_catalogo_id)
            if impuesto and impuesto.activo:
                impuestos.append(impuesto)

        return impuestos

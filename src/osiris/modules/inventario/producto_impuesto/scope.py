from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, col, select

from osiris.core.company_scope import resolve_company_scope
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.inventario.bodega.entity import Bodega
from osiris.modules.inventario.producto.entity import ProductoBodega, ProductoImpuesto


def resolve_product_tax_company(session: Session, producto_id: UUID | None = None) -> Empresa:
    """Resuelve empresa del perfil fiscal desde auth o un único scope de bodegas."""
    empresa_id = resolve_company_scope()
    if empresa_id is None and producto_id is None:
        active_company_ids = session.exec(
            select(Empresa.id).where(col(Empresa.activo).is_(True))
        ).all()
        if len(active_company_ids) == 1:
            empresa_id = active_company_ids[0]
        else:
            raise HTTPException(
                status_code=409,
                detail=(
                    "No se puede resolver una empresa única para el perfil fiscal. "
                    "Seleccione una empresa autenticada."
                ),
            )
    if empresa_id is None and producto_id is not None:
        empresa_ids = set(
            session.exec(
                select(Bodega.empresa_id)
                .join(ProductoBodega, col(ProductoBodega.bodega_id) == col(Bodega.id))
                .where(
                    col(ProductoBodega.producto_id) == producto_id,
                    col(ProductoBodega.activo).is_(True),
                    col(Bodega.activo).is_(True),
                )
                .distinct()
            ).all()
        )
        tax_company_ids = session.exec(
            select(ProductoImpuesto.empresa_id)
            .where(
                col(ProductoImpuesto.producto_id) == producto_id,
                col(ProductoImpuesto.activo).is_(True),
                col(ProductoImpuesto.empresa_id).is_not(None),
            )
            .distinct()
        ).all()
        empresa_ids.update(company_id for company_id in tax_company_ids if company_id)
        if len(empresa_ids) == 1:
            empresa_id = next(iter(empresa_ids))
        else:
            raise HTTPException(
                status_code=409,
                detail=(
                    "No se puede resolver una empresa única para el perfil fiscal del producto. "
                    "Seleccione una empresa autenticada o concilie sus bodegas activas."
                ),
            )
    if empresa_id is None:
        raise HTTPException(
            status_code=409,
            detail="El perfil fiscal requiere una empresa autenticada en el contexto de sesión.",
        )

    empresa = session.get(Empresa, empresa_id)
    if not empresa or not empresa.activo:
        raise HTTPException(status_code=403, detail="La empresa del perfil fiscal no existe o está inactiva.")
    return empresa
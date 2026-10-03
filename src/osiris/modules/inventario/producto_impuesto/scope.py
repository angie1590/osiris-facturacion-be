from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, col, select

from osiris.core.company_scope import resolve_company_scope
from osiris.modules.common.empresa.entity import Empresa
from osiris.modules.inventario.bodega.entity import Bodega
from osiris.modules.inventario.producto.entity import ProductoBodega


def resolve_product_tax_company(session: Session, producto_id: UUID | None = None) -> Empresa:
    """Resuelve empresa del perfil fiscal desde auth o un único scope de bodegas."""
    empresa_id = resolve_company_scope()
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
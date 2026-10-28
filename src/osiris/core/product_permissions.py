from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Mapping
from types import MappingProxyType
from typing import Literal
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlmodel import Session

from osiris.core.audit_context import reset_current_user_id, set_current_user_id
from osiris.core.auth import get_current_usuario
from osiris.core.db import get_session
from osiris.core.permisos import AccionPermiso, requiere_permiso
from osiris.modules.common.rol.entity import Rol
from osiris.modules.common.usuario.entity import Usuario

ProductOperation = Literal["read", "create", "update", "delete"]
PRODUCT_PERMISSIONS: Mapping[ProductOperation, AccionPermiso] = MappingProxyType(
    {
        "read": "leer",
        "create": "crear",
        "update": "actualizar",
        "delete": "eliminar",
    }
)


def require_product_permission(
    session: Session, user_id: UUID, operation: ProductOperation
) -> Usuario:
    action = PRODUCT_PERMISSIONS[operation]
    with session.no_autoflush:
        user = session.get(Usuario, user_id)
        if user is None or not user.activo:
            raise HTTPException(status_code=403, detail="Usuario inactivo o no disponible")
        role = session.get(Rol, user.rol_id)
        if role is None or not role.activo:
            raise HTTPException(status_code=403, detail="Rol inactivo o no disponible")
        requiere_permiso(session, user.id, "PRODUCTOS", action)
    return user


def product_permission(
    operation: ProductOperation,
) -> Callable[..., AsyncGenerator[Usuario, None]]:
    PRODUCT_PERMISSIONS[operation]

    async def guard(
        user: Usuario = Depends(get_current_usuario),
        session: Session = Depends(get_session),
    ) -> AsyncGenerator[Usuario, None]:
        actor = require_product_permission(session, user.id, operation)
        token = set_current_user_id(str(actor.id))
        try:
            yield actor
        finally:
            reset_current_user_id(token)

    return guard


read_product_permission = product_permission("read")
create_product_permission = product_permission("create")
update_product_permission = product_permission("update")
delete_product_permission = product_permission("delete")

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

CatalogOperation = Literal[
    "read_categories",
    "create_category",
    "update_category",
    "move_category",
    "deactivate_category",
    "reactivate_category",
    "read_category_attributes",
    "configure_mapping",
    "assign_attribute",
    "override_mapping",
    "remove_mapping",
    "reactivate_mapping",
    "backfill_mapping",
    "preview_mapping",
    "create_and_assign_attribute",
    "read_attributes",
    "create_attribute",
    "update_attribute",
    "deactivate_attribute",
    "reactivate_attribute",
    "undo_attribute_change",
    "annotate_attribute_unit",
    "preview_attribute_update",
    "preview_attribute_deactivation",
    "read_units",
    "create_unit",
    "update_unit",
    "deactivate_unit",
    "reactivate_unit",
]
CatalogPermission = tuple[str, AccionPermiso]
CATALOG_MODULE_NAMES: Mapping[str, str] = MappingProxyType(
    {
        "CATEGORIAS": "Categorías",
        "ATRIBUTOS": "Atributos",
        "UNIDADES": "Unidades",
        "PRODUCTOS": "Productos",
    }
)

CATALOG_PERMISSIONS: Mapping[CatalogOperation, tuple[CatalogPermission, ...]] = MappingProxyType(
    {
        "read_categories": (("CATEGORIAS", "leer"),),
        "create_category": (("CATEGORIAS", "crear"),),
        "update_category": (("CATEGORIAS", "actualizar"),),
        "move_category": (("CATEGORIAS", "actualizar"),),
        "deactivate_category": (("CATEGORIAS", "eliminar"),),
        "reactivate_category": (("CATEGORIAS", "actualizar"),),
        "read_category_attributes": (("CATEGORIAS", "leer"), ("ATRIBUTOS", "leer")),
        "configure_mapping": (("CATEGORIAS", "actualizar"), ("ATRIBUTOS", "leer")),
        "assign_attribute": (("CATEGORIAS", "actualizar"), ("ATRIBUTOS", "leer")),
        "override_mapping": (("CATEGORIAS", "actualizar"), ("ATRIBUTOS", "leer")),
        "remove_mapping": (("CATEGORIAS", "actualizar"), ("ATRIBUTOS", "leer")),
        "reactivate_mapping": (("CATEGORIAS", "actualizar"), ("ATRIBUTOS", "leer")),
        "backfill_mapping": (("CATEGORIAS", "actualizar"), ("ATRIBUTOS", "leer")),
        "preview_mapping": (("CATEGORIAS", "actualizar"), ("ATRIBUTOS", "leer")),
        "create_and_assign_attribute": (
            ("CATEGORIAS", "actualizar"),
            ("ATRIBUTOS", "leer"),
            ("ATRIBUTOS", "crear"),
        ),
        "read_attributes": (("ATRIBUTOS", "leer"),),
        "create_attribute": (("ATRIBUTOS", "crear"),),
        "update_attribute": (("ATRIBUTOS", "actualizar"),),
        "deactivate_attribute": (("ATRIBUTOS", "eliminar"),),
        "reactivate_attribute": (("ATRIBUTOS", "actualizar"),),
        "undo_attribute_change": (("ATRIBUTOS", "actualizar"),),
        "annotate_attribute_unit": (("ATRIBUTOS", "actualizar"),),
        "preview_attribute_update": (("ATRIBUTOS", "actualizar"),),
        "preview_attribute_deactivation": (("ATRIBUTOS", "eliminar"),),
        "read_units": (("UNIDADES", "leer"),),
        "create_unit": (("UNIDADES", "crear"),),
        "update_unit": (("UNIDADES", "actualizar"),),
        "deactivate_unit": (("UNIDADES", "eliminar"),),
        "reactivate_unit": (("UNIDADES", "actualizar"),),
    }
)


def require_catalog_permission(
    session: Session, user_id: UUID, operation: CatalogOperation
) -> Usuario:
    """Check every effective grant without flushing or owning the caller's transaction."""
    requirements = CATALOG_PERMISSIONS[operation]
    with session.no_autoflush:
        usuario = session.get(Usuario, user_id)
        if usuario is None or not usuario.activo:
            raise HTTPException(status_code=403, detail="Usuario inactivo o no disponible")
        role = session.get(Rol, usuario.rol_id)
        if role is None or not role.activo:
            raise HTTPException(status_code=403, detail="Rol inactivo o no disponible")
        for module, action in requirements:
            requiere_permiso(session, usuario.id, module, action)
    return usuario


def catalog_permission(operation: CatalogOperation) -> Callable[..., AsyncGenerator[Usuario, None]]:
    """Return the authenticated actor and scope audit context to the consuming caller.

    Unknown operations fail at dependency construction. No routes are registered here.
    The synchronous helper alone does not establish an audit context.
    """
    CATALOG_PERMISSIONS[operation]

    async def guard(
        usuario: Usuario = Depends(get_current_usuario),
        session: Session = Depends(get_session),
    ) -> AsyncGenerator[Usuario, None]:
        actor = require_catalog_permission(session, usuario.id, operation)
        token = set_current_user_id(str(actor.id))
        try:
            yield actor
        finally:
            reset_current_user_id(token)

    return guard

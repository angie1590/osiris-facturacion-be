# src/osiris/modules/common/rol_modulo_permiso/models.py
from datetime import datetime
from typing import Optional
from uuid import UUID
from osiris.domain.base_models import BaseOSModel


class RolModuloPermisoCreate(BaseOSModel):
    rol_id: UUID
    modulo_id: UUID
    puede_leer: bool = False
    puede_crear: bool = False
    puede_actualizar: bool = False
    puede_eliminar: bool = False
    usuario_auditoria: Optional[str] = None


class RolModuloPermisoUpdate(BaseOSModel):
    puede_leer: Optional[bool] = None
    puede_crear: Optional[bool] = None
    puede_actualizar: Optional[bool] = None
    puede_eliminar: Optional[bool] = None
    usuario_auditoria: Optional[str] = None


class RolModuloPermisoRead(BaseOSModel):
    id: UUID
    rol_id: UUID
    modulo_id: UUID
    puede_leer: bool
    puede_crear: bool
    puede_actualizar: bool
    puede_eliminar: bool
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    usuario_auditoria: Optional[str] = None


# Modelo para respuesta de permisos por módulo (usado en endpoint de usuario)
class ModuloPermisoRead(BaseOSModel):
    codigo: str
    nombre: str
    puede_leer: bool
    puede_crear: bool
    puede_actualizar: bool
    puede_eliminar: bool

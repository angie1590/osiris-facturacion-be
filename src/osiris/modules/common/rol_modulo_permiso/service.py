from typing import List
from uuid import UUID
from sqlmodel import Session, col, select
from osiris.domain.service import BaseService
from osiris.core.auth import is_admin_role
from osiris.core.catalog_permissions import CATALOG_MODULE_NAMES
from .repository import RolModuloPermisoRepository
from .entity import RolModuloPermiso
from .models import ModuloPermisoRead
from osiris.modules.common.modulo.entity import Modulo
from osiris.modules.common.rol.entity import Rol


class RolModuloPermisoService(BaseService[RolModuloPermiso]):
    repo = RolModuloPermisoRepository()

    def obtener_permisos_por_rol(
        self, session: Session, rol_id: UUID
    ) -> List[ModuloPermisoRead]:
        """
        Retorna lista de módulos con sus permisos para un rol específico.
        Solo incluye registros activos y módulos activos.
        """
        statement = (
            select(Modulo, RolModuloPermiso)
            .outerjoin(
                RolModuloPermiso,
                (col(Modulo.id) == RolModuloPermiso.modulo_id)
                & (col(RolModuloPermiso.rol_id) == rol_id)
                & (col(RolModuloPermiso.activo).is_(True)),
            )
            .where(col(Modulo.activo).is_(True))
            .order_by(col(Modulo.orden), Modulo.nombre)
        )

        results = session.exec(statement).all()
        role = session.get(Rol, rol_id)
        active_role = bool(role and role.activo)
        admin_role = is_admin_role(role)

        permisos_list = []
        for modulo, permiso in results:
            permisos_list.append(
                ModuloPermisoRead(
                    codigo=modulo.codigo,
                    nombre=modulo.nombre,
                    puede_leer=active_role and (admin_role or (permiso.puede_leer if permiso else False)),
                    puede_crear=active_role and (admin_role or (permiso.puede_crear if permiso else False)),
                    puede_actualizar=active_role and (admin_role or (permiso.puede_actualizar if permiso else False)),
                    puede_eliminar=active_role and (admin_role or (permiso.puede_eliminar if permiso else False)),
                )
            )

        if admin_role:
            present_codes = {permission.codigo for permission in permisos_list}
            for code, name in CATALOG_MODULE_NAMES.items():
                if code not in present_codes:
                    permisos_list.append(
                        ModuloPermisoRead(
                            codigo=code,
                            nombre=name,
                            puede_leer=True,
                            puede_crear=True,
                            puede_actualizar=True,
                            puede_eliminar=True,
                        )
                    )

        return permisos_list

    def obtener_menu_por_rol(
        self, session: Session, rol_id: UUID
    ) -> List[ModuloPermisoRead]:
        """
        Retorna solo los módulos donde el rol tiene puede_leer = True.
        Útil para generar el menú dinámico.
        """
        permisos = self.obtener_permisos_por_rol(session, rol_id)
        return [p for p in permisos if p.puede_leer]

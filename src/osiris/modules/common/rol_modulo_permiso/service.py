from typing import List
from uuid import UUID
from sqlmodel import Session, select
from osiris.domain.service import BaseService
from .repository import RolModuloPermisoRepository
from .entity import RolModuloPermiso
from .models import ModuloPermisoRead
from osiris.modules.common.modulo.entity import Modulo


class RolModuloPermisoService(BaseService):
    repo = RolModuloPermisoRepository()

    def obtener_permisos_por_rol(self, session: Session, rol_id: UUID) -> List[ModuloPermisoRead]:
        """
        Retorna lista de módulos con sus permisos para un rol específico.
        Solo incluye registros activos y módulos activos.
        """
        statement = (
            select(Modulo, RolModuloPermiso)
            .outerjoin(
                RolModuloPermiso,
                (Modulo.id == RolModuloPermiso.modulo_id)
                & (RolModuloPermiso.rol_id == rol_id)
                & (RolModuloPermiso.activo.is_(True))
            )
            .where(Modulo.activo.is_(True))
            .order_by(Modulo.orden, Modulo.nombre)
        )

        results = session.exec(statement).all()

        permisos_list = []
        for modulo, permiso in results:
            permisos_list.append(
                ModuloPermisoRead(
                    codigo=modulo.codigo,
                    nombre=modulo.nombre,
                    puede_leer=permiso.puede_leer if permiso else False,
                    puede_crear=permiso.puede_crear if permiso else False,
                    puede_actualizar=permiso.puede_actualizar if permiso else False,
                    puede_eliminar=permiso.puede_eliminar if permiso else False,
                )
            )

        return permisos_list

    def obtener_menu_por_rol(self, session: Session, rol_id: UUID) -> List[ModuloPermisoRead]:
        """
        Retorna solo los módulos donde el rol tiene puede_leer = True.
        Útil para generar el menú dinámico.
        """
        permisos = self.obtener_permisos_por_rol(session, rol_id)
        return [p for p in permisos if p.puede_leer]

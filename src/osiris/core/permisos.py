# src/osiris/core/permisos.py
from typing import Literal
from uuid import UUID
from fastapi import HTTPException, status
from sqlmodel import Session, select

from osiris.modules.common.usuario.entity import Usuario
from osiris.modules.common.rol_modulo_permiso.entity import RolModuloPermiso
from osiris.modules.common.modulo.entity import Modulo


AccionPermiso = Literal["leer", "crear", "actualizar", "eliminar"]


def verificar_permiso(
    session: Session,
    usuario_id: UUID,
    codigo_modulo: str,
    accion: AccionPermiso
) -> bool:
    """
    Verifica si un usuario tiene permiso para realizar una acción en un módulo.

    Args:
        session: Sesión de BD
        usuario_id: UUID del usuario
        codigo_modulo: Código del módulo (ej: "VENTAS", "INVENTARIO")
        accion: Acción a verificar ("leer", "crear", "actualizar", "eliminar")

    Returns:
        True si tiene permiso, False si no
    """
    # Obtener usuario
    usuario = session.get(Usuario, usuario_id)
    if not usuario or not usuario.activo:
        return False

    # Obtener módulo
    modulo_stmt = select(Modulo).where(Modulo.codigo == codigo_modulo, Modulo.activo.is_(True))
    modulo = session.exec(modulo_stmt).first()
    if not modulo:
        return False

    # Obtener permiso
    permiso_stmt = select(RolModuloPermiso).where(
        RolModuloPermiso.rol_id == usuario.rol_id,
        RolModuloPermiso.modulo_id == modulo.id,
        RolModuloPermiso.activo.is_(True)
    )
    permiso = session.exec(permiso_stmt).first()

    if not permiso:
        return False

    # Verificar acción específica
    if accion == "leer":
        return permiso.puede_leer
    elif accion == "crear":
        return permiso.puede_crear
    elif accion == "actualizar":
        return permiso.puede_actualizar
    elif accion == "eliminar":
        return permiso.puede_eliminar

    return False


def requiere_permiso(
    session: Session,
    usuario_id: UUID,
    codigo_modulo: str,
    accion: AccionPermiso
):
    """
    Valida permiso y lanza HTTPException 403 si no tiene acceso.
    Útil para usar en endpoints.

    Ejemplo:
        @router.get("/ventas")
        def listar_ventas(
            usuario_id: UUID,
            session: Session = Depends(get_session)
        ):
            requiere_permiso(session, usuario_id, "VENTAS", "leer")
            # ... resto del endpoint
    """
    if not verificar_permiso(session, usuario_id, codigo_modulo, accion):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No tiene permiso para {accion} en el módulo {codigo_modulo}"
        )

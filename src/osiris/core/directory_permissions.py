from __future__ import annotations

import logging
import re
from typing import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from osiris.core.auth import get_current_usuario
from osiris.core.db import get_session
from osiris.core.permisos import AccionPermiso, requiere_permiso
from osiris.core.security_audit import SensitiveEndpointRule, log_unauthorized_access
from osiris.modules.common.rol.entity import Rol
from osiris.modules.common.usuario.entity import Usuario


def _record_denial(session: Session, request: Request, user_id: UUID, module: str, action: AccionPermiso, error: HTTPException) -> None:
    session.rollback()
    try:
        log_unauthorized_access(
            session, request=request, user_id=str(user_id), payload=None,
            reason=str(error.detail), rule=SensitiveEndpointRule(
                method=request.method, path_regex=re.compile(re.escape(request.url.path) + "$"),
                modulo_codigo=module, accion=action,
            ),
        )
    except Exception:
        session.rollback()
        logging.getLogger(__name__).exception("No se pudo registrar acceso denegado del Directorio")


def require_directory_permission(session: Session, user_id: UUID, module: str, action: AccionPermiso) -> None:
    try:
        requiere_permiso(session, user_id, module, action)
    except HTTPException as error:
        request = session.info.get("directory_permission_request")
        if error.status_code == 403 and isinstance(request, Request):
            _record_denial(session, request, user_id, module, action, error)
        raise


def directory_permission(module: str, action: AccionPermiso) -> Callable[..., Usuario]:
    def guard(
        request: Request,
        usuario: Usuario = Depends(get_current_usuario),
        session: Session = Depends(get_session),
    ) -> Usuario:
        session.info["directory_permission_request"] = request
        role = session.get(Rol, usuario.rol_id)
        if role is None or role.activo is False:
            error = HTTPException(status_code=403, detail="Rol inactivo o no disponible")
            _record_denial(session, request, usuario.id, module, action, error)
            raise error
        require_directory_permission(session, usuario.id, module, action)
        return usuario

    return guard
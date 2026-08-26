from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.redis import get_redis
from app.core.security import decode_token
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate JWT, check blacklist, return active user."""
    try:
        payload = decode_token(token)
    except JWTError:
        raise UnauthorizedError("INVALID_TOKEN", "Token is invalid or expired")

    if payload.get("type") != "access":
        raise UnauthorizedError("INVALID_TOKEN", "Not an access token")

    redis = await get_redis()
    if await redis.get(f"blacklist:{token}"):
        raise UnauthorizedError("TOKEN_REVOKED", "Token has been revoked")

    user_id = int(payload["sub"])
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user or not user.is_active:
        raise UnauthorizedError("ACCOUNT_INACTIVE", "Account is inactive")

    return user


async def get_current_empresa_id(request: Request, user: User = Depends(get_current_user)) -> int:
    """Empresa activa: header X-Empresa-Id (validado contra accesos del usuario) o única empresa asignada."""
    empresa_ids = {ue.empresa_id for ue in user.empresas}
    if not empresa_ids:
        raise ForbiddenError("NO_EMPRESA_ASSIGNED", "El usuario no tiene empresas asignadas")

    header_value = request.headers.get("X-Empresa-Id")
    if header_value:
        empresa_id = int(header_value)
        if empresa_id not in empresa_ids:
            raise ForbiddenError("EMPRESA_NOT_ALLOWED", "No tienes acceso a esta empresa")
        return empresa_id

    if len(empresa_ids) == 1:
        return next(iter(empresa_ids))

    raise ForbiddenError("EMPRESA_HEADER_REQUIRED", "Debe especificar X-Empresa-Id")


_ROLE_LABELS = {
    UserRole.admin: "Administrador",
    UserRole.operator: "Operador",
    UserRole.supervisor: "Supervisor",
}


def require_role(*roles: UserRole):
    """FastAPI dependency que exige uno de los roles indicados."""

    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            labels = ", ".join(_ROLE_LABELS.get(r, r.value) for r in roles)
            raise ForbiddenError(
                detail=f"No tienes permiso para realizar esta acción. Requiere rol: {labels}."
            )
        return user

    return _check


require_admin = require_role(UserRole.admin)
require_admin_or_supervisor = require_role(UserRole.admin, UserRole.supervisor)
require_any_role = require_role(UserRole.admin, UserRole.operator, UserRole.supervisor)

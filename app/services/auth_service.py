from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.models.user import RefreshToken, User
from app.repositories.user_repository import UserRepository, hash_token


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)

    async def login(self, username: str, password: str) -> dict:
        user = await self.user_repo.get_by_username(username.lower())
        if not user or not verify_password(password, user.hashed_password):
            raise UnauthorizedError("INVALID_CREDENTIALS", "Invalid credentials")
        if not user.is_active:
            raise UnauthorizedError("ACCOUNT_INACTIVE", "Account is inactive")

        empresa_ids = [ue.empresa_id for ue in user.empresas if ue.is_active]
        access_token = create_access_token(
            user.id,
            extra_claims={"role": user.role.value, "username": user.username, "empresas": empresa_ids},
        )
        refresh_token_str = create_refresh_token(user.id)

        rt = RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh_token_str),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        await self.user_repo.save_refresh_token(rt)
        await self.db.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token_str,
            "token_type": "bearer",
            "require_password_change": user.must_change_password,
        }

    async def refresh(self, refresh_token_str: str) -> dict:
        rt = await self.user_repo.get_refresh_token_by_hash(hash_token(refresh_token_str))
        if not rt:
            raise UnauthorizedError("TOKEN_REVOKED", "Refresh token is invalid or revoked")
        if rt.expires_at < datetime.now(timezone.utc):
            raise UnauthorizedError("TOKEN_EXPIRED", "Refresh token has expired")

        user = await self.user_repo.get_by_id(rt.user_id)
        if not user or not user.is_active:
            raise UnauthorizedError("ACCOUNT_INACTIVE", "Account is inactive")

        await self.user_repo.revoke_refresh_token(rt)

        empresa_ids = [ue.empresa_id for ue in user.empresas if ue.is_active]
        access_token = create_access_token(
            user.id,
            extra_claims={"role": user.role.value, "username": user.username, "empresas": empresa_ids},
        )
        new_refresh_token = create_refresh_token(user.id)
        new_rt = RefreshToken(
            user_id=user.id,
            token_hash=hash_token(new_refresh_token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        await self.user_repo.save_refresh_token(new_rt)
        await self.db.commit()

        return {"access_token": access_token, "refresh_token": new_refresh_token, "token_type": "bearer"}

    async def logout(self, user: User) -> None:
        await self.user_repo.revoke_all_refresh_tokens(user.id)
        await self.db.commit()

    async def change_password(self, user: User, current_password: str | None, new_password: str) -> None:
        if not user.must_change_password:
            if not current_password or not verify_password(current_password, user.hashed_password):
                raise UnauthorizedError("INVALID_CREDENTIALS", "Current password is incorrect")
        user.hashed_password = hash_password(new_password)
        user.must_change_password = False
        await self.db.commit()

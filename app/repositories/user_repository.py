import hashlib
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import RefreshToken, User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.db.execute(
            select(User).options(selectinload(User.empresas)).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self.db.execute(
            select(User).options(selectinload(User.empresas)).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def save_refresh_token(self, rt: RefreshToken) -> RefreshToken:
        self.db.add(rt)
        await self.db.flush()
        return rt

    async def get_refresh_token_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def revoke_refresh_token(self, rt: RefreshToken) -> None:
        rt.revoked_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def revoke_all_refresh_tokens(self, user_id: int) -> None:
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

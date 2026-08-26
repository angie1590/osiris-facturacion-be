import asyncio

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.user_repository import UserRepository


async def main() -> None:
    async with AsyncSessionLocal() as db:
        repo = UserRepository(db)
        if await repo.get_by_username("admin"):
            print("Admin ya existe, omitiendo seed.")
            return
        admin = User(
            username="admin",
            hashed_password=hash_password("Admin@12345!"),
            full_name="Administrador",
            role=UserRole.admin,
            must_change_password=True,
        )
        db.add(admin)
        await db.commit()
        print("Admin creado: admin / Admin@12345!")


if __name__ == "__main__":
    asyncio.run(main())

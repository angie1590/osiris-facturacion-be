import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.enums import IdentificationType, UserRole
from app.models.empresa import Empresa
from app.models.user import User, UsuarioEmpresa
from app.repositories.user_repository import UserRepository


async def main() -> None:
    async with AsyncSessionLocal() as db:
        repo = UserRepository(db)
        admin = await repo.get_by_username("admin")

        if not admin:
            admin = User(
                username="admin",
                hashed_password=hash_password("Admin@12345!"),
                full_name="Administrador",
                role=UserRole.admin,
                must_change_password=False,
            )
            db.add(admin)
            await db.flush()
            print("Admin creado: admin / Admin@12345!")
        else:
            admin.hashed_password = hash_password("Admin@12345!")
            admin.must_change_password = False
            print("Admin ya existe")

        result = await db.execute(select(Empresa).where(Empresa.ruc == "0000000001"))
        empresa = result.scalar_one_or_none()
        if empresa is None:
            empresa = Empresa(
                ruc="0000000001",
                razon_social="Mi Empresa Demo",
                identification_type=IdentificationType.ruc,
                obligado_contabilidad=True,
                is_active=True,
            )
            db.add(empresa)
            await db.flush()
            print("Empresa creada: Mi Empresa Demo")
        else:
            print("Empresa ya existe")

        result = await db.execute(
            select(UsuarioEmpresa).where(
                UsuarioEmpresa.user_id == admin.id,
                UsuarioEmpresa.empresa_id == empresa.id,
            )
        )
        if result.scalar_one_or_none() is None:
            db.add(
                UsuarioEmpresa(
                user_id=admin.id,
                empresa_id=empresa.id,
                role=UserRole.admin,
                is_active=True,
                )
            )
            print(f"Admin asignado a empresa {empresa.razon_social}")
        else:
            print("Admin ya está asignado a empresa")

        await db.commit()
        print("Seed completado")


if __name__ == "__main__":
    asyncio.run(main())

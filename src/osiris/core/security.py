from passlib.context import CryptContext

PASSWORD_MIN_LENGTH = 8


def validate_password(plain: str) -> str:
    if not isinstance(plain, str) or len(plain) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"La contrasena debe tener al menos {PASSWORD_MIN_LENGTH} caracteres")
    return plain

# bcrypt es el estándar seguro y ampliamente soportado
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)

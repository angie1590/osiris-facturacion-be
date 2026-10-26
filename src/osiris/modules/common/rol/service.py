from osiris.domain.service import BaseService
from .entity import Rol
from .repository import RolRepository

class RolService(BaseService[Rol]):
    repo = RolRepository()
    pass  # hooks disponibles si luego necesitas reglas

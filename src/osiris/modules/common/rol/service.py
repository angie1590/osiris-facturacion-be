from osiris.domain.service import BaseService
from .repository import RolRepository

class RolService(BaseService):
    repo = RolRepository()
    pass  # hooks disponibles si luego necesitas reglas

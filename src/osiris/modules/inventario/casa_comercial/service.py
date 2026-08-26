from osiris.domain.service import BaseService
from .repository import CasaComercialRepository

class CasaComercialService(BaseService):
    repo = CasaComercialRepository()
    pass  # hooks disponibles si luego necesitas reglas

from osiris.domain.service import BaseService
from .entity import CasaComercial
from .repository import CasaComercialRepository


class CasaComercialService(BaseService[CasaComercial]):
    repo = CasaComercialRepository()
    pass  # hooks disponibles si luego necesitas reglas

from osiris.domain.repository import BaseRepository
from .entity import CasaComercial

class CasaComercialRepository(BaseRepository):
    model = CasaComercial

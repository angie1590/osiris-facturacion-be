from osiris.domain.service import BaseService
from .repository import AtributoRepository

class AtributoService(BaseService):
    repo = AtributoRepository()

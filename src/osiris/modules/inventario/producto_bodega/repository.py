# src/osiris/modules/inventario/producto_bodega/repository.py
from osiris.domain.repository import BaseRepository
from osiris.modules.inventario.producto.entity import ProductoBodega


class ProductoBodegaRepository(BaseRepository):
    model = ProductoBodega

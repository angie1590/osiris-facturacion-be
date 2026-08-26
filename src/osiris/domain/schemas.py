from typing import Generic, List, TypeVar
from pydantic import BaseModel
from osiris.utils.pagination import PaginationMeta

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    meta: PaginationMeta
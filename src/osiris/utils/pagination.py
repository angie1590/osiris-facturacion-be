from math import ceil
from pydantic import BaseModel

class PaginationMeta(BaseModel):
    total: int
    limit: int
    offset: int
    next_offset: int | None
    prev_offset: int | None
    has_more: bool
    page: int
    page_count: int

def build_pagination_meta(total: int, limit: int, offset: int) -> PaginationMeta:
    page = (offset // limit) + 1 if limit else 1
    page_count = ceil(total / limit) if limit else 1

    next_off = offset + limit
    prev_off = offset - limit

    has_more = next_off < total
    next_offset = next_off if has_more else None
    prev_offset = prev_off if prev_off >= 0 else None

    return PaginationMeta(
        total=total,
        limit=limit,
        offset=offset,
        next_offset=next_offset,
        prev_offset=prev_offset,
        has_more=has_more,
        page=page,
        page_count=page_count,
    )

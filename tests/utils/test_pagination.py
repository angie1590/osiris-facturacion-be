from osiris.utils.pagination import build_pagination_meta

def test_build_pagination_meta_middle_page():
    meta = build_pagination_meta(total=25, limit=10, offset=10)
    assert meta.total == 25
    assert meta.limit == 10
    assert meta.offset == 10
    assert meta.page == 2
    assert meta.page_count == 3
    assert meta.has_more is True
    assert meta.prev_offset == 0
    assert meta.next_offset == 20

def test_build_pagination_meta_first_page():
    meta = build_pagination_meta(total=5, limit=10, offset=0)
    assert meta.page == 1
    assert meta.page_count == 1
    assert meta.has_more is False
    assert meta.prev_offset is None
    assert meta.next_offset is None

def test_build_pagination_meta_last_page():
    meta = build_pagination_meta(total=21, limit=10, offset=20)
    assert meta.page == 3
    assert meta.page_count == 3
    assert meta.has_more is False
    assert meta.prev_offset == 10
    assert meta.next_offset is None

from datetime import datetime, timezone
from types import SimpleNamespace

from osiris.core.auth import is_token_invalidated


def test_token_before_logout_is_invalidated():
    usuario = SimpleNamespace(sesion_invalidada_en=datetime(2026, 1, 1, 12, tzinfo=timezone.utc))
    assert is_token_invalidated({"iat": datetime(2026, 1, 1, 11, tzinfo=timezone.utc).timestamp()}, usuario)


def test_token_after_logout_remains_valid():
    usuario = SimpleNamespace(sesion_invalidada_en=datetime(2026, 1, 1, 12, tzinfo=timezone.utc))
    assert not is_token_invalidated({"iat": datetime(2026, 1, 1, 13, tzinfo=timezone.utc).timestamp()}, usuario)


def test_legacy_token_without_iat_is_not_invalidated():
    usuario = SimpleNamespace(sesion_invalidada_en=datetime(2026, 1, 1, 12, tzinfo=timezone.utc))
    assert not is_token_invalidated({}, usuario)

from __future__ import annotations

import base64
import json

import pytest
from fastapi import HTTPException

from osiris.utils.catalog_preview import CatalogPreviewSigner


def preview_context():
    return {
        "operation": "update_category_assignment",
        "target": "mapping-id",
        "actor": "authenticated-user",
        "payload": {"obligatorio": True, "valor_default": None},
        "state": {"definition": {"nombre": "RAM"}, "mappings": [], "values": []},
    }


def test_preview_token_matches_unchanged_context_without_exposing_payload():
    signer = CatalogPreviewSigner(b"test-only-catalog-preview-key-32bytes")
    context = preview_context()
    token = signer.issue(**context, now=1000)
    signer.verify(token, **context, now=1001)
    encoded, _signature = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    assert set(claims) == {"v", "iat", "exp", "binding", "state"}
    assert "RAM" not in json.dumps(claims)
    assert "authenticated-user" not in json.dumps(claims)


@pytest.mark.parametrize("changed_field", ["operation", "target", "actor", "payload", "state"])
def test_preview_rejects_different_binding_or_state(changed_field):
    signer = CatalogPreviewSigner(b"test-only-catalog-preview-key-32bytes")
    context = preview_context()
    token = signer.issue(**context, now=1000)
    context[changed_field] = (
        {"changed": True} if changed_field in {"payload", "state"} else "different"
    )
    with pytest.raises(HTTPException) as error:
        signer.verify(token, **context, now=1001)
    assert error.value.status_code == 409
    assert error.value.detail["code"] == "CATALOG_PREVIEW_STALE"


@pytest.mark.parametrize("current_time", [999, 1300, 1400])
def test_preview_rejects_future_or_expired_tokens(current_time):
    signer = CatalogPreviewSigner(b"test-only-catalog-preview-key-32bytes")
    context = preview_context()
    token = signer.issue(**context, now=1000)
    with pytest.raises(HTTPException):
        signer.verify(token, **context, now=current_time)


@pytest.mark.parametrize("token", ["", "invalid", "a.b.c", "invalid.signature", "x" * 2049])
def test_preview_rejects_malformed_tokens(token):
    signer = CatalogPreviewSigner(b"test-only-catalog-preview-key-32bytes")
    with pytest.raises(HTTPException) as error:
        signer.verify(token, **preview_context(), now=1001)
    assert error.value.detail["code"] == "CATALOG_PREVIEW_STALE"


def test_new_override_or_value_invalidates_preview():
    signer = CatalogPreviewSigner(b"test-only-catalog-preview-key-32bytes")
    context = preview_context()
    token = signer.issue(**context, now=1000)
    context["state"]["mappings"].append({"id": "new-child-override"})
    with pytest.raises(HTTPException):
        signer.verify(token, **context, now=1001)


def test_omitted_field_is_not_equivalent_to_explicit_null():
    signer = CatalogPreviewSigner(b"test-only-catalog-preview-key-32bytes")
    context = preview_context()
    token = signer.issue(**context, now=1000)
    del context["payload"]["valor_default"]
    with pytest.raises(HTTPException):
        signer.verify(token, **context, now=1001)


def test_different_key_order_preserves_binding():
    signer = CatalogPreviewSigner(b"test-only-catalog-preview-key-32bytes")
    context = preview_context()
    token = signer.issue(**context, now=1000)
    context["payload"] = {"valor_default": None, "obligatorio": True}
    signer.verify(token, **context, now=1001)


def test_wrong_signing_key_rejects_preview():
    context = preview_context()
    token = CatalogPreviewSigner(b"first-test-only-signing-key-32bytes").issue(**context, now=1000)
    with pytest.raises(HTTPException):
        CatalogPreviewSigner(b"second-test-only-signing-key-32bytes").verify(
            token, **context, now=1001
        )


def test_signer_rejects_weak_key_or_unbounded_expiration():
    with pytest.raises(ValueError):
        CatalogPreviewSigner(b"weak")
    with pytest.raises(ValueError):
        CatalogPreviewSigner(b"test-only-catalog-preview-key-32bytes", ttl_seconds=0)


def test_real_signer_error_matches_published_catalog_contract():
    from osiris.domain.catalog_contracts import CatalogError

    signer = CatalogPreviewSigner(b"test-only-catalog-preview-key-32bytes")
    with pytest.raises(HTTPException) as error:
        signer.verify("invalid", **preview_context(), now=1001)
    response = CatalogError.model_validate({"detail": error.value.detail})
    assert response.detail.code == "CATALOG_PREVIEW_STALE"
    assert response.detail.conteos == {}
    assert response.detail.acciones_permitidas == ["previsualizar"]

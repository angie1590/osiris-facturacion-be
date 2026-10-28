from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4
from typing import Any

from fastapi import FastAPI

from osiris.core.product_permissions import (
    create_product_permission,
    delete_product_permission,
    read_product_permission,
    update_product_permission,
)

PRODUCT_PERMISSION_DEPENDENCIES = (
    read_product_permission,
    create_product_permission,
    update_product_permission,
    delete_product_permission,
)


def override_product_permissions(app: FastAPI, role_id: Any) -> None:
    actor = SimpleNamespace(id=uuid4(), rol_id=role_id)
    for dependency in PRODUCT_PERMISSION_DEPENDENCIES:
        app.dependency_overrides[dependency] = lambda actor=actor: actor


def clear_product_permission_overrides(app: FastAPI) -> None:
    for dependency in PRODUCT_PERMISSION_DEPENDENCIES:
        app.dependency_overrides.pop(dependency, None)

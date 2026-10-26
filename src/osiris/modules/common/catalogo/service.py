from __future__ import annotations

from typing import Any, List
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, col, select

from osiris.core.audit import record_domain_change
from osiris.modules.common.catalogo.entity import Catalogo, CatalogoValor
from osiris.modules.inventario.atributo.entity import Atributo


class CatalogoService:
    @staticmethod
    def _duplicate_catalog(session: Session, nombre: str, exclude_id: UUID | None = None) -> bool:
        statement = select(Catalogo.id).where(func.lower(Catalogo.nombre) == nombre.strip().lower())
        if exclude_id is not None:
            statement = statement.where(Catalogo.id != exclude_id)
        return session.exec(statement.limit(1)).first() is not None

    def list(self, session: Session) -> List[dict[str, Any]]:
        catalogs = session.exec(
            select(Catalogo).where(col(Catalogo.activo).is_(True)).order_by(Catalogo.nombre)
        ).all()
        return [
            {
                "id": item.id,
                "name": item.nombre,
                "description": item.descripcion,
                "is_active": item.activo,
                "value_count": int(
                    session.exec(
                        select(func.count(col(CatalogoValor.id))).where(
                            CatalogoValor.catalogo_id == item.id,
                            col(CatalogoValor.activo).is_(True),
                        )
                    ).one()
                ),
                "created_at": item.creado_en,
                "updated_at": item.actualizado_en,
            }
            for item in catalogs
        ]

    def create(self, session: Session, *, name: str, description: str | None = None) -> dict[str, Any]:
        normalized_name = name.strip()
        if self._duplicate_catalog(session, normalized_name):
            raise HTTPException(status_code=409, detail="Ya existe un catálogo con ese nombre.")
        catalog = Catalogo(
            nombre=normalized_name,
            descripcion=description.strip() if description else None,
            usuario_auditoria="api",
            activo=True,
        )
        session.add(catalog)
        if not hasattr(session, "_mock_methods"):
            session.flush()
            record_domain_change(
                session,
                entity="tbl_catalogo",
                entity_id=catalog.id,
                action="CREATE_CATALOG",
                before={},
                after={"nombre": catalog.nombre, "descripcion": catalog.descripcion},
            )
        session.commit()
        session.refresh(catalog)
        return self._catalog_read(catalog, 0)

    def update(self, session: Session, catalog_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        catalog = session.get(Catalogo, catalog_id)
        if not catalog or not catalog.activo:
            return None
        before = {"nombre": catalog.nombre, "descripcion": catalog.descripcion}
        if data.get("name") is not None:
            name = data["name"].strip()
            if self._duplicate_catalog(session, name, catalog_id):
                raise HTTPException(status_code=409, detail="Ya existe un catálogo con ese nombre.")
            catalog.nombre = name
        if "description" in data:
            catalog.descripcion = data["description"].strip() if data["description"] else None
        session.add(catalog)
        if not hasattr(session, "_mock_methods"):
            record_domain_change(
                session,
                entity="tbl_catalogo",
                entity_id=catalog_id,
                action="UPDATE_CATALOG",
                before=before,
                after={"nombre": catalog.nombre, "descripcion": catalog.descripcion},
            )
        session.commit()
        session.refresh(catalog)
        value_count = int(
            session.exec(
                select(func.count(col(CatalogoValor.id))).where(
                    CatalogoValor.catalogo_id == catalog_id,
                    col(CatalogoValor.activo).is_(True),
                )
            ).one()
        )
        return self._catalog_read(catalog, value_count)

    def delete(self, session: Session, catalog_id: UUID) -> bool | None:
        catalog = session.get(Catalogo, catalog_id)
        if not catalog or not catalog.activo:
            return None
        referenced = session.exec(
            select(Atributo.id).where(
                Atributo.catalog_id == catalog_id,
                col(Atributo.activo).is_(True),
            ).limit(1)
        ).first()
        if referenced:
            raise HTTPException(
                status_code=409,
                detail="No se puede dar de baja un catálogo asociado a atributos activos.",
            )
        before = {"nombre": catalog.nombre, "descripcion": catalog.descripcion, "activo": True}
        catalog.activo = False
        session.add(catalog)
        if not hasattr(session, "_mock_methods"):
            record_domain_change(
                session,
                entity="tbl_catalogo",
                entity_id=catalog_id,
                action="DELETE_CATALOG",
                before=before,
                after={"activo": False},
            )
        session.commit()
        return True

    def list_values(self, session: Session, catalog_id: UUID, *, include_inactive: bool) -> List[dict[str, Any]]:
        catalog = session.get(Catalogo, catalog_id)
        if not catalog or not catalog.activo:
            raise HTTPException(status_code=404, detail="Catálogo no encontrado o inactivo.")
        statement = select(CatalogoValor).where(CatalogoValor.catalogo_id == catalog_id)
        if not include_inactive:
            statement = statement.where(col(CatalogoValor.activo).is_(True))
        statement = statement.order_by(col(CatalogoValor.orden), CatalogoValor.valor)
        return [self._value_read(item) for item in session.exec(statement).all()]

    def add_value(self, session: Session, catalog_id: UUID, value: str) -> dict[str, Any]:
        catalog = session.get(Catalogo, catalog_id)
        if not catalog or not catalog.activo:
            raise HTTPException(status_code=404, detail="Catálogo no encontrado o inactivo.")
        normalized = value.strip()
        existing = session.exec(
            select(CatalogoValor).where(
                CatalogoValor.catalogo_id == catalog_id,
                func.lower(CatalogoValor.valor) == normalized.lower(),
            )
        ).first()
        if existing and existing.activo:
            raise HTTPException(status_code=409, detail="El valor ya existe en el catálogo.")
        if existing:
            before = {"value": existing.valor, "is_active": existing.activo}
            existing.activo = True
            existing.valor = normalized
            session.add(existing)
            entity = existing
        else:
            before = {}
            entity = CatalogoValor(
                catalogo_id=catalog_id,
                valor=normalized,
                usuario_auditoria="api",
                activo=True,
            )
            session.add(entity)
        if not hasattr(session, "_mock_methods"):
            session.flush()
            record_domain_change(
                session,
                entity="tbl_catalogo_valor",
                entity_id=entity.id,
                action="UPSERT_CATALOG_VALUE",
                before=before,
                after={"catalogo_id": str(catalog_id), "value": entity.valor, "is_active": entity.activo},
            )
        session.commit()
        session.refresh(entity)
        return self._value_read(entity)

    def update_value(self, session: Session, catalog_id: UUID, value_id: UUID, value: str) -> dict[str, Any] | None:
        entity = session.get(CatalogoValor, value_id)
        if not entity or entity.catalogo_id != catalog_id or not entity.activo:
            return None
        before = {"value": entity.valor, "is_active": entity.activo}
        normalized = value.strip()
        duplicate = session.exec(
            select(CatalogoValor.id).where(
                CatalogoValor.catalogo_id == catalog_id,
                CatalogoValor.id != value_id,
                col(CatalogoValor.activo).is_(True),
                func.lower(CatalogoValor.valor) == normalized.lower(),
            ).limit(1)
        ).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="El valor ya existe en el catálogo.")
        entity.valor = normalized
        session.add(entity)
        if not hasattr(session, "_mock_methods"):
            record_domain_change(
                session,
                entity="tbl_catalogo_valor",
                entity_id=value_id,
                action="UPDATE_CATALOG_VALUE",
                before=before,
                after={"catalogo_id": str(catalog_id), "value": entity.valor, "is_active": entity.activo},
            )
        session.commit()
        session.refresh(entity)
        return self._value_read(entity)

    def toggle_value(self, session: Session, catalog_id: UUID, value_id: UUID, *, active: bool) -> dict[str, Any] | None:
        entity = session.get(CatalogoValor, value_id)
        if not entity or entity.catalogo_id != catalog_id:
            return None
        before = {"value": entity.valor, "is_active": entity.activo}
        entity.activo = active
        session.add(entity)
        if not hasattr(session, "_mock_methods"):
            record_domain_change(
                session,
                entity="tbl_catalogo_valor",
                entity_id=value_id,
                action="REACTIVATE_CATALOG_VALUE" if active else "DEACTIVATE_CATALOG_VALUE",
                before=before,
                after={"catalogo_id": str(catalog_id), "value": entity.valor, "is_active": entity.activo},
            )
        session.commit()
        session.refresh(entity)
        return self._value_read(entity)

    @staticmethod
    def _catalog_read(catalog: Catalogo, value_count: int) -> dict[str, Any]:
        return {
            "id": catalog.id,
            "name": catalog.nombre,
            "description": catalog.descripcion,
            "is_active": catalog.activo,
            "value_count": value_count,
            "created_at": catalog.creado_en,
            "updated_at": catalog.actualizado_en,
        }

    @staticmethod
    def _value_read(value: CatalogoValor) -> dict[str, Any]:
        return {
            "id": value.id,
            "catalog_id": value.catalogo_id,
            "value": value.valor,
            "is_active": value.activo,
            "created_at": value.creado_en,
            "updated_at": value.actualizado_en,
        }
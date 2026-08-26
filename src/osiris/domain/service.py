# src/domain/service.py
from typing import Any, Dict, Generic, Type, TypeVar, Union, Tuple
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select, SQLModel
from fastapi import HTTPException
from osiris.utils.pagination import build_pagination_meta

ModelT = TypeVar("ModelT")
# Tipos aceptados para declarar FKs en cada service:
# - Modelo  -> asume columna 'id', require_activo=True si existe
# - (Modelo, "columna") -> require_activo=True
# - (Modelo, "columna", False) -> NO exigir activo
# - {"model": Modelo, "field": "columna", "require_active": bool}
FkSpec = Union[
    Type[SQLModel],
    Tuple[Type[SQLModel], str],
    Tuple[Type[SQLModel], str, bool],
    Dict[str, Any],
]
class BaseService(Generic[ModelT]):
    repo = None  # cada subclase la setea

    fk_models: Dict[str, FkSpec] = {}

    @staticmethod
    def _ensure_dict(data: Any) -> Dict[str, Any]:
        """Acepta dict o DTO/SQLModel y devuelve dict con campos enviados."""
        if hasattr(data, "model_dump"):  # Pydantic/SQLModel v2
            return data.model_dump(exclude_unset=True)  # type: ignore[attr-defined]
        if isinstance(data, dict):
            return data
        # Último recurso: __dict__ sin privados
        return {k: v for k, v in vars(data).items() if not k.startswith("_")}

    @staticmethod
    def _parse_fk_spec(spec: FkSpec) -> Tuple[Type[SQLModel], str, bool]:
        """Normaliza la especificación de FK a (modelo, columna, require_active)."""
        # Modelo -> usa 'id'
        if isinstance(spec, type) and issubclass(spec, SQLModel):
            return spec, "id", True

        # Tupla (Modelo, "columna") o (Modelo, "columna", require_active)
        if isinstance(spec, tuple):
            if len(spec) == 2:
                model, field = spec
                return model, field, True
            if len(spec) == 3:
                model, field, require_active = spec
                return model, field, bool(require_active)

        # Dict {"model": M, "field": "col", "require_active": bool}
        if isinstance(spec, dict):
            model = spec["model"]
            field = spec.get("field", "id")
            require_active = spec.get("require_active", True)
            return model, field, bool(require_active)

        raise ValueError("fk_models contiene una especificación de FK inválida")



    def _check_fk_active_and_exists(self, session: Session, data: Dict[str, Any]) -> None:
        """
        Para cada entrada en fk_models:
          - verifica existencia (modelo.campo == valor)
          - si require_active=True y el modelo tiene 'activo', exige True
        Solo valida campos presentes en 'data'.
        """
        for field_name, spec in self.fk_models.items():
            if field_name not in data or data[field_name] is None:
                continue

            model, field, require_active = self._parse_fk_spec(spec)
            # Asegura que el modelo tiene la columna declarada
            if not hasattr(model, field):
                raise HTTPException(
                    status_code=500,
                    detail=f"Configuración inválida: {model.__name__}.{field} no existe"
                )

            stmt = select(model).where(getattr(model, field) == data[field_name])
            obj = session.exec(stmt).first()
            if not obj:
                raise HTTPException(status_code=404, detail=f"{model.__name__} no encontrado")

            if require_active and hasattr(obj, "activo") and getattr(obj, "activo") is False:
                raise HTTPException(status_code=409, detail=f"{model.__name__} inactivo")

    def list(self, session: Session, *, only_active=True, limit=50, offset=0, **kw):
        return self.repo.list(session, only_active=only_active, limit=limit, offset=offset, **kw)

    def list_paginated(self, session: Session, *, only_active=True, limit=50, offset=0, **kw):
        items, total = self.repo.list(session, only_active=only_active, limit=limit, offset=offset, **kw)
        meta = build_pagination_meta(total=total, limit=limit, offset=offset)
        return items, meta

    def _handle_transaction_error(self, session: Session, exc: Exception) -> None:
        session.rollback()
        if isinstance(exc, IntegrityError) and hasattr(self.repo, "_raise_integrity"):
            self.repo._raise_integrity(exc)
        raise exc

    # Hooks de dominio
    def validate_create(self, data: Dict[str, Any], session: Session) -> None: ...
    def validate_update(self, data: Dict[str, Any], session: Session) -> None: ...
    def on_created(self, obj: ModelT, session: Session) -> None: ...
    def on_updated(self, obj: ModelT, session: Session) -> None: ...
    def on_deleted(self, obj: ModelT, session: Session) -> None: ...

    # Operaciones
    def create(self, session: Session, data: Dict[str, Any], *, commit: bool = True) -> ModelT:
        try:
            self.validate_create(data, session)
            self._check_fk_active_and_exists(session, data)
            obj = self.repo.create(session, data)
            self.on_created(obj, session)
            if commit:
                session.commit()
                session.refresh(obj)
            return obj
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    def get(self, session: Session, item_id: Any):
        return self.repo.get(session, item_id)

    def update(self, session: Session, item_id: Any, data: Any, *, commit: bool = True):
        try:
            db_obj = self.repo.get(session, item_id)
            if not db_obj:
                return None
            self._check_fk_active_and_exists(session, data)
            updated = self.repo.update(session, db_obj, data)
            self.on_updated(updated, session)
            if commit:
                session.commit()
                session.refresh(updated)
            return updated
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    def delete(self, session: Session, item_id: Any, *, commit: bool = True) -> bool | None:
        try:
            db_obj = self.repo.get(session, item_id)
            if not db_obj:
                return None
            deleted = self.repo.delete(session, db_obj)
            self.on_deleted(db_obj, session)
            if commit:
                session.commit()
            return deleted
        except Exception as exc:
            self._handle_transaction_error(session, exc)

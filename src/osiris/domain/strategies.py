# src/domain/strategies.py
from typing import Protocol, Any, Dict
from sqlmodel import Session

class CreateStrategy(Protocol):
    def before_create(self, data: Dict[str, Any], session: Session) -> Dict[str, Any]: ...
    def after_create(self, obj: Any, session: Session) -> Any: ...

class UpdateStrategy(Protocol):
    def before_update(self, data: Dict[str, Any], session: Session) -> Dict[str, Any]: ...
    def after_update(self, obj: Any, session: Session) -> Any: ...

class DeleteStrategy(Protocol):
    def before_delete(self, obj: Any, session: Session) -> None: ...
    def after_delete(self, obj: Any, session: Session) -> None: ...

class DefaultCreate:
    def before_create(self, data, session): return data
    def after_create(self, obj, session): return obj

class DefaultUpdate:
    def before_update(self, data, session): return data
    def after_update(self, obj, session): return obj

class DefaultDelete:
    def before_delete(self, obj, session): ...
    def after_delete(self, obj, session): ...

from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlmodel import Session


PayloadT = TypeVar("PayloadT")
ResultT = TypeVar("ResultT")


class TemplateMethodService(Generic[PayloadT, ResultT]):
    """
    Implementación base de Template Method para orquestar create/update
    sin alterar la lógica de negocio de cada dominio.
    """

    def execute_create(self, session: Session, payload: PayloadT, **kwargs: Any) -> ResultT:
        context = self._pre_create_hook(session, payload, **kwargs)
        result = self._execute_create(session, payload, context=context, **kwargs)
        return self._post_create_hook(session, payload, result, context=context, **kwargs)

    def execute_update(self, session: Session, payload: PayloadT, **kwargs: Any) -> ResultT:
        context = self._pre_update_hook(session, payload, **kwargs)
        result = self._execute_update(session, payload, context=context, **kwargs)
        return self._post_update_hook(session, payload, result, context=context, **kwargs)

    def _pre_create_hook(self, session: Session, payload: PayloadT, **kwargs: Any) -> dict[str, Any]:
        _ = (session, payload, kwargs)
        return {}

    def _execute_create(
        self,
        session: Session,
        payload: PayloadT,
        *,
        context: dict[str, Any],
        **kwargs: Any,
    ) -> ResultT:
        _ = (session, payload, context, kwargs)
        raise NotImplementedError

    def _post_create_hook(
        self,
        session: Session,
        payload: PayloadT,
        result: ResultT,
        *,
        context: dict[str, Any],
        **kwargs: Any,
    ) -> ResultT:
        _ = (session, payload, context, kwargs)
        return result

    def _pre_update_hook(self, session: Session, payload: PayloadT, **kwargs: Any) -> dict[str, Any]:
        _ = (session, payload, kwargs)
        return {}

    def _execute_update(
        self,
        session: Session,
        payload: PayloadT,
        *,
        context: dict[str, Any],
        **kwargs: Any,
    ) -> ResultT:
        _ = (session, payload, context, kwargs)
        raise NotImplementedError

    def _post_update_hook(
        self,
        session: Session,
        payload: PayloadT,
        result: ResultT,
        *,
        context: dict[str, Any],
        **kwargs: Any,
    ) -> ResultT:
        _ = (session, payload, context, kwargs)
        return result

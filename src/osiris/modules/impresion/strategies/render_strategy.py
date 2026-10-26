from __future__ import annotations

from abc import ABC, abstractmethod


def checked_pdf_output(value: object) -> bytes:
    if not isinstance(value, bytes):
        raise TypeError("El renderizador PDF debe devolver bytes.")
    return value


def checked_html_output(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("El renderizador HTML debe devolver texto.")
    return value


class RenderStrategy(ABC):
    @abstractmethod
    def render_pdf(self, html_content: str) -> bytes:
        raise NotImplementedError

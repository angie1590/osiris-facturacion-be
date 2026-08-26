from __future__ import annotations

from abc import ABC, abstractmethod


class RenderStrategy(ABC):
    @abstractmethod
    def render_pdf(self, html_content: str) -> bytes:
        raise NotImplementedError


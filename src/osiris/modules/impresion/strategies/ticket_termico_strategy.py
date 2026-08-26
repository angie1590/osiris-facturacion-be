from __future__ import annotations

from pathlib import Path

from osiris.modules.impresion.strategies.render_strategy import RenderStrategy
from osiris.modules.impresion.strategies.ride_a4_strategy import _build_minimal_pdf


class TicketTermicoStrategy(RenderStrategy):
    def __init__(self, templates_dir: Path) -> None:
        self.templates_dir = templates_dir

    @staticmethod
    def _template_name(ancho: str) -> str:
        return "ticket_termico_58mm.html" if ancho == "58mm" else "ticket_termico_80mm.html"

    def render_ticket_html(self, context: dict, *, ancho: str = "80mm") -> str:
        template_name = self._template_name(ancho)
        template_path = self.templates_dir / template_name
        if not template_path.exists():
            raise FileNotFoundError(f"No existe la plantilla térmica: {template_name}")

        try:
            from jinja2 import Environment, FileSystemLoader, select_autoescape  # type: ignore

            env = Environment(
                loader=FileSystemLoader(str(self.templates_dir)),
                autoescape=select_autoescape(["html", "xml"]),
            )
            template = env.get_template(template_name)
            return template.render(**context)
        except ModuleNotFoundError:
            # Fallback simple para entornos sin Jinja2.
            html = template_path.read_text(encoding="utf-8")
            for key, value in context.items():
                html = html.replace(f"{{{{ {key} }}}}", str(value))
            return html

    def render_pdf(self, html_content: str) -> bytes:
        try:
            from weasyprint import HTML  # type: ignore

            return HTML(string=html_content).write_pdf()
        except ModuleNotFoundError:
            plain = " ".join(html_content.split())
            lines = [plain[i : i + 90] for i in range(0, max(len(plain), 1), 90)] or ["TICKET TERMICO"]
            return _build_minimal_pdf(lines)


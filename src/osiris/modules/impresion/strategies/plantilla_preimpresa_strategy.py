from __future__ import annotations

from pathlib import Path

from osiris.modules.impresion.strategies.render_strategy import RenderStrategy
from osiris.modules.impresion.strategies.ride_a4_strategy import _build_minimal_pdf


class PlantillaPreimpresaStrategy(RenderStrategy):
    def __init__(self, templates_dir: Path) -> None:
        self.templates_dir = templates_dir

    def render_html(self, context: dict) -> str:
        template_name = "nota_venta_preimpresa.html"
        template_path = self.templates_dir / template_name
        if not template_path.exists():
            raise FileNotFoundError(f"No existe la plantilla preimpresa: {template_name}")

        try:
            from jinja2 import Environment, FileSystemLoader, select_autoescape  # type: ignore

            env = Environment(
                loader=FileSystemLoader(str(self.templates_dir)),
                autoescape=select_autoescape(["html", "xml"]),
            )
            template = env.get_template(template_name)
            return template.render(**context)
        except ModuleNotFoundError:
            # Fallback para entornos sin Jinja2.
            return self._render_html_fallback(context)

    @staticmethod
    def _render_html_fallback(context: dict) -> str:
        paginas = context.get("paginas") or []
        margen_superior_cm = context.get("margen_superior_cm", "5")
        total = context.get("total", "0.00")

        pages_html: list[str] = []
        for idx, pagina in enumerate(paginas):
            rows = []
            for item in pagina:
                rows.append(
                    (
                        "<tr>"
                        f"<td>{item.get('cantidad', '')}</td>"
                        f"<td>{item.get('descripcion', '')}</td>"
                        f"<td>{item.get('valor_unitario', '')}</td>"
                        f"<td>{item.get('valor_total', '')}</td>"
                        "</tr>"
                    )
                )

            totales_html = ""
            if idx == len(paginas) - 1:
                totales_html = (
                    '<div class="totales"><div class="row"><span>Total</span>'
                    f"<span>{total}</span></div></div>"
                )

            pages_html.append(
                (
                    '<section class="page"><table><thead><tr>'
                    "<th>Cantidad</th><th>Descripción</th><th>V. Unitario</th><th>V. Total</th>"
                    "</tr></thead><tbody>"
                    + "".join(rows)
                    + "</tbody></table>"
                    + totales_html
                    + "</section>"
                )
            )

        return (
            "<!doctype html><html lang='es'><head><meta charset='utf-8' />"
            "<meta name='ticket-template' content='PREIMPRESA_NOTA_VENTA' />"
            "<style>@page{size:A4;margin:0;}body{margin:0;"
            f"padding-top: {margen_superior_cm}cm;"
            "padding-left:1cm;padding-right:1cm;font-family:'Courier New',Courier,monospace;font-size:11px;}"
            ".page{min-height:29.7cm;position:relative;page-break-after:always;}"
            ".page:last-child{page-break-after:auto;}table{width:100%;border-collapse:collapse;}"
            "th,td{border-bottom:1px dotted #666;padding:2px 4px;}"
            "th:nth-child(1),td:nth-child(1){width:10%;text-align:right;}"
            "th:nth-child(2),td:nth-child(2){width:54%;}"
            "th:nth-child(3),td:nth-child(3),th:nth-child(4),td:nth-child(4){width:18%;text-align:right;}"
            ".totales{position:absolute;right:0;bottom:2.2cm;width:38%;}"
            ".totales .row{display:flex;justify-content:space-between;font-weight:bold;}"
            "</style></head><body>"
            + "".join(pages_html)
            + "</body></html>"
        )

    def render_pdf(self, html_content: str) -> bytes:
        try:
            from weasyprint import HTML  # type: ignore

            return HTML(string=html_content).write_pdf()
        except ModuleNotFoundError:
            plain = " ".join(html_content.split())
            lines = [plain[i : i + 90] for i in range(0, max(len(plain), 1), 90)] or ["NOTA VENTA PREIMPRESA"]
            return _build_minimal_pdf(lines)

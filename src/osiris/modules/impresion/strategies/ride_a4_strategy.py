from __future__ import annotations

import re
from html import unescape

from osiris.modules.impresion.strategies.render_strategy import RenderStrategy


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_minimal_pdf(lines: list[str]) -> bytes:
    line_ops: list[str] = ["BT", "/F1 9 Tf", "40 810 Td"]
    first = True
    for line in lines:
        safe_line = _pdf_escape(line[:110])
        if first:
            line_ops.append(f"({safe_line}) Tj")
            first = False
        else:
            line_ops.append("0 -14 Td")
            line_ops.append(f"({safe_line}) Tj")
    line_ops.append("ET")
    content_stream = ("\n".join(line_ops)).encode("latin-1", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        f"<< /Length {len(content_stream)} >>\nstream\n".encode() + content_stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{idx} 0 obj\n".encode())
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode())

    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_start}\n%%EOF\n"
    )
    pdf.extend(trailer.encode())
    return bytes(pdf)


class RideA4Strategy(RenderStrategy):
    def render_pdf(self, html_content: str) -> bytes:
        try:
            from weasyprint import HTML  # type: ignore

            return HTML(string=html_content).write_pdf()
        except ModuleNotFoundError:
            # Fallback local para entornos sin dependencia gráfica.
            plain = unescape(re.sub(r"<[^>]+>", " ", html_content))
            plain = re.sub(r"\s+", " ", plain).strip()
            chunks = [plain[i : i + 110] for i in range(0, max(len(plain), 1), 110)] or ["RIDE A4"]
            return _build_minimal_pdf(chunks)


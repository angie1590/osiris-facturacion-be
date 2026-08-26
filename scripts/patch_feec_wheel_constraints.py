#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import re
import tempfile
import zipfile
from pathlib import Path


OLD_REQ = "Requires-Dist: cryptography (<=40.0.2)"
NEW_REQ = "Requires-Dist: cryptography (>=46.0.5,<47.0.0)"


def _sha256_urlsafe(data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    return "sha256=" + base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _write_record(dist_info_dir: Path) -> None:
    record_path = dist_info_dir / "RECORD"
    rows: list[list[str]] = []

    for file_path in sorted(p for p in dist_info_dir.parent.rglob("*") if p.is_file()):
        rel = file_path.relative_to(dist_info_dir.parent).as_posix()
        if rel.endswith(".dist-info/RECORD"):
            rows.append([rel, "", ""])
            continue
        data = file_path.read_bytes()
        rows.append([rel, _sha256_urlsafe(data), str(len(data))])

    with record_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerows(rows)


def _normalize_cryptography_requirement(metadata_text: str) -> tuple[str, bool]:
    lines = metadata_text.splitlines()
    replaced = False
    normalized_lines: list[str] = []

    for line in lines:
        if re.match(r"^Requires-Dist:\s*cryptography\b", line) and "<=40.0.2" in line.replace(
            " ", ""
        ):
            normalized_lines.append(NEW_REQ)
            replaced = True
            continue
        normalized_lines.append(line)

    normalized = "\n".join(normalized_lines)
    if metadata_text.endswith("\n"):
        normalized += "\n"
    return normalized, replaced


def patch_wheel(wheel_path: Path) -> tuple[bool, str]:
    if not wheel_path.exists():
        return False, f"Wheel no encontrado: {wheel_path}"

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        with zipfile.ZipFile(wheel_path, "r") as zf:
            zf.extractall(tmp_path)

        metadata_files = list(tmp_path.rglob("*.dist-info/METADATA"))
        if len(metadata_files) != 1:
            return False, "No se pudo ubicar METADATA del wheel fe-ec."

        metadata_file = metadata_files[0]
        text = metadata_file.read_text(encoding="utf-8")

        if NEW_REQ in text and "<=40.0.2" not in text:
            return True, "Wheel ya estaba normalizado (sin cambios)."
        normalized_text, replaced = _normalize_cryptography_requirement(text)
        if not replaced:
            if OLD_REQ in text:
                normalized_text = text.replace(OLD_REQ, NEW_REQ)
                replaced = True
            else:
                return False, (
                    "No se encontró la restricción esperada de cryptography en METADATA. "
                    "Revisa versión del wheel fe-ec."
                )

        metadata_file.write_text(normalized_text, encoding="utf-8")

        dist_info = metadata_file.parent
        _write_record(dist_info)

        rebuilt_wheel = tmp_path / wheel_path.name
        with zipfile.ZipFile(rebuilt_wheel, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in sorted(p for p in tmp_path.rglob("*") if p.is_file()):
                if file_path == rebuilt_wheel:
                    continue
                zf.write(file_path, file_path.relative_to(tmp_path).as_posix())

        wheel_path.write_bytes(rebuilt_wheel.read_bytes())
        return True, "Wheel fe-ec normalizado correctamente."


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normaliza constraints de cryptography en wheel local fe-ec."
    )
    parser.add_argument(
        "--wheel",
        default="lib/fe_ec-0.1.0-py3-none-any-3.whl",
        help="Ruta al wheel fe-ec",
    )
    args = parser.parse_args()

    ok, message = patch_wheel(Path(args.wheel))
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

import re
import unicodedata


def generate_attribute_code(name: str) -> str:
    normalized = (
        unicodedata.normalize("NFKD", name)
        .encode("ascii", "ignore")
        .decode()
        .lower()
    )
    code = re.sub("[^a-z0-9]+", "_", normalized).strip("_")
    if not code:
        code = "atributo"
    if code[0].isdigit():
        code = f"atributo_{code}"
    if len(code) > 120:
        raise ValueError("El codigo generado del atributo no puede superar 120 caracteres.")
    return code
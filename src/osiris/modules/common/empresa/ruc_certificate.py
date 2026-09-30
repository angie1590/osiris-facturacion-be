from __future__ import annotations

import re
from io import BytesIO

from fastapi import HTTPException
from pydantic import BaseModel, Field
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from osiris.modules.common.empresa.entity import (
    RegimenTributario,
    TipoContribuyenteJuridico,
)
from osiris.utils.validacion_identificacion import ValidacionCedulaRucService


MAX_CERTIFICATE_BYTES = 5 * 1024 * 1024
MAX_CERTIFICATE_PAGES = 5


class SriRucAdditionalData(BaseModel):
    estado: str | None = None
    artesano: str | None = None
    provincia: str | None = None
    canton: str | None = None
    parroquia: str | None = None
    jurisdiccion: str | None = None
    actividades_economicas: list[str] = Field(default_factory=list)
    obligaciones_tributarias: list[str] = Field(default_factory=list)
    codigo_verificacion: str | None = None


class SriRucCertificatePreview(BaseModel):
    ruc: str
    razon_social: str
    tipo_contribuyente_juridico: TipoContribuyenteJuridico
    regimen: RegimenTributario
    obligado_contabilidad: bool
    agente_retencion: bool
    contribuyente_especial: bool
    direccion_matriz: str
    email: str | None = None
    telefono: str | None = None
    artesano_calificado: bool = False
    additional: SriRucAdditionalData
    warnings: list[str] = Field(default_factory=list)


class SriRucCertificateService:
    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value.replace("\x00", " ")).strip()

    @staticmethod
    def _boolean_after(text: str, label: str, *, until: str | None = None) -> bool:
        end = f"(?={until})" if until else ""
        match = re.search(
            rf"{label}\s+(.*?\b(?:S[IÍ]|NO)\b).*?{end}",
            text,
            re.IGNORECASE,
        )
        if not match:
            return False
        values = re.findall(r"\b(S[IÍ]|NO)\b", match.group(1), re.IGNORECASE)
        return bool(values and values[-1].upper() in {"SI", "SÍ"})

    @staticmethod
    def _name(lines: list[str], ruc: str) -> str | None:
        label_index = next(
            (index for index, line in enumerate(lines) if "APELLIDOS Y NOMBRES" in line.upper()),
            None,
        )
        candidates: list[str] = []
        if label_index is not None:
            candidates.extend(lines[label_index + 1 : label_index + 4])
            candidates.extend(reversed(lines[max(0, label_index - 3) : label_index]))

        ruc_index = next((index for index, line in enumerate(lines) if ruc in line), None)
        if ruc_index is not None:
            candidates.extend(lines[max(0, ruc_index - 4) : ruc_index + 2])

        excluded_tokens = (
            "CERTIFICADO",
            "REGISTRO ÚNICO",
            "CONTRIBUYENTES",
            "APELLIDOS Y NOMBRES",
            "NÚMERO RUC",
            "ESTADO",
            "RÉGIMEN",
        )
        for candidate in candidates:
            normalized = candidate.strip().upper()
            if any(token in normalized for token in excluded_tokens) or ruc in normalized:
                continue
            if re.fullmatch(r"[A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ\s.'-]{5,}", normalized) and len(
                normalized.split()
            ) >= 2:
                return normalized
        return None

    @staticmethod
    def _extract_list(text: str, start: str, end: str) -> list[str]:
        match = re.search(rf"{start}\s+(.*?)(?={end})", text, re.IGNORECASE)
        if not match:
            return []
        section = match.group(1)
        entries = re.findall(
            r"(?:[•\-]\s*)?([A-Z]\d{8}|\d{4})\s*[-–]?\s*(.*?)(?=(?:[•\-]\s*)?(?:[A-Z]\d{8}|\d{4})\b|$)",
            section,
            re.IGNORECASE,
        )
        return [f"{code.upper()} - {description.strip(' .')}" for code, description in entries]

    @classmethod
    def parse_text(cls, raw_text: str) -> SriRucCertificatePreview:
        text = cls._normalize(raw_text)
        lines = [cls._normalize(line) for line in raw_text.splitlines() if cls._normalize(line)]
        ruc_match = re.search(r"\b\d{13}\b", text)
        if not ruc_match:
            raise ValueError("No se encontró un número RUC de 13 dígitos en el certificado.")
        ruc = ruc_match.group(0)
        if not ValidacionCedulaRucService.es_identificacion_valida(ruc):
            raise ValueError("El certificado contiene un RUC ecuatoriano inválido.")

        razon_social = cls._name(lines, ruc)
        if not razon_social:
            raise ValueError("No se pudieron identificar los apellidos y nombres o razón social.")

        regimen_match = re.search(
            r"R[ÉE]GIMEN\s+(GENERAL|RIMPE\s*-?\s*EMPRENDEDOR|RIMPE\s*-?\s*NEGOCIO\s+POPULAR)",
            text,
            re.IGNORECASE,
        )
        regimen_text = cls._normalize(regimen_match.group(1)).upper() if regimen_match else "GENERAL"
        regimen = {
            "GENERAL": RegimenTributario.GENERAL,
            "RIMPE EMPRENDEDOR": RegimenTributario.RIMPE_EMPRENDEDOR,
            "RIMPE - EMPRENDEDOR": RegimenTributario.RIMPE_EMPRENDEDOR,
            "RIMPE NEGOCIO POPULAR": RegimenTributario.RIMPE_NEGOCIO_POPULAR,
            "RIMPE - NEGOCIO POPULAR": RegimenTributario.RIMPE_NEGOCIO_POPULAR,
        }.get(regimen_text, RegimenTributario.GENERAL)

        type_match = re.search(
            r"TIPO\s+(?:AGENTE DE RETENCI[ÓO]N\s+)?(PERSONAS? NATURALES?|SOCIEDADES?)",
            text,
            re.IGNORECASE,
        )
        tipo = (
            TipoContribuyenteJuridico.SOCIEDAD
            if type_match and "SOCIEDAD" in type_match.group(1).upper()
            else TipoContribuyenteJuridico.PERSONA_NATURAL
        )

        geo_match = re.search(
            r"PROVINCIA:\s*(.*?)\s+CANT[ÓO]N:\s*(.*?)\s+PARROQUIA:\s*(.*?)(?=\s+(?:ZONA|DIRECCI[ÓO]N|CALLE:))",
            text,
            re.IGNORECASE,
        )
        address_match = re.search(
            r"CALLE:\s*(.*?)(?=\s+(?:MEDIOS DE CONTACTO|ACTIVIDADES ECON[ÓO]MICAS|OBLIGADO A LLEVAR CONTABILIDAD))",
            text,
            re.IGNORECASE,
        )
        direccion = cls._normalize(address_match.group(0)) if address_match else ""
        if not direccion:
            raise ValueError("No se pudo identificar el domicilio tributario del certificado.")

        artisan_match = re.search(
            r"ARTESANO\s+(.*?)(?=\s+FECHA DE REGISTRO)", text, re.IGNORECASE
        )
        artisan_value = cls._normalize(artisan_match.group(1)) if artisan_match else None
        artesano_calificado = bool(
            artisan_value
            and "NO REGISTRA" not in artisan_value.upper()
            and artisan_value.upper() not in {"NO", "NINGUNO"}
        )
        contact_match = re.search(
            r"MEDIOS DE CONTACTO\s+(.*?)(?=\s+ACTIVIDADES ECON[ÓO]MICAS)",
            text,
            re.IGNORECASE,
        )
        contact_text = cls._normalize(contact_match.group(1)) if contact_match else ""
        email_match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", contact_text, re.IGNORECASE)
        phone_match = re.search(r"(?:\+593|0)?(?:9\d{8}|[2-7]\d{6,7})\b", contact_text)
        status_match = re.search(r"ESTADO\s+(ACTIVO|SUSPENDIDO|PASIVO)", text, re.IGNORECASE)
        jurisdiction_match = re.search(
            r"JURISDICCI[ÓO]N\s+(.*?)(?=\s+TIPO\b)", text, re.IGNORECASE
        )
        verification_match = re.search(
            r"C[ÓO]DIGO DE VERIFICACI[ÓO]N:\s*([A-Z0-9]+)", text, re.IGNORECASE
        )

        warnings: list[str] = []
        agent = cls._boolean_after(
            text, r"AGENTE DE RETENCI[ÓO]N", until=r"CONTRIBUYENTE ESPECIAL"
        )
        special = cls._boolean_after(text, r"CONTRIBUYENTE ESPECIAL")
        if agent:
            warnings.append("El certificado indica agente de retención; complete la resolución antes de guardar.")
        if special:
            warnings.append("El certificado indica contribuyente especial; complete la resolución antes de guardar.")

        return SriRucCertificatePreview(
            ruc=ruc,
            razon_social=razon_social,
            tipo_contribuyente_juridico=tipo,
            regimen=regimen,
            obligado_contabilidad=cls._boolean_after(
                text, r"OBLIGADO A LLEVAR CONTABILIDAD", until=r"UBICACI[ÓO]N GEOGR[ÁA]FICA"
            ),
            agente_retencion=agent,
            contribuyente_especial=special,
            direccion_matriz=direccion,
            email=email_match.group(0).lower() if email_match else None,
            telefono=phone_match.group(0) if phone_match else None,
            artesano_calificado=artesano_calificado,
            additional=SriRucAdditionalData(
                estado=status_match.group(1).upper() if status_match else None,
                artesano=artisan_value,
                provincia=cls._normalize(geo_match.group(1)) if geo_match else None,
                canton=cls._normalize(geo_match.group(2)) if geo_match else None,
                parroquia=cls._normalize(geo_match.group(3)) if geo_match else None,
                jurisdiccion=(
                    cls._normalize(jurisdiction_match.group(1))
                    if jurisdiction_match
                    else None
                ),
                actividades_economicas=cls._extract_list(
                    text,
                    r"ACTIVIDADES ECON[ÓO]MICAS",
                    r"ESTABLECIMIENTOS\s+(?:\d+\s+)?ABIERTOS",
                ),
                obligaciones_tributarias=cls._extract_list(
                    text, r"OBLIGACIONES TRIBUTARIAS", r"(?:LAS OBLIGACIONES|N[ÚU]MEROS DEL RUC)"
                ),
                codigo_verificacion=(
                    verification_match.group(1) if verification_match else None
                ),
            ),
            warnings=warnings,
        )

    @classmethod
    def extract_pdf(cls, content: bytes) -> SriRucCertificatePreview:
        if len(content) > MAX_CERTIFICATE_BYTES:
            raise ValueError("El certificado PDF no puede superar 5 MB.")
        if not content.startswith(b"%PDF"):
            raise ValueError("El archivo seleccionado no es un PDF válido.")
        try:
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise ValueError("El certificado PDF está protegido con contraseña.")
            if len(reader.pages) > MAX_CERTIFICATE_PAGES:
                raise ValueError("El certificado PDF no puede superar 5 páginas.")
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except PdfReadError as exc:
            raise ValueError("No se pudo leer el certificado PDF.") from exc
        if not text.strip():
            raise ValueError("El PDF no contiene texto seleccionable; ingrese los datos manualmente.")
        return cls.parse_text(text)


def certificate_error(detail: str) -> HTTPException:
    return HTTPException(status_code=400, detail=detail)
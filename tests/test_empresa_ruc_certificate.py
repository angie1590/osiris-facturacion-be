from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from osiris.modules.common.empresa.entity import (
    RegimenTributario,
    TipoContribuyenteJuridico,
)
from osiris.modules.common.empresa.ruc_certificate import SriRucCertificateService
from osiris.main import app


SRI_CERTIFICATE_TEXT = """
Certificado
Registro Único de Contribuyentes
PINEDA ALVAREZ DANIEL FERNANDO
Apellidos y nombres Número RUC
0103523908001
Estado
ACTIVO
Régimen
GENERAL
Artesano
No registra
Fecha de registro
06/06/2013
Inicio de actividades Cese de actividades
28/06/2021 31/07/2020
Reinicio de actividades
06/06/2013
Fecha de actualización
01/02/2024
Calle: DE LAS HIEDRAS Número: S/N Intersección: AVENIDA ORDOÑEZ LAZO
Número de piso: 0 Referencia: A UNA CUADRA DE LA ENTRADA A RIO AMARILLO
Dirección
Obligado a llevar contabilidad
Provincia: AZUAY Cantón: CUENCA Parroquia: SAN SEBASTIAN
ZONA 6 / AZUAY / CUENCA NO
Ubicación geográfica
Domicilio tributario
Jurisdicción
Tipo Agente de retención
PERSONAS NATURALES NO
Contribuyente especial
NO
Medios de contacto
No registra
Actividades económicas
• G46510101 - VENTA AL POR MAYOR DE COMPUTADORAS Y EQUIPO PERIFÉRICO.
• G47411101 - VENTA AL POR MENOR DE COMPUTADORAS EN ESTABLECIMIENTOS ESPECIALIZADOS.
• M74901001 - PRESTACION DE SERVICIOS PROFESIONALES.
Establecimientos
1 Abiertos Cerrados 0
Obligaciones tributarias
• 2011 DECLARACION DE IVA
Las obligaciones tributarias reflejadas en este documento están sujetas a cambios.
Números del RUC anteriores
No registra
Código de verificación: RCR1716479633455575
"""


def test_parsea_certificado_ruc_sri_adjunto():
    preview = SriRucCertificateService.parse_text(SRI_CERTIFICATE_TEXT)

    assert preview.ruc == "0103523908001"
    assert preview.razon_social == "PINEDA ALVAREZ DANIEL FERNANDO"
    assert preview.tipo_contribuyente_juridico == TipoContribuyenteJuridico.PERSONA_NATURAL
    assert preview.regimen == RegimenTributario.GENERAL
    assert preview.obligado_contabilidad is False
    assert preview.agente_retencion is False
    assert preview.contribuyente_especial is False
    assert "DE LAS HIEDRAS" in preview.direccion_matriz
    assert preview.additional.provincia == "AZUAY"
    assert preview.additional.canton == "CUENCA"
    assert preview.additional.parroquia == "SAN SEBASTIAN"
    assert preview.additional.artesano == "No registra"
    assert len(preview.additional.actividades_economicas) == 3
    assert preview.additional.obligaciones_tributarias == ["2011 - DECLARACION DE IVA"]
    assert preview.additional.codigo_verificacion == "RCR1716479633455575"
    assert preview.warnings == []


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"not a pdf", "no es un PDF válido"),
        (b"%PDF" + b"0" * (5 * 1024 * 1024 + 1), "no puede superar 5 MB"),
    ],
)
def test_rechaza_contenido_pdf_invalido(content: bytes, message: str):
    with pytest.raises(ValueError, match=message):
        SriRucCertificateService.extract_pdf(content)


def test_ruc_del_certificado_es_valido_como_numero_decimal():
    preview = SriRucCertificateService.parse_text(SRI_CERTIFICATE_TEXT)
    assert Decimal(preview.ruc) > 0


def test_parsea_indicadores_tributarios_positivos_con_advertencias():
    text = (
        SRI_CERTIFICATE_TEXT.replace(
            "ZONA 6 / AZUAY / CUENCA NO\nUbicación geográfica",
            "ZONA 6 / AZUAY / CUENCA SI\nUbicación geográfica",
        )
        .replace("PERSONAS NATURALES NO", "PERSONAS NATURALES SI")
        .replace("Contribuyente especial\nNO", "Contribuyente especial\nSI")
    )

    preview = SriRucCertificateService.parse_text(text)

    assert preview.obligado_contabilidad is True
    assert preview.agente_retencion is True
    assert preview.contribuyente_especial is True
    assert len(preview.warnings) == 2


def test_endpoint_previsualiza_certificado_pdf():
    preview = SriRucCertificateService.parse_text(SRI_CERTIFICATE_TEXT)
    with patch.object(SriRucCertificateService, "extract_pdf", return_value=preview):
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/empresas/importar-certificado-ruc",
                files={"file": ("ruc.pdf", b"%PDF-1.4 test", "application/pdf")},
            )

    assert response.status_code == 200
    assert response.json()["ruc"] == "0103523908001"
    assert response.json()["additional"]["provincia"] == "AZUAY"


def test_endpoint_rechaza_archivo_que_no_es_pdf():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/empresas/importar-certificado-ruc",
            files={"file": ("ruc.txt", b"texto", "text/plain")},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Debe seleccionar un archivo PDF."
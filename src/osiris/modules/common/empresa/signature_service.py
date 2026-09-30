from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timezone

from cryptography import x509
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.serialization import pkcs12
from fastapi import HTTPException
from sqlmodel import Session

from osiris.core.settings import get_settings
from osiris.modules.common.empresa.entity import Empresa


MAX_P12_BYTES = 5 * 1024 * 1024


class EmpresaSignatureService:
    @staticmethod
    def _fernet() -> Fernet:
        digest = hashlib.sha256(get_settings().SECRET_KEY.encode("utf-8")).digest()
        return Fernet(base64.urlsafe_b64encode(digest))

    @staticmethod
    def _expiration(certificate: x509.Certificate) -> datetime:
        value = getattr(certificate, "not_valid_after_utc", None)
        if value is None:
            value = certificate.not_valid_after.replace(tzinfo=timezone.utc)
        return value.replace(tzinfo=None)

    def save(
        self,
        session: Session,
        empresa_id,
        *,
        filename: str,
        content: bytes,
        password: str,
    ) -> Empresa:
        empresa = session.get(Empresa, empresa_id)
        if not empresa or not empresa.activo:
            raise HTTPException(status_code=404, detail="Empresa no encontrada.")
        if len(content) > MAX_P12_BYTES or not content:
            raise HTTPException(status_code=400, detail="La firma P12 debe pesar entre 1 byte y 5 MB.")
        if not filename.lower().endswith((".p12", ".pfx")):
            raise HTTPException(status_code=400, detail="Debe seleccionar un archivo .p12 o .pfx.")
        try:
            private_key, certificate, _ = pkcs12.load_key_and_certificates(
                content, password.encode("utf-8")
            )
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail="Archivo o contraseña de firma electrónica inválidos.") from exc
        if private_key is None or certificate is None:
            raise HTTPException(status_code=400, detail="La firma no contiene certificado y clave privada.")
        expiration = self._expiration(certificate)
        if expiration <= datetime.utcnow():
            raise HTTPException(status_code=400, detail="La firma electrónica está caducada.")
        cipher = self._fernet()
        empresa.firma_electronica_cifrada = cipher.encrypt(content)
        empresa.firma_password_cifrada = cipher.encrypt(password.encode("utf-8"))
        empresa.firma_nombre_archivo = filename
        empresa.firma_caduca_en = expiration
        session.add(empresa)
        session.commit()
        session.refresh(empresa)
        return empresa

    def credentials(self, empresa: Empresa) -> tuple[bytes, str]:
        if not empresa.firma_electronica_configurada:
            raise HTTPException(
                status_code=400,
                detail="La empresa no tiene una firma electrónica vigente configurada.",
            )
        try:
            cipher = self._fernet()
            return (
                cipher.decrypt(empresa.firma_electronica_cifrada),
                cipher.decrypt(empresa.firma_password_cifrada).decode("utf-8"),
            )
        except (InvalidToken, UnicodeDecodeError) as exc:
            raise HTTPException(status_code=500, detail="No se pudo descifrar la firma electrónica.") from exc

    @staticmethod
    def delete(session: Session, empresa_id) -> Empresa:
        empresa = session.get(Empresa, empresa_id)
        if not empresa or not empresa.activo:
            raise HTTPException(status_code=404, detail="Empresa no encontrada.")
        empresa.firma_electronica_cifrada = None
        empresa.firma_password_cifrada = None
        empresa.firma_nombre_archivo = None
        empresa.firma_caduca_en = None
        session.add(empresa)
        session.commit()
        session.refresh(empresa)
        return empresa
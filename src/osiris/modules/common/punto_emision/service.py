from __future__ import annotations

from datetime import datetime
from typing import Optional, cast
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import Session, select

from osiris.core.permisos import verificar_permiso
from osiris.domain.service import BaseService
from osiris.modules.common.audit_log.entity import AuditLog
from .repository import PuntoEmisionRepository
from .entity import PuntoEmision, PuntoEmisionSecuencial, TipoDocumentoSRI
from osiris.modules.common.rol.entity import Rol
from osiris.modules.common.sucursal.entity import Sucursal
from osiris.modules.common.usuario.entity import Usuario


class PuntoEmisionService(BaseService):
    MODULO_PERMISO_AJUSTE_SECUENCIAL = "PUNTOS_EMISION"

    repo = PuntoEmisionRepository()
    fk_models = {
        "sucursal_id": Sucursal,
    }

    # ---------- atajos ----------
    def list_by_sucursal(
        self, session: Session, *, sucursal_id: UUID,
        limit: int, offset: int, only_active: bool = True
    ):
        return self.list_paginated(
            session,
            limit=limit,
            offset=offset,
            only_active=only_active,
            sucursal_id=sucursal_id,
        )

    def get_by_clave_natural(
        self, session: Session, *, sucursal_id: UUID, codigo: str, only_active: Optional[bool] = None
    ) -> Optional[PuntoEmision]:
        stmt = select(PuntoEmision).where(
            PuntoEmision.sucursal_id == sucursal_id,
            PuntoEmision.codigo == codigo,
        )
        if only_active is True:
            stmt = stmt.where(PuntoEmision.activo.is_(True))
        return session.exec(stmt).first()

    @staticmethod
    def _require_admin(session: Session, usuario_id: UUID) -> None:
        stmt = (
            select(Usuario, Rol)
            .join(Rol, Rol.id == Usuario.rol_id)
            .where(
                Usuario.id == usuario_id,
                Usuario.activo.is_(True),
                Rol.activo.is_(True),
            )
        )
        row = session.exec(stmt).first()
        if not row:
            raise HTTPException(status_code=403, detail="Usuario administrador invalido o inactivo")

        _, rol = row
        if rol.nombre.strip().upper() not in {"ADMIN", "ADMINISTRADOR"}:
            raise HTTPException(status_code=403, detail="Solo un administrador puede ajustar secuenciales")

    def _require_permiso_ajuste_secuencial(self, session: Session, usuario_id: UUID) -> None:
        if not verificar_permiso(
            session,
            usuario_id,
            self.MODULO_PERMISO_AJUSTE_SECUENCIAL,
            "actualizar",
        ):
            raise HTTPException(
                status_code=403,
                detail=(
                    "No tiene permiso especifico para ajustar secuenciales "
                    f"({self.MODULO_PERMISO_AJUSTE_SECUENCIAL})."
                ),
            )

    @staticmethod
    def _sri_pad_9(numero: int) -> str:
        return str(numero).zfill(9)

    def _get_or_create_locked_secuencial(
        self,
        session: Session,
        *,
        punto_emision_id: UUID,
        tipo_documento: TipoDocumentoSRI,
        usuario_auditoria: Optional[str] = None,
    ) -> PuntoEmisionSecuencial:
        punto_emision = session.get(PuntoEmision, punto_emision_id)
        if not punto_emision or not punto_emision.activo:
            raise HTTPException(status_code=404, detail="Punto de emision no encontrado o inactivo")

        try:
            stmt = (
                select(PuntoEmisionSecuencial)
                .where(
                    PuntoEmisionSecuencial.punto_emision_id == punto_emision_id,
                    PuntoEmisionSecuencial.tipo_documento == tipo_documento,
                )
                .with_for_update()
            )
            secuencial = session.exec(stmt).one()
        except NoResultFound:
            # PuntoEmision stores the next number; the ledger stores the last issued number.
            inicial = max(punto_emision.secuencial_actual - 1, 0) if tipo_documento == TipoDocumentoSRI.FACTURA else 0
            try:
                with session.begin_nested():
                    secuencial_nuevo = PuntoEmisionSecuencial(
                        punto_emision_id=punto_emision_id,
                        tipo_documento=tipo_documento,
                        secuencial_actual=inicial,
                        usuario_auditoria=usuario_auditoria or punto_emision.usuario_auditoria,
                        activo=True,
                    )
                    session.add(secuencial_nuevo)
                    session.flush()
            except IntegrityError:
                # Otra transaccion lo inserto primero; continuamos para bloquear el registro ya creado.
                pass

            stmt = (
                select(PuntoEmisionSecuencial)
                .where(
                    PuntoEmisionSecuencial.punto_emision_id == punto_emision_id,
                    PuntoEmisionSecuencial.tipo_documento == tipo_documento,
                )
                .with_for_update()
            )
            secuencial = session.exec(stmt).one()

        if hasattr(secuencial, "activo") and secuencial.activo is False:
            secuencial.activo = True
        return secuencial

    def obtener_siguiente_secuencial(
        self,
        session: Session,
        *,
        punto_emision_id: UUID,
        tipo_documento: TipoDocumentoSRI,
        usuario_auditoria: Optional[str] = None,
    ) -> str:
        """Preview only: no counter reservation happens outside sale issue."""
        punto = session.get(PuntoEmision, punto_emision_id)
        if not punto or not punto.activo:
            raise HTTPException(status_code=404, detail="Punto de emision no encontrado o inactivo")
        row = session.exec(
            select(PuntoEmisionSecuencial).where(
                PuntoEmisionSecuencial.punto_emision_id == punto_emision_id,
                PuntoEmisionSecuencial.tipo_documento == tipo_documento,
            ).with_for_update()
        ).first()
        next_number = (
            row.secuencial_actual + 1
            if row
            else punto.secuencial_actual
            if tipo_documento == TipoDocumentoSRI.FACTURA
            else 1
        )
        if next_number > 999999999:
            raise HTTPException(status_code=409, detail="La serie alcanzó el máximo secuencial SRI (999999999).")
        return self._sri_pad_9(next_number)

    def ajustar_secuencial_manual(
        self,
        session: Session,
        *,
        punto_emision_id: UUID,
        tipo_documento: TipoDocumentoSRI,
        nuevo_secuencial: int,
        usuario_id: UUID,
        justificacion: str,
    ) -> PuntoEmisionSecuencial:
        if not justificacion or not justificacion.strip():
            raise HTTPException(status_code=400, detail="La justificacion es obligatoria")

        self._require_admin(session, usuario_id)
        self._require_permiso_ajuste_secuencial(session, usuario_id)
        from osiris.modules.ventas.models import Venta

        used = session.exec(
            select(Venta.id)
            .where(
                Venta.punto_emision_id == punto_emision_id,
                cast(ColumnElement[str | None], Venta.secuencial_formateado).is_not(None),
            )
            .limit(1)
        ).first()
        if used:
            raise HTTPException(
                status_code=409,
                detail="La serie ya contiene comprobantes; cree un nuevo punto para iniciar otra serie autorizada.",
            )
        secuencial = self._get_or_create_locked_secuencial(
            session,
            punto_emision_id=punto_emision_id,
            tipo_documento=tipo_documento,
            usuario_auditoria=str(usuario_id),
        )

        secuencial_anterior = secuencial.secuencial_actual + 1
        if not 1 <= nuevo_secuencial <= 999999999:
            raise HTTPException(status_code=400, detail="El secuencial inicial debe estar entre 1 y 999999999.")
        estado_anterior = {
            "punto_emision_id": str(punto_emision_id),
            "tipo_documento": tipo_documento.value,
            "proximo_secuencial": secuencial_anterior,
            "secuencial_sri": self._sri_pad_9(secuencial_anterior),
        }

        secuencial.secuencial_actual = nuevo_secuencial - 1
        punto = session.get(PuntoEmision, punto_emision_id)
        if punto and tipo_documento == TipoDocumentoSRI.FACTURA:
            punto.secuencial_actual = nuevo_secuencial
            session.add(punto)
        secuencial.usuario_auditoria = str(usuario_id)
        if hasattr(secuencial, "actualizado_en"):
            secuencial.actualizado_en = datetime.utcnow()

        estado_nuevo = {
            "punto_emision_id": str(punto_emision_id),
            "tipo_documento": tipo_documento.value,
            "proximo_secuencial": nuevo_secuencial,
            "secuencial_sri": self._sri_pad_9(nuevo_secuencial),
            "justificacion": justificacion.strip(),
            "motivo_salto": justificacion.strip(),
            "delta": nuevo_secuencial - secuencial_anterior,
        }
        audit = AuditLog(
            tabla_afectada="tbl_punto_emision_secuencial",
            registro_id=str(secuencial.id),
            entidad="PuntoEmisionSecuencial",
            entidad_id=secuencial.id,
            accion="MANUAL_ADJUST",
            estado_anterior=estado_anterior,
            estado_nuevo=estado_nuevo,
            before_json=estado_anterior,
            after_json=estado_nuevo,
            usuario_id=str(usuario_id),
            usuario_auditoria=str(usuario_id),
            fecha=datetime.utcnow(),
        )

        session.add(secuencial)
        session.add(audit)
        session.commit()
        session.refresh(secuencial)
        return secuencial

    def obtener_siguiente_secuencial_formateado(
        self,
        session: Session,
        *,
        punto_emision_id: UUID,
        tipo_documento: TipoDocumentoSRI,
        usuario_auditoria: Optional[str] = None,
    ) -> str:
        return self.obtener_siguiente_secuencial(
            session,
            punto_emision_id=punto_emision_id,
            tipo_documento=tipo_documento,
            usuario_auditoria=usuario_auditoria,
        )

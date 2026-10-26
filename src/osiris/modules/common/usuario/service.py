# src/osiris/modules/common/usuario/service.py
from __future__ import annotations

from typing import Any, cast
import secrets
import string
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlmodel import Session, select
from uuid import UUID

from osiris.domain.service import BaseService, FkSpec
from osiris.core import security
from osiris.core.db import SOFT_DELETE_INCLUDE_INACTIVE_OPTION
from osiris.core.audit_context import get_current_user_id
from osiris.core.directory_permissions import require_directory_permission as requiere_permiso
from .repository import UsuarioRepository
from .entity import Usuario
from osiris.modules.common.persona.entity import Persona
from osiris.modules.common.rol.entity import Rol
from osiris.modules.common.persona.composition import resolve_persona
from osiris.modules.common.empleado.entity import Empleado
from .models import UsuarioRead


def check_directory_references(session: Session, data: dict[str, Any], references: dict[str, FkSpec]) -> None:
    for field, specification in references.items():
        if data.get(field) is None:
            continue
        model, primary_key, require_active = BaseService._parse_fk_spec(specification)
        reference: Any = session.exec(select(model).where(getattr(model, primary_key) == data[field]).execution_options(
            **{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True}
        )).first()
        if reference is None:
            raise HTTPException(status_code=404, detail=f"{model.__name__} no encontrado")
        if require_active and getattr(reference, "activo", True) is False:
            raise HTTPException(status_code=409, detail=f"{model.__name__} inactivo")


class UsuarioService(BaseService[Usuario, UsuarioRead]):
    """
    - Validación de FKs (persona_id, rol_id) se hace en BaseService usando fk_models.
    - Unicidades (username, persona_id único) se delegan al BaseRepository (maneja IntegrityError -> 409).
    - Reglas de negocio aquí: hash de password, campos no editables en update.
    """
    repo = UsuarioRepository()
    fk_models = {
        "persona_id": Persona,
        "rol_id": Rol,
    }

    def _check_fk_active_and_exists(self, session: Session, data: dict[str, Any]) -> None:
        check_directory_references(session, data, self.fk_models)

    # ---------- helpers ----------
    @staticmethod
    def _ensure_dict(data: Any) -> dict[str, Any]:
        payload: dict[str, Any]
        if hasattr(data, "model_dump"):
            payload = data.model_dump(exclude_unset=True)
        elif isinstance(data, dict):
            payload = data.copy()
        else:
            payload = {key: value for key, value in vars(data).items() if not key.startswith("_")}
        for field in ("persona_id", "rol_id"):
            if payload.get(field) is not None:
                try:
                    payload[field] = UUID(str(payload[field]))
                except (TypeError, ValueError) as exc:
                    raise HTTPException(status_code=422, detail=f"{field} debe ser UUID") from exc
        actor = get_current_user_id()
        if actor:
            payload["usuario_auditoria"] = actor
        return payload

    @staticmethod
    def _pop_and_hash_password(data: dict[str, Any]) -> None:
        plain = data.pop("password", None)
        if plain is not None:
            try:
                security.validate_password(plain)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            data["password_hash"] = security.hash_password(plain)

    # ---------- CREATE ----------
    def create(self, session: Session, data: Any, *, commit: bool = True) -> Usuario:
        try:
            actor = get_current_user_id()
            if actor:
                requiere_permiso(session, UUID(actor), "USUARIOS", "crear")
            payload = resolve_persona(session, self._ensure_dict(data).copy())
            if not payload.get("password"):
                raise HTTPException(status_code=400, detail="La contrasena es obligatoria")
            username = str(payload.get("username", "")).strip().lower()
            if not 3 <= len(username) <= 120:
                raise HTTPException(status_code=400, detail="Username debe tener entre 3 y 120 caracteres")
            existing = session.exec(select(Usuario).where(or_(
                Usuario.persona_id == payload["persona_id"],
                func.lower(func.trim(Usuario.username)) == username,
            )).execution_options(**{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True})).first()
            if existing is not None:
                raise HTTPException(status_code=409, detail="Usuario ya registrado; requiere una decision administrativa o reactivacion explicita")
            payload["username"] = username
            payload["requiere_cambio_password"] = True
            self._pop_and_hash_password(payload)
            self._check_fk_active_and_exists(session, payload)
            user = cast(Usuario, self.repo.create(session, payload))
            if commit:
                session.commit()
                session.refresh(user)
            return user
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    # ---------- UPDATE (solo rol_id, password, usuario_auditoria) ----------
    def update(self, session: Session, item_id: UUID, data: Any, *, commit: bool = True) -> Usuario | None:
        try:
            incoming = self._ensure_dict(data).copy()
            current = self.repo.get(session, item_id)
            if current is None:
                return None
            for field in ("persona_id", "username"):
                if field in incoming and str(incoming[field]) != str(getattr(current, field)):
                    raise HTTPException(status_code=409, detail=f"{field} es inmutable")
                incoming.pop(field, None)
            allowed = {"rol_id", "password", "usuario_auditoria"}
            if incoming.keys() - allowed:
                raise HTTPException(status_code=422, detail="Campos no editables; use acciones explicitas de ciclo de vida")
            if "rol_id" in incoming and incoming["rol_id"] is None:
                raise HTTPException(status_code=422, detail="rol_id no puede ser null")
            if incoming.get("password") is not None:
                self._pop_and_hash_password(incoming)
                incoming["requiere_cambio_password"] = True
                incoming["sesion_invalidada_en"] = datetime.utcnow()
            else:
                incoming.pop("password", None)
            self._check_fk_active_and_exists(session, incoming)
            updated = cast(Usuario, self.repo.update(session, current, incoming))
            if commit:
                session.commit()
                session.refresh(updated)
            return updated
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    # ---------- Auth opcional ----------
    def authenticate(self, session: Session, username: str, password: str) -> Usuario | None:
        user = session.exec(select(Usuario).where(func.lower(func.trim(Usuario.username)) == username.strip().lower())).first()
        if not user or not user.activo:
            return None
        if not security.verify_password(password, user.password_hash):
            return None
        return user

    # ---------- Reset password ----------
    @staticmethod
    def _generate_temp_password(length: int = 12) -> str:
        if length < security.PASSWORD_MIN_LENGTH:
            raise ValueError("Longitud temporal inferior a la politica de contrasenas")
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def reset_password(self, session: Session, item_id: UUID, *, usuario_auditoria: str | None = None) -> tuple[Usuario, str]:
        try:
            user = self.repo.get(session, item_id)
            if not user:
                raise HTTPException(status_code=404, detail="Usuario no encontrado")
            if hasattr(user, "activo") and user.activo is False:
                raise HTTPException(status_code=409, detail="Usuario inactivo")

            temp_password = self._generate_temp_password()
            security.validate_password(temp_password)
            hashed = security.hash_password(temp_password)
            requiere_cambio_password = True

            data: dict[str, Any] = {
                "password_hash": hashed,
                "requiere_cambio_password": requiere_cambio_password,
                "sesion_invalidada_en": datetime.utcnow(),
            }
            if usuario_auditoria:
                data["usuario_auditoria"] = usuario_auditoria

            updated = self.repo.update(session, user, self._ensure_dict(data))
            session.commit()
            session.refresh(updated)
            return updated, temp_password
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    def delete(self, session: Session, item_id: UUID, *, commit: bool = True) -> bool | None:
        try:
            user = session.exec(select(Usuario).where(Usuario.id == item_id).execution_options(
                **{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True}
            ).with_for_update()).first()
            if user is None:
                return None
            self.repo.update(session, user, {"activo": False, "sesion_invalidada_en": datetime.utcnow()})
            if commit:
                session.commit()
            return True
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    def reactivate(self, session: Session, item_id: UUID, *, confirmar_empleado_inactivo: bool = False,
                   usuario_auditoria: str | None = None, commit: bool = True) -> Usuario:
        try:
            user = session.exec(select(Usuario).where(Usuario.id == item_id).execution_options(
                **{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True}
            ).with_for_update()).first()
            if user is None:
                raise HTTPException(status_code=404, detail="Usuario no encontrado")
            resolve_persona(session, {"persona_id": user.persona_id})
            self._check_fk_active_and_exists(session, {"rol_id": user.rol_id})
            employee = session.exec(select(Empleado).where(Empleado.persona_id == user.persona_id).execution_options(
                **{SOFT_DELETE_INCLUDE_INACTIVE_OPTION: True}
            )).first()
            if employee is not None and not employee.activo and not confirmar_empleado_inactivo:
                raise HTTPException(status_code=409, detail="Empleado inactivo; confirmar_empleado_inactivo requiere decision administrativa explicita")
            updated = cast(Usuario, self.repo.update(session, user, self._ensure_dict({
                "activo": True, "usuario_auditoria": usuario_auditoria,
            })))
            if commit:
                session.commit()
                session.refresh(updated)
            return updated
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    def invalidate_session(self, session: Session, user: Usuario) -> None:
        try:
            self.repo.update(session, user, {"sesion_invalidada_en": datetime.utcnow()})
            session.commit()
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    def change_password(self, session: Session, user: Usuario, *, new_password: str,
                        current_password: str | None = None) -> None:
        try:
            if not user.requiere_cambio_password and not current_password:
                raise HTTPException(status_code=400, detail="La contrasena actual es obligatoria")
            if current_password and not security.verify_password(current_password, user.password_hash):
                raise HTTPException(status_code=400, detail="Contrasena actual incorrecta")
            payload: dict[str, Any] = {"password": new_password}
            self._pop_and_hash_password(payload)
            payload["requiere_cambio_password"] = False
            self.repo.update(session, user, payload)
            session.commit()
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    def set_approval_code(self, session: Session, user: Usuario, code: str) -> None:
        try:
            self.repo.update(session, user, {"codigo_aprobacion_hash": security.hash_password(code)})
            session.commit()
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    @staticmethod
    def to_read(session: Session, user: Usuario) -> UsuarioRead:
        return UsuarioRead.model_validate({
            **user.model_dump(), "persona": session.get(Persona, user.persona_id),
            "tiene_codigo_aprobacion": user.codigo_aprobacion_hash is not None,
            "rol_nombre": (role.nombre if (role := session.get(Rol, user.rol_id)) else None),
        })

    # ---------- Verify password ----------
    def verify_password(self, session: Session, item_id: UUID, password: str) -> bool:
        user = self.repo.get(session, item_id)
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if hasattr(user, "activo") and user.activo is False:
            raise HTTPException(status_code=409, detail="Usuario inactivo")
        return security.verify_password(password, getattr(user, "password_hash", ""))

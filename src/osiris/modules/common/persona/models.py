# src/osiris/modules/common/persona/models.py
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, Annotated
from uuid import UUID

from pydantic import EmailStr, StringConstraints, model_validator

from osiris.domain.base_models import BaseOSModel
from osiris.utils.validacion_identificacion import ValidacionCedulaRucService


class TipoIdentificacion(str, Enum):
    CEDULA = "CEDULA"
    RUC = "RUC"
    PASAPORTE = "PASAPORTE"


# Atajos de constraints (Pydantic v2)
Str120 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Str255 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
IdentStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
TelStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]


class PersonaBase(BaseOSModel):
    identificacion: IdentStr
    tipo_identificacion: TipoIdentificacion
    nombre: Str120
    apellido: Str120
    direccion: Optional[Str255] = None
    telefono: Optional[TelStr] = None
    ciudad: Optional[Str120] = None
    email: Optional[EmailStr] = None


class PersonaCreate(PersonaBase):
    usuario_auditoria: str

    @model_validator(mode="after")
    def validar_identificacion_por_tipo(self) -> "PersonaCreate":
        tipo = self.tipo_identificacion
        identificacion = self.identificacion

        if tipo == TipoIdentificacion.CEDULA:
            if not ValidacionCedulaRucService.es_cedula_valida(identificacion):
                raise ValueError("La cédula ingresada no es válida.")
        elif tipo == TipoIdentificacion.RUC:
            if not ValidacionCedulaRucService.es_ruc_persona_natural_valido(identificacion):
                raise ValueError("El RUC ingresado no corresponde a una persona natural.")
        elif tipo == TipoIdentificacion.PASAPORTE:
            if not identificacion or len(identificacion.strip()) < 5:
                raise ValueError("El pasaporte debe tener al menos 5 caracteres.")
        return self


class PersonaUpdate(BaseOSModel):
    identificacion: Optional[IdentStr] = None
    tipo_identificacion: Optional[TipoIdentificacion] = None
    nombre: Optional[Str120] = None
    apellido: Optional[Str120] = None
    direccion: Optional[Str255] = None
    telefono: Optional[TelStr] = None
    ciudad: Optional[Str120] = None
    email: Optional[EmailStr] = None
    usuario_auditoria: str
    activo: Optional[bool] = None

    @model_validator(mode="after")
    def validar_identificacion_si_cambia(self) -> "PersonaUpdate":
        tipo = self.tipo_identificacion
        identificacion = self.identificacion

        if identificacion and tipo:
            if tipo == TipoIdentificacion.CEDULA:
                if not ValidacionCedulaRucService.es_cedula_valida(identificacion):
                    raise ValueError("La cédula ingresada no es válida.")
            elif tipo == TipoIdentificacion.RUC:
                if not ValidacionCedulaRucService.es_ruc_persona_natural_valido(identificacion):
                    raise ValueError("El RUC ingresado no corresponde a una persona natural.")
            elif tipo == TipoIdentificacion.PASAPORTE:
                if len(identificacion.strip()) < 5:
                    raise ValueError("El pasaporte debe tener al menos 5 caracteres.")
        elif identificacion or tipo:
            raise ValueError("Si vas a actualizar la identificación, debes enviar también el tipo.")
        return self



class PersonaRead(PersonaBase):
    id: UUID
    activo: bool
    # Estos nombres siguen lo que traen los mixins actuales:
    creado_en: datetime
    actualizado_en: datetime
    usuario_auditoria: Optional[str] = None

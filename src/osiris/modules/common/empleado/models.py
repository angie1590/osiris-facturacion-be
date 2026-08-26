from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Optional
from uuid import UUID

from pydantic import Field as PydField, condecimal, model_validator
from osiris.domain.base_models import BaseOSModel

SalarioType = Annotated[condecimal(max_digits=10, decimal_places=2), "Salario decimal"]

def _min_employee_age() -> int:
    # Parametrizable por env var EMP_MIN_AGE, por defecto 16
    try:
        return max(0, int(os.getenv("EMP_MIN_AGE", "16")))
    except Exception:
        return 16


def _calc_age(born: date, today: date) -> int:
    # Cálculo correcto de edad (sin aproximaciones por días)
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


class UsuarioInlineCreate(BaseOSModel):
    username: str = PydField(min_length=3, max_length=150)
    password: str = PydField(min_length=6)
    rol_id: UUID
    usuario_auditoria: Optional[str] = None


class EmpleadoCreate(BaseOSModel):
    persona_id: UUID
    empresa_id: UUID
    salario: SalarioType
    fecha_ingreso: date
    fecha_nacimiento: Optional[date] = None
    fecha_salida: Optional[date] = None
    foto: Optional[str] = None

    # Al crear el empleado, también se crea el usuario
    usuario: UsuarioInlineCreate
    usuario_auditoria: Optional[str] = None

    @model_validator(mode="after")
    def _validar_reglas_de_fecha(self):
        min_age = _min_employee_age()

        # 1) Edad mínima si fecha_nacimiento fue enviada
        if self.fecha_nacimiento is not None:
            edad = _calc_age(self.fecha_nacimiento, date.today())
            if edad < min_age:
                raise ValueError(f"El empleado debe tener al menos {min_age} años.")

        # 2) fecha_salida > fecha_ingreso si ambas existen
        if self.fecha_salida is not None:
            if self.fecha_salida <= self.fecha_ingreso:
                raise ValueError("La fecha de salida debe ser posterior a la fecha de ingreso.")

        if self.fecha_ingreso > date.today():
            raise ValueError("La fecha de ingreso no puede ser en el futuro.")

        return self


class EmpleadoUpdate(BaseOSModel):
    # persona_id NO se puede cambiar
    empresa_id: Optional[UUID] = None
    salario: Optional[SalarioType] = None
    fecha_ingreso: Optional[date] = None
    fecha_nacimiento: Optional[date] = None
    fecha_salida: Optional[date] = None
    foto: Optional[str] = None
    usuario_auditoria: Optional[str] = None

    @model_validator(mode="after")
    def _validar_edad_si_envia_fecha_nacimiento(self):
        # Validamos edad mínima sólo si llega fecha_nacimiento en el payload
        if self.fecha_nacimiento is not None:
            min_age = _min_employee_age()
            edad = _calc_age(self.fecha_nacimiento, date.today())
            if edad < min_age:
                raise ValueError(f"El empleado debe tener al menos {min_age} años.")
        return self


class EmpleadoRead(BaseOSModel):
    id: UUID
    persona_id: UUID
    empresa_id: UUID
    salario: Decimal
    fecha_ingreso: date
    fecha_nacimiento: Optional[date] = None
    fecha_salida: Optional[date] = None
    foto: Optional[str] = None
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    usuario_auditoria: Optional[str] = None

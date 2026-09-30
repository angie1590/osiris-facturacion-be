# src/osiris/modules/common/empresa/models.py
from __future__ import annotations
from datetime import datetime
from typing import Optional, Annotated
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator, model_validator
from osiris.utils.validacion_identificacion import ValidacionCedulaRucService
from .entity import RegimenTributario, ModoEmisionEmpresa, TipoContribuyenteJuridico


# Atajos de tipos con restricciones
RazonSocial = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
NombreComercial = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r'^[A-Za-zÁÉÍÓÚÑáéíóúñ0-9\s\.\,\-]+$')]
RUC = Annotated[str, StringConstraints(min_length=13, max_length=13, pattern=r'^\d{13}$')]
Telefono = Annotated[str, StringConstraints(pattern=r'^\d{7,10}$')]
TipoContribuyenteID = Annotated[str, StringConstraints(min_length=2, max_length=2)]
NumeroResolucion = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


class EmpresaBase(BaseModel):
    razon_social: RazonSocial
    nombre_comercial: Optional[NombreComercial] = None
    ruc: RUC
    direccion_matriz: str
    email: Optional[EmailStr] = None
    telefono: Optional[Telefono] = None
    logo: Optional[str] = None
    tipo_contribuyente_juridico: Optional[TipoContribuyenteJuridico] = None
    obligado_contabilidad: bool = False
    regimen: RegimenTributario = RegimenTributario.GENERAL
    contribuyente_especial: bool = False
    contribuyente_especial_resolucion: Optional[NumeroResolucion] = None
    gran_contribuyente: bool = False
    gran_contribuyente_resolucion: Optional[NumeroResolucion] = None
    agente_retencion: bool = False
    agente_retencion_resolucion: Optional[NumeroResolucion] = None
    artesano_calificado: bool = False
    impuesto_catalogo_ids: list[UUID] = Field(default_factory=list)
    modo_emision: ModoEmisionEmpresa = ModoEmisionEmpresa.ELECTRONICO
    tipo_contribuyente_id: TipoContribuyenteID
    usuario_auditoria: str

    @field_validator("ruc")
    @classmethod
    def _validar_ruc(cls, v: str) -> str:
        if not ValidacionCedulaRucService.es_identificacion_valida(v):
            raise ValueError("El RUC ingresado no es válido.")
        return v

    @model_validator(mode="after")
    def _validar_reglas_tributarias(self):
        if (
            self.tipo_contribuyente_juridico == TipoContribuyenteJuridico.SOCIEDAD
            and self.regimen == RegimenTributario.RIMPE_NEGOCIO_POPULAR
        ):
            raise HTTPException(
                status_code=400,
                detail="La combinación SOCIEDAD + RIMPE_NEGOCIO_POPULAR no está permitida.",
            )

        if self.contribuyente_especial and not self.contribuyente_especial_resolucion:
            raise HTTPException(
                status_code=400,
                detail="El número de resolución es obligatorio para contribuyente especial.",
            )
        if self.gran_contribuyente and not self.gran_contribuyente_resolucion:
            raise HTTPException(
                status_code=400,
                detail="El número de resolución es obligatorio para gran contribuyente.",
            )
        if self.agente_retencion and not self.agente_retencion_resolucion:
            raise HTTPException(
                status_code=400,
                detail="El número de resolución es obligatorio para agente de retención.",
            )
        puede_emitir_nota_venta = (
            self.regimen == RegimenTributario.RIMPE_NEGOCIO_POPULAR
            or self.artesano_calificado
        )
        if self.modo_emision == ModoEmisionEmpresa.NOTA_VENTA_FISICA and not puede_emitir_nota_venta:
            raise HTTPException(
                status_code=400,
                detail="NOTA_VENTA_FISICA solo está permitido para RIMPE Negocio Popular o artesanos calificados.",
            )
        if puede_emitir_nota_venta and self.modo_emision == ModoEmisionEmpresa.ELECTRONICO:
            raise HTTPException(
                status_code=400,
                detail="RIMPE Negocio Popular y artesanos calificados deben emitir notas de venta físicas.",
            )
        return self

class EmpresaCreate(EmpresaBase):
    """POST/PUT (reemplazo total)."""


class EmpresaUpdate(BaseModel):
    razon_social: Optional[RazonSocial] = None
    nombre_comercial: Optional[NombreComercial] = None
    ruc: Optional[RUC] = None
    direccion_matriz: Optional[str] = None
    email: Optional[EmailStr] = None
    telefono: Optional[Telefono] = None
    logo: Optional[str] = None
    tipo_contribuyente_juridico: Optional[TipoContribuyenteJuridico] = None
    obligado_contabilidad: Optional[bool] = None
    regimen: Optional[RegimenTributario] = None
    contribuyente_especial: Optional[bool] = None
    contribuyente_especial_resolucion: Optional[NumeroResolucion] = None
    gran_contribuyente: Optional[bool] = None
    gran_contribuyente_resolucion: Optional[NumeroResolucion] = None
    agente_retencion: Optional[bool] = None
    agente_retencion_resolucion: Optional[NumeroResolucion] = None
    artesano_calificado: Optional[bool] = None
    impuesto_catalogo_ids: Optional[list[UUID]] = None
    modo_emision: Optional[ModoEmisionEmpresa] = None
    tipo_contribuyente_id: Optional[TipoContribuyenteID] = None
    usuario_auditoria: Optional[str] = None

    @field_validator("ruc")
    @classmethod
    def _validar_ruc_opt(cls, v: str) -> str:
        if v is not None and not ValidacionCedulaRucService.es_identificacion_valida(v):
            raise ValueError("El RUC ingresado no es válido.")
        return v

    @model_validator(mode="after")
    def _validar_modo_emision_por_regimen(self):
        puede_emitir_nota_venta = (
            self.regimen == RegimenTributario.RIMPE_NEGOCIO_POPULAR
            or self.artesano_calificado is True
        )
        if self.modo_emision == ModoEmisionEmpresa.NOTA_VENTA_FISICA and not puede_emitir_nota_venta:
            raise HTTPException(
                status_code=400,
                detail=(
                    "NOTA_VENTA_FISICA solo está permitido para RIMPE Negocio Popular "
                    "o artesanos calificados."
                ),
            )
        if puede_emitir_nota_venta and self.modo_emision == ModoEmisionEmpresa.ELECTRONICO:
            raise HTTPException(
                status_code=400,
                detail="RIMPE Negocio Popular y artesanos calificados deben emitir notas de venta físicas.",
            )
        return self

    @model_validator(mode="after")
    def _validar_campos_tributarios_condicionales(self):
        if (
            self.tipo_contribuyente_juridico == TipoContribuyenteJuridico.SOCIEDAD
            and self.regimen == RegimenTributario.RIMPE_NEGOCIO_POPULAR
        ):
            raise ValueError("La combinación SOCIEDAD + RIMPE_NEGOCIO_POPULAR no está permitida.")

        if self.contribuyente_especial is True and not (self.contribuyente_especial_resolucion or "").strip():
            raise ValueError("El número de resolución es obligatorio para contribuyente especial.")

        if self.gran_contribuyente is True and not (self.gran_contribuyente_resolucion or "").strip():
            raise ValueError("El número de resolución es obligatorio para gran contribuyente.")

        if self.agente_retencion is True and not (self.agente_retencion_resolucion or "").strip():
            raise ValueError("El número de resolución es obligatorio para agente de retención.")

        return self

class EmpresaRead(EmpresaBase):
    id: UUID
    activo: bool
    firma_electronica_configurada: bool = False
    firma_nombre_archivo: Optional[str] = None
    firma_caduca_en: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class EmpresaRegimenModoRules(BaseModel):
    tipo_contribuyente_juridico: Optional[TipoContribuyenteJuridico]
    regimen: RegimenTributario
    modo_emision: ModoEmisionEmpresa
    contribuyente_especial: bool = False
    contribuyente_especial_resolucion: Optional[str] = None
    gran_contribuyente: bool = False
    gran_contribuyente_resolucion: Optional[str] = None
    agente_retencion: bool = False
    agente_retencion_resolucion: Optional[str] = None
    artesano_calificado: bool = False

    @model_validator(mode="after")
    def _validar_modo_emision_por_regimen(self):
        puede_emitir_nota_venta = (
            self.regimen == RegimenTributario.RIMPE_NEGOCIO_POPULAR
            or self.artesano_calificado
        )
        if self.modo_emision == ModoEmisionEmpresa.NOTA_VENTA_FISICA and not puede_emitir_nota_venta:
            raise ValueError(
                "NOTA_VENTA_FISICA solo está permitido para RIMPE Negocio Popular o artesanos calificados."
            )
        if puede_emitir_nota_venta and self.modo_emision == ModoEmisionEmpresa.ELECTRONICO:
            raise ValueError(
                "RIMPE Negocio Popular y artesanos calificados deben emitir notas de venta físicas."
            )

        if (
            self.tipo_contribuyente_juridico == TipoContribuyenteJuridico.SOCIEDAD
            and self.regimen == RegimenTributario.RIMPE_NEGOCIO_POPULAR
        ):
            raise ValueError("La combinación SOCIEDAD + RIMPE_NEGOCIO_POPULAR no está permitida.")

        if self.contribuyente_especial and not (self.contribuyente_especial_resolucion or "").strip():
            raise ValueError("El número de resolución es obligatorio para contribuyente especial.")

        if self.gran_contribuyente and not (self.gran_contribuyente_resolucion or "").strip():
            raise ValueError("El número de resolución es obligatorio para gran contribuyente.")

        if self.agente_retencion and not (self.agente_retencion_resolucion or "").strip():
            raise ValueError("El número de resolución es obligatorio para agente de retención.")

        return self

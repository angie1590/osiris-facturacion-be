from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Path, Query, UploadFile, status
from sqlmodel import Session

from osiris.core.db import get_session
from osiris.domain.schemas import PaginatedResponse
from osiris.modules.common.empresa.models import EmpresaCreate, EmpresaRead, EmpresaUpdate
from osiris.modules.common.empresa.service import EmpresaService
from osiris.modules.common.empresa.signature_service import MAX_P12_BYTES, EmpresaSignatureService
from osiris.modules.common.empresa.ruc_certificate import (
    MAX_CERTIFICATE_BYTES,
    SriRucCertificatePreview,
    SriRucCertificateService,
    certificate_error,
)


router = APIRouter(prefix="/api/v1/empresas", tags=["Empresas"])
service = EmpresaService()
signature_service = EmpresaSignatureService()


@router.post(
    "/importar-certificado-ruc",
    response_model=SriRucCertificatePreview,
    summary="Previsualizar datos de certificado RUC PDF",
)
async def importar_certificado_ruc(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise certificate_error("Debe seleccionar un archivo PDF.")
    content = await file.read(MAX_CERTIFICATE_BYTES + 1)
    await file.close()
    try:
        return SriRucCertificateService.extract_pdf(content)
    except ValueError as exc:
        raise certificate_error(str(exc)) from exc


@router.post(
    "/{item_id}/firma-electronica",
    response_model=EmpresaRead,
    summary="Cargar y validar firma electrónica empresarial",
)
async def cargar_firma_electronica(
    item_id: UUID,
    file: UploadFile = File(...),
    password: str = Form(..., min_length=1),
    session: Session = Depends(get_session),
):
    content = await file.read(MAX_P12_BYTES + 1)
    await file.close()
    empresa = signature_service.save(
        session,
        item_id,
        filename=file.filename or "firma.p12",
        content=content,
        password=password,
    )
    return EmpresaRead.model_validate(empresa)


@router.delete(
    "/{item_id}/firma-electronica",
    response_model=EmpresaRead,
    summary="Eliminar firma electrónica empresarial",
)
def eliminar_firma_electronica(
    item_id: UUID,
    session: Session = Depends(get_session),
):
    return EmpresaRead.model_validate(signature_service.delete(session, item_id))


@router.get("", response_model=PaginatedResponse[EmpresaRead])
def list_empresas(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    only_active: bool = Query(True),
    session: Session = Depends(get_session),
):
    items, meta = service.list_paginated(session, only_active=only_active, limit=limit, offset=offset)
    return {"items": items, "meta": meta}


@router.get("/{item_id}", response_model=EmpresaRead)
def get_empresa(item_id: UUID = Path(...), session: Session = Depends(get_session)):
    obj = service.get(session, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"Empresa {item_id} not found")
    return obj


@router.post("", response_model=EmpresaRead, status_code=status.HTTP_201_CREATED)
def create_empresa(payload: EmpresaCreate = Body(...), session: Session = Depends(get_session)):
    return service.create(session, payload.model_dump(exclude_unset=True))


@router.put("/{item_id}", response_model=EmpresaRead)
def update_empresa(
    item_id: UUID = Path(...),
    payload: EmpresaUpdate = Body(...),
    session: Session = Depends(get_session),
):
    updated = service.update(session, item_id, payload.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Empresa {item_id} not found")
    return updated


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_empresa(item_id: UUID = Path(...), session: Session = Depends(get_session)):
    ok = service.delete(session, item_id)
    if ok is None:
        raise HTTPException(status_code=404, detail=f"Empresa {item_id} not found")

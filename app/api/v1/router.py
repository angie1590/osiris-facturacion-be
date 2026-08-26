from fastapi import APIRouter

from app.api.v1.endpoints import auth, empresas

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(empresas.router, prefix="/empresas", tags=["empresas"])

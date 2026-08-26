from pydantic import BaseModel, ConfigDict, Field


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    require_password_change: bool = False


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    current_password: str | None = None
    new_password: str = Field(..., min_length=8)


class EmpresaAccesoResponse(BaseModel):
    empresa_id: int
    razon_social: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class MeResponse(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    is_active: bool
    require_password_change: bool
    empresas: list[EmpresaAccesoResponse] = []

    model_config = ConfigDict(from_attributes=True)

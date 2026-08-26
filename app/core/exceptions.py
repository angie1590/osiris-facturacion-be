from fastapi import HTTPException, status


class AppError(HTTPException):
    def __init__(self, code: str, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST, field_errors: dict[str, str] | None = None):
        body: dict = {"code": code, "message": detail}
        if field_errors:
            body["errors"] = field_errors
        super().__init__(status_code=status_code, detail=body)


class NotFoundError(AppError):
    def __init__(self, code: str = "NOT_FOUND", detail: str = "Resource not found"):
        super().__init__(code=code, detail=detail, status_code=status.HTTP_404_NOT_FOUND)


class ConflictError(AppError):
    def __init__(self, code: str = "CONFLICT", detail: str = "Conflict"):
        super().__init__(code=code, detail=detail, status_code=status.HTTP_409_CONFLICT)


class ForbiddenError(AppError):
    def __init__(self, code: str = "INSUFFICIENT_PERMISSIONS", detail: str = "No tienes permiso para realizar esta acción."):
        super().__init__(code=code, detail=detail, status_code=status.HTTP_403_FORBIDDEN)


class UnauthorizedError(AppError):
    def __init__(self, code: str = "AUTHENTICATION_REQUIRED", detail: str = "Authentication required"):
        super().__init__(code=code, detail=detail, status_code=status.HTTP_401_UNAUTHORIZED)


class ValidationAppError(AppError):
    def __init__(self, code: str = "VALIDATION_ERROR", detail: str = "Validation error", field_errors: dict[str, str] | None = None):
        super().__init__(code=code, detail=detail, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, field_errors=field_errors)

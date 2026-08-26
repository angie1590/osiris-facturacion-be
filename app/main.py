import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.redis import close_redis, get_redis

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_redis()
    logger.info("Redis connected")
    yield
    await close_redis()
    logger.info("Redis closed")


app = FastAPI(
    title="Osiris Facturación API",
    description="API de facturación electrónica para PyMEs (Ecuador)",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.core.exceptions import AppError  # noqa: E402


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content=exc.detail)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    field_errors: dict[str, str] = {}
    for error in exc.errors():
        loc = error.get("loc", [])
        field = str(loc[-1]) if len(loc) > 1 else "body"
        field_errors[field] = error.get("msg", "Invalid value")
    return JSONResponse(
        status_code=422,
        content={"code": "VALIDATION_ERROR", "message": "Los datos enviados no son válidos.", "errors": field_errors},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(status_code=500, content={"code": "INTERNAL_SERVER_ERROR", "message": "An unexpected error occurred"})


from app.api.v1.router import api_router  # noqa: E402

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok"}

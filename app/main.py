from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.exception_logging import register_exception_logging
from app.core.lifespan import lifespan
from app.core.logging import setup_logging
from app.middleware.request_context import RequestContextMiddleware

_settings = get_settings()
setup_logging(_settings)


def create_app() -> FastAPI:
    settings = _settings

    application = FastAPI(
        title=settings.app_name,
        version=__version__,
        debug=settings.app_debug,
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(RequestContextMiddleware)

    application.include_router(api_router, prefix=settings.api_v1_prefix)
    register_exception_logging(application)

    @application.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"service": settings.app_name, "version": __version__}

    return application


app = create_app()

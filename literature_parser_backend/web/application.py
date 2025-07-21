from importlib import metadata

from fastapi import FastAPI
from fastapi.responses import UJSONResponse

from literature_parser_backend.web.api.router import api_router
from literature_parser_backend.web.lifespan import lifespan_setup


def get_app() -> FastAPI:
    """
    Get FastAPI application.

    This is the main constructor of an application.

    :return: application.
    """
    try:
        version = metadata.version("literature_parser_backend")
    except Exception:
        version = "0.1.0"  # Fallback version for development

    app = FastAPI(
        title="literature_parser_backend",
        version=version,
        lifespan=lifespan_setup,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        default_response_class=UJSONResponse,
    )

    # Main router for the API.
    app.include_router(router=api_router, prefix="/api")

    return app

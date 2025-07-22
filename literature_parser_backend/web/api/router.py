from fastapi.routing import APIRouter

from literature_parser_backend.web.api import literature, monitoring, task, upload

api_router = APIRouter()
api_router.include_router(monitoring.router)
api_router.include_router(literature.router)
api_router.include_router(task.router)
api_router.include_router(upload.router)

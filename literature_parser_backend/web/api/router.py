from fastapi.routing import APIRouter

from literature_parser_backend.web.api import graphs, literatures, monitoring, resolve, tasks, upload

api_router = APIRouter()
api_router.include_router(monitoring.router)
# ========== 0.2 API Endpoints ==========
api_router.include_router(resolve.router)      # POST /api/resolve - Unified resolution
api_router.include_router(literatures.router)  # GET /api/literatures - Literature retrieval
api_router.include_router(tasks.router)        # GET /api/tasks - Task tracking
api_router.include_router(graphs.router)       # GET /api/graphs - Relationship graphs
# ========== Other Endpoints ==========
api_router.include_router(upload.router)

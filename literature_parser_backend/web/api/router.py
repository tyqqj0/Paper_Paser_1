from fastapi.routing import APIRouter

from literature_parser_backend.web.api import graphs, literature, literatures, monitoring, resolve, task, tasks, upload

api_router = APIRouter()
api_router.include_router(monitoring.router)
# ========== New 0.2 API Endpoints ==========
api_router.include_router(resolve.router)      # POST /api/resolve - Unified resolution
api_router.include_router(literatures.router)  # GET /api/literatures - Literature retrieval
api_router.include_router(tasks.router)        # GET /api/tasks - Task tracking (plural)
api_router.include_router(graphs.router)       # GET /api/graphs - Relationship graphs
# ========== Legacy 0.1 API Endpoints ==========
api_router.include_router(literature.router)  # POST /api/literature - Legacy processing
api_router.include_router(task.router)        # GET /api/task - Legacy task management
api_router.include_router(upload.router)

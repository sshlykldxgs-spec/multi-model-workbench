"""API 路由。契约见 docs/api-contract.md。"""

from fastapi import APIRouter

from app.api.v1 import auth, conversations, health, models, runs

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(models.router, tags=["models"])
api_router.include_router(conversations.router, tags=["conversations"])
api_router.include_router(runs.router, tags=["runs"])

__all__ = ["api_router"]

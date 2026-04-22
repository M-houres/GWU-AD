from fastapi import APIRouter

from app.api import admin, auth, billing, partners, tasks, users

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(partners.router, prefix="/partners", tags=["partners"])

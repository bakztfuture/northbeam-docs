"""Every API router, collected under one parent. A new area adds one include_router line here."""

from fastapi import APIRouter

from app.routes import admin, health, public

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(admin.router, prefix="/admin")
api_router.include_router(public.router, prefix="/public")

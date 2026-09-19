# app/api/main_router.py
from fastapi import APIRouter

from app.api.routes.auth import auth_routes, sso_roles_routes
from app.api.routes.health import health_routes
from app.api.routes.media import admin_media_routes, media_routes
from app.api.routes.project import admin_project_routes, project_routes, status_routes
from app.api.routes.portfolio_bridge import portfolio_routes
from app.api.routes.skill import admin_skill_routes, skill_routes
from app.api.routes.apps import router as apps_router
from app.api.routes.advance_scraper import router as advance_scraper_router

main_router = APIRouter(prefix="/api/allprojects")

# Public
main_router.include_router(health_routes.router)
main_router.include_router(auth_routes.router)
main_router.include_router(media_routes.router)
main_router.include_router(status_routes.public_router)
main_router.include_router(skill_routes.router)
main_router.include_router(project_routes.router)
main_router.include_router(portfolio_routes.router)
main_router.include_router(apps_router)

# Live apps (project status + roles gated)
main_router.include_router(advance_scraper_router)

# Admin (owner + super_admin)
main_router.include_router(sso_roles_routes.router)
main_router.include_router(status_routes.admin_router)
main_router.include_router(admin_media_routes.router)
main_router.include_router(admin_project_routes.router)
main_router.include_router(admin_skill_routes.router)

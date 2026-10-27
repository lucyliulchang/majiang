"""聚合 HTTP 路由，统一挂在 /api 下。"""

from fastapi import APIRouter

from main.api import auth, history, rooms, rules, users

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(rules.router)
api_router.include_router(rooms.router)
api_router.include_router(history.router)

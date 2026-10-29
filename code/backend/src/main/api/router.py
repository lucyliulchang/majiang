"""聚合 HTTP 路由，统一挂在 /api 下。"""

from fastapi import APIRouter

from main.api import auth, families, history, rooms, rules, skins, user

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(families.router)
api_router.include_router(user.router)
# 规则族在 /api/rule-families，模板在 /api/rules（04 §5）
api_router.include_router(rules.family_router)
api_router.include_router(rules.router)
api_router.include_router(rooms.router)
api_router.include_router(history.router)
# 皮肤在 /api/skins（04 §8）
api_router.include_router(skins.router)

"""FastAPI 应用装配。"""

import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from common.loggingCommon import get_logger, setup_logging
from common.securityCommon import hash_password
from config.basicSettings import PUBLIC_IMAGE_URL, VERSION
from config.localSettings import FRONTEND_DIST, settings
from db.base import SessionLocal, init_db
from db.models import Game, User
from main import ws as ws_api
from main.api.router import api_router
from tools.seedPresets import install_presets

logger = get_logger("mahjong.main")


def close_stale_games() -> None:
    """把库里遗留的"进行中"场次标记为中断。

    房态只在内存，进程重启后这些场次永远不会有人继续打；不处理的话战绩页会长期
    挂着一串"进行中"的僵尸场次。已结算的每局结果都在 game_rounds 里，积分不受影响。
    """
    with SessionLocal() as session:
        stale = session.scalars(select(Game).where(Game.status == "playing")).all()
        if not stale:
            return
        now = datetime.now(timezone.utc)
        for game in stale:
            game.status = "aborted"
            game.ended_at = now
        session.commit()
        logger.info("已把 %d 场遗留的进行中对局标记为中断", len(stale))


def bootstrap() -> None:
    """建表、写预置规则、清理遗留对局、确保有一个管理员账号。"""
    init_db()
    close_stale_games()
    with SessionLocal() as session:
        install_presets(session)
        admin = session.scalar(select(User).where(User.role == "admin"))
        if admin is not None:
            return
        password = settings.admin_init_password or secrets.token_urlsafe(9)
        user = User(
            username=settings.admin_init_username.strip().lower() or "admin",
            display_name="管理员",
            password_hash=hash_password(password),
            role="admin",
            color="#C9A063",
        )
        session.add(user)
        session.commit()
        if not settings.admin_init_password:
            logger.warning(
                "已创建管理员账号 %s，随机初始密码：%s（请登录后立刻修改）",
                user.username,
                password,
            )
        else:
            logger.info("已创建管理员账号 %s", user.username)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.ensure_dirs()
    setup_logging()
    bootstrap()
    logger.info("家庭麻将后端已启动，版本 %s", VERSION)
    yield
    logger.info("家庭麻将后端已停止")


app = FastAPI(title="家庭麻将", version=VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(ws_api.router)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "version": VERSION}


# 前端直访的图片（牌面皮肤等）：本地由本服务托管，生产由 Nginx 从
# /data/webserver/majiangapp 出，两处 URL 前缀一致。
settings.ensure_dirs()
app.mount(
    PUBLIC_IMAGE_URL,
    StaticFiles(directory=settings.public_dir),
    name="public-images",
)

# 前端产物 code/frontend/dist（本地开发才有；生产由 Nginx 托管，
# 目录不存在则跳过挂载，API 不受影响）
dist_dir = FRONTEND_DIST
if dist_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=dist_dir / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        # 未匹配的 /api 路径必须返回 JSON 404，不能落进 SPA 的 index.html，
        # 否则前端会把 HTML 当 JSON 解析，报出与真实原因无关的错。
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="接口不存在")
        target = dist_dir / full_path
        if full_path and target.is_file():
            return FileResponse(target)
        return FileResponse(dist_dir / "index.html")

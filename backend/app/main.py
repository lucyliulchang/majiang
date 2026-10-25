"""FastAPI 应用装配。"""

import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.api import ws as ws_api
from app.api.router import api_router
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.core.security import hash_password
from app.db.base import SessionLocal, init_db
from app.db.models import Game, User
from app.seeds.presets import install_presets

logger = get_logger("mahjong.main")

VERSION = "1.0.0"


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


dist_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
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

"""FastAPI 应用装配。"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from common import mysqlCommon
from common.bizCommon import BizError
from common.loggingCommon import get_logger, setup_logging
from common.mysqlHandle import DBUnavailableError
from config.basicSettings import PUBLIC_IMAGE_URL, VERSION
from config.localSettings import FRONTEND_DIST, settings
from main import ws as ws_api
from main.api.router import api_router
from processor import accountService
from tools.seedPresets import installPresets

logger = get_logger("mahjong.main")


def close_stale_games() -> int:
    """把库里遗留的「进行中」场次标记为 ABORTED（进程重启后无人能续局）。

    房态只在内存，重启后这些场次永远不会有人继续打；不处理的话战绩页会长期
    挂着一串「进行中」的僵尸场次。已结算的每局结果都在 mj_game_round 里，积分不受影响。
    一条 UPDATE 完成，返回受影响行数。
    """
    affected = mysqlCommon.update_mj_game_abort_playing()
    if affected > 0:
        logger.info("已把 %d 场遗留的进行中对局标记为 ABORTED", affected)
    return affected


def bootstrap() -> None:
    """写预置规则（幂等）+ 清理遗留对局。

    建表由 `tools/initTables.py` 负责（02 §6.3），启动期不再做 ORM 自动建表：
    账号由 contentHub 账号服务管理，本库只镜像 USER_BASIC。
    数据库不可用时不阻断启动（请求层统一 503 DB_UNAVAILABLE），只记错误日志。
    """
    try:
        counts = installPresets()
        logger.info("预置数据就绪：%s", counts)
        close_stale_games()
    except (DBUnavailableError, RuntimeError) as error:
        logger.error("启动期数据库不可用，跳过预置数据与遗留场次清理：%s", error)


def check_account_service() -> None:
    """启动探活：账号服务可达性只打印结果，**不阻塞启动**（01 §5.5、docs/部署.md §4）。"""
    try:
        ok, detail = accountService.checkService()
    except Exception as error:  # noqa: BLE001 探活本身不能拖死启动
        ok, detail = False, str(error)

    if ok:
        logger.info(
            "账号服务可达 %s（%s）", settings.account_service_url, detail
        )
    else:
        logger.warning(
            "账号服务不可达 %s（%s）：登录/注册/找回口令将返回 503，服务继续启动",
            settings.account_service_url,
            detail,
        )
    logger.info(
        "账号开关：注册=%s 找回口令=%s 默认角色=%s",
        settings.account_register_enabled,
        settings.account_password_reset_enabled,
        settings.account_default_role,
    )


_background_tasks: set[asyncio.Task] = set()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.ensure_dirs()
    setup_logging()
    bootstrap()

    # 探活放后台：账号服务不可达/超时都不拖慢启动，只留一条结论日志
    task = asyncio.create_task(asyncio.to_thread(check_account_service))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    logger.info("家庭麻将后端已启动，版本 %s", VERSION)
    yield
    logger.info("家庭麻将后端已停止")


app = FastAPI(title="家庭麻将", version=VERSION, lifespan=lifespan)


@app.exception_handler(BizError)
async def biz_error_handler(_: Request, exc: BizError) -> JSONResponse:
    """业务异常统一输出 04 §1 的错误体：{"detail": 中文提示, "code": ERROR_CODE}。

    AccountServiceError / FamilyServiceError 都是 BizError 的子类，一个 handler 覆盖。
    """
    return JSONResponse(
        status_code=exc.httpStatus,
        content={"detail": exc.message, "code": exc.code},
    )


@app.exception_handler(DBUnavailableError)
async def db_unavailable_handler(_: Request, exc: DBUnavailableError) -> JSONResponse:
    """数据层不可用：不把驱动异常原样抛给前端（01 §4.1）。"""
    logger.error("数据库不可用：%s", exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "数据服务暂时不可用，请稍后再试", "code": "DB_UNAVAILABLE"},
    )

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
# /data/webserver/majiangapp 出，两处 URL 前缀一致（01 §10）。
# 目录 = settings.public_dir（data/webserver/majiangapp；生产由 UPLOAD_DIR 指到
# /data/webserver/majiangapp），启动时不存在则自动创建——上传接口不能因缺目录 500。
settings.ensure_dirs()


class CachedStaticFiles(StaticFiles):
    """皮肤/前端静态文件：文件名含内容哈希，可长缓存（05 §6.3）。

    `index.html` 例外：它是唯一不带哈希的入口，必须每次回源，否则前端发版后
    用户会长期拿到旧的 build 引用。
    """

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        fullPath = str(args[0]) if args else str(kwargs.get("full_path") or "")
        if fullPath.rsplit("/", 1)[-1] == "index.html":
            response.headers.setdefault("Cache-Control", "no-cache")
        else:
            response.headers.setdefault(
                "Cache-Control", "public, max-age=31536000, immutable"
            )
        return response


app.mount(
    PUBLIC_IMAGE_URL,
    CachedStaticFiles(directory=settings.public_dir),
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
        # 入口 HTML 不带哈希：no-cache，避免发版后仍用旧产物
        return FileResponse(dist_dir / "index.html", headers={"Cache-Control": "no-cache"})

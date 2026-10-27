"""基础设置：版本号、默认常量、环境变量读取。

与 `config/localSettings.py` 的分工：
  本文件 —— 与部署环境无关的东西：VERSION、URL 前缀、默认值、.env 读取；
  localSettings.py —— 按 APP_ENV 选择环境、推导运行期路径、对外暴露 `settings`。

目录纪律（勿改，运维与 .gitignore 均按此约定）：

    code/backend/src/   —— 只放代码，不产生任何运行时产物
    code/backend/log/   —— 所有日志（应用日志 + cron 脚本日志）
    code/backend/data/  —— 所有附属数据（数据库、备份、静态图片）
    code/backend/data/webserver/majiangapp/ —— 前端可直接访问的图片，
        生产环境对应 /data/webserver/majiangapp，两条路径下的 URL 保持一致。
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

VERSION = "1.0.0"

# basicSettings.py -> config -> src -> backend，即 code/backend
BACKEND_DIR = Path(__file__).resolve().parents[2]
# code
CODE_DIR = BACKEND_DIR.parent

# 运行期目录默认值：按 __file__ 推算，不随进程 cwd 漂移
DEFAULT_LOG_DIR = BACKEND_DIR / "log"
DEFAULT_DATA_DIR = BACKEND_DIR / "data"

# 前端直访静态图片的 URL 前缀：本地由本服务挂载，生产由 Nginx 从
# /data/webserver/majiangapp 出，前端只认这一个前缀。
PUBLIC_IMAGE_URL = "/majiangapp"

DEFAULT_SECRET_KEY = "dev-only-insecure-key-change-me"
DEFAULT_ADMIN_USERNAME = "admin"
# 留空则启动时随机生成口令并打印一次日志
DEFAULT_ADMIN_PASSWORD = ""
DEFAULT_TOKEN_TTL_HOURS = 720
DEFAULT_CORS_ORIGINS = "*"
DEFAULT_SECURE_COOKIES = False

# 出牌超时与碰杠胡询问窗口的兜底值，实际以规则模板为准
DEFAULT_CLAIM_WINDOW_SECONDS = 8
# 断线后保留座位时长
DEFAULT_SEAT_RESERVE_SECONDS = 180
# 聊天限流：每人每 N 秒最多 M 条
DEFAULT_CHAT_RATE_WINDOW = 5
DEFAULT_CHAT_RATE_LIMIT = 3

# 皮肤图片上传限制（S8 落地时使用，此处只定常量）
UPLOAD_MAX_BYTES = 2 * 1024 * 1024
UPLOAD_ALLOWED_SUFFIXES = (".png", ".webp", ".jpg", ".jpeg")


def default_sqlite_url(data_dir: Path = DEFAULT_DATA_DIR) -> str:
    """开发用 SQLite 的绝对路径连接串，库文件落在 data/db，不散落在代码目录。"""
    return f"sqlite:///{(data_dir / 'db' / 'mahjong.db').as_posix()}"


class BasicSettings(BaseSettings):
    """全部来自环境变量或 .env 文件。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    secret_key: str = DEFAULT_SECRET_KEY
    database_url: str = default_sqlite_url()

    # 运行时目录：允许用 LOG_DIR / DATA_DIR 覆盖（生产可指到独立挂载盘）
    log_dir: Path = DEFAULT_LOG_DIR
    data_dir: Path = DEFAULT_DATA_DIR

    admin_init_username: str = DEFAULT_ADMIN_USERNAME
    admin_init_password: str = DEFAULT_ADMIN_PASSWORD

    token_ttl_hours: int = DEFAULT_TOKEN_TTL_HOURS
    cors_origins: str = DEFAULT_CORS_ORIGINS
    secure_cookies: bool = DEFAULT_SECURE_COOKIES

    claim_window_seconds: int = DEFAULT_CLAIM_WINDOW_SECONDS
    seat_reserve_seconds: int = DEFAULT_SEAT_RESERVE_SECONDS
    chat_rate_window: int = DEFAULT_CHAT_RATE_WINDOW
    chat_rate_limit: int = DEFAULT_CHAT_RATE_LIMIT

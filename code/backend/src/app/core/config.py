"""应用配置：全部来自环境变量或 .env 文件。

目录纪律（勿改，运维与 .gitignore 均按此约定）：

    code/backend/src/   —— 只放代码，不产生任何运行时产物
    code/backend/log/   —— 所有日志（应用日志 + cron 脚本日志）
    code/backend/data/  —— 所有附属数据（数据库、备份、静态图片）
    code/backend/data/webserver/majiangapp/ —— 前端可直接访问的图片，
        生产环境对应 /data/webserver/majiangapp，两条路径下的 URL 保持一致。
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py -> core -> app -> src -> backend，即 code/backend
BACKEND_DIR = Path(__file__).resolve().parents[3]
CODE_DIR = BACKEND_DIR.parent
FRONTEND_DIST = CODE_DIR / "frontend" / "dist"

# 前端直访静态图片的 URL 前缀：本地由本服务挂载，生产由 Nginx 从
# /data/webserver/majiangapp 出，前端只认这一个前缀。
PUBLIC_IMAGE_URL = "/majiangapp"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    secret_key: str = "dev-only-insecure-key-change-me"
    # 库文件落在 data/db，运行目录里不再散落 .db
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'db' / 'mahjong.db').as_posix()}"

    # 运行时目录：允许用 LOG_DIR / DATA_DIR 覆盖（生产可指到独立挂载盘）
    log_dir: Path = BACKEND_DIR / "log"
    data_dir: Path = BACKEND_DIR / "data"

    admin_init_username: str = "admin"
    admin_init_password: str = ""

    token_ttl_hours: int = 720
    cors_origins: str = "*"
    secure_cookies: bool = False

    # 出牌超时与碰杠胡询问窗口的兜底值，实际以规则模板为准
    claim_window_seconds: int = 8
    # 断线后保留座位时长
    seat_reserve_seconds: int = 180
    # 聊天限流：每人每 N 秒最多 M 条
    chat_rate_window: int = 5
    chat_rate_limit: int = 3

    @property
    def cors_origin_list(self) -> list[str]:
        raw = (self.cors_origins or "*").strip()
        if raw == "*":
            return ["*"]
        return [item.strip() for item in raw.split(",") if item.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def public_dir(self) -> Path:
        """前端可直接访问的图片根目录（生产 /data/webserver/majiangapp）。"""
        return self.data_dir / "webserver" / "majiangapp"

    def ensure_dirs(self) -> None:
        """启动时保证 log/ 与 data/ 的骨架存在，缺目录不能让服务起不来。"""
        for path in (
            self.log_dir,
            self.log_dir / "schedule",
            self.data_dir,
            self.data_dir / "db",
            self.data_dir / "backup",
            self.public_dir,
            self.public_dir / "tiles",
        ):
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError:
                continue


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

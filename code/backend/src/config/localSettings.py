"""本地环境设置：按 APP_ENV 选择环境、推导运行期路径，并对外暴露 `settings`。

环境（APP_ENV，默认 local）：
    local        —— 本机开发：SQLite 落在 code/backend/data/db，日志落 code/backend/log
    test_server  —— 测试服：目录同构，库与口令差异全部由 .env 给出
    server_01    —— 生产：目录由部署位置决定（code/backend 对应 /data/majiang）

职责边界：
    本文件只做「环境选择 + 派生路径 + 只读属性」；
    常量与默认值、.env 字段读取在 `config/basicSettings.py`。
"""

import os
from functools import lru_cache
from pathlib import Path

from config.basicSettings import CODE_DIR, PUBLIC_IMAGE_URL, BasicSettings

# 未设置 APP_ENV 时按本机开发处理，行为与迁移前一致
DEFAULT_APP_ENV = "local"
APP_ENV = (os.getenv("APP_ENV") or DEFAULT_APP_ENV).strip().lower()

# 环境映射：只放「必须按环境区分、又不适合写进 .env」的项。
# 同名环境变量优先级更高（见 _preset_values），因此这里不写任何口令与地址。
ENV_PRESETS: dict[str, dict[str, object]] = {
    "local": {"secure_cookies": False},
    "test_server": {"secure_cookies": False},
    "server_01": {"secure_cookies": True},
}

# 前端构建产物：config -> src -> backend -> code，即 code/frontend/dist。
# 仅本地开发时由后端托管；生产由 Nginx 平铺到 /data/webserver/majiangapp。
FRONTEND_DIST = CODE_DIR / "frontend" / "dist"


class Settings(BasicSettings):
    """基础设置 + 环境名 + 派生路径（派生项都是只读属性，不重复读环境变量）。"""

    app_env: str = APP_ENV

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
        """前端可直接访问的图片根目录（生产 /data/webserver/majiangapp）。

        优先 UPLOAD_DIR：生产站点树与前端的 Nginx root 必须重合，否则
        `/majiangapp/tiles/...` 会落到 /data/majiang/data 下面而 404（docs/部署.md §5.2）。
        """
        raw = (self.upload_dir or "").strip()
        if raw:
            path = Path(raw)
            return path if path.is_absolute() else (DEFAULT_DATA_DIR.parent / path)
        return self.data_dir / "webserver" / "majiangapp"

    @property
    def tiles_dir(self) -> Path:
        """皮肤资源根：`{public_dir}/tiles/{skinCode}/{tileKey}.{hash8}.{ext}`。"""
        return self.public_dir / "tiles"

    @property
    def frontend_dist(self) -> Path:
        """前端产物目录，目录不存在时调用方跳过静态挂载。"""
        return FRONTEND_DIST

    def ensure_dirs(self) -> None:
        """启动时保证 log/ 与 data/ 的骨架存在，缺目录不能让服务起不来。"""
        for path in (
            self.log_dir,
            self.log_dir / "schedule",
            self.data_dir,
            self.data_dir / "db",
            self.data_dir / "backup",
            self.public_dir,
            self.tiles_dir,
        ):
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError:
                continue


def _preset_values() -> dict[str, object]:
    """取当前环境映射，环境变量优先——.env 永远压过这里的默认值。"""
    preset = ENV_PRESETS.get(APP_ENV, {})
    return {key: value for key, value in preset.items() if key.upper() not in os.environ}


@lru_cache
def get_settings() -> Settings:
    return Settings(**_preset_values())


settings = get_settings()

__all__ = [
    "APP_ENV",
    "ENV_PRESETS",
    "FRONTEND_DIST",
    "PUBLIC_IMAGE_URL",
    "Settings",
    "get_settings",
    "settings",
]

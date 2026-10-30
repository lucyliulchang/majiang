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

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

VERSION = "1.1.0"

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

DEFAULT_SECRET_KEY = "dev-only-insecure-key-change-me-32bytes"
DEFAULT_TOKEN_TTL_HOURS = 720
DEFAULT_CORS_ORIGINS = "*"
DEFAULT_SECURE_COOKIES = False

# 账号服务（contentHub acis）——账号不是本系统资产，只做客户端与档案镜像（01 §5）
DEFAULT_ACCOUNT_SERVICE_URL = "http://127.0.0.1:8160/acis"
# 注册默认关闭（生产口径）；开放时账号服务仍会校验短信验证码
DEFAULT_ACCOUNT_ALLOW_REGISTER = False
# 自助找回口令默认开启（家庭场景需要）
DEFAULT_ACCOUNT_ALLOW_PASSWORD_RESET = True
# 本系统角色：admin / member。未返回或不在管理员白名单时回落到这里
DEFAULT_ACCOUNT_DEFAULT_ROLE = "member"

# acis 管理员角色白名单（与 contentHub config/basicSettings.py::USER_ADMIN_ROLE_LIST 一致）
USER_ADMIN_ROLE_LIST = ("administrator", "manager")
# 本系统角色 -> acis roleName（回写 acis 时用，对应 contentHub ::ROLE_ACCOUNT_ROLE）
ROLE_ACCOUNT_ROLE = {"admin": "administrator", "member": "customer"}

# 验证码本地限流（进程内计数，不落库、不缓存明文；见 04 §2.3）
DEFAULT_AUTH_VERIFY_CODE_COOLDOWN_SECONDS = 60
DEFAULT_AUTH_VERIFY_CODE_MAX_ATTEMPTS = 5
# 账号服务侧验证码 TTL（仅用于前端文案，本地不判断）
AUTH_VERIFY_CODE_EXPIRE_SECONDS = 600

# 出牌超时与碰杠胡询问窗口的兜底值，实际以规则模板为准
DEFAULT_CLAIM_WINDOW_SECONDS = 8
# 断线后保留座位时长
DEFAULT_SEAT_RESERVE_SECONDS = 180
# 聊天限流：每人每 N 秒最多 M 条
DEFAULT_CHAT_RATE_WINDOW = 5
DEFAULT_CHAT_RATE_LIMIT = 3

# 观战（S5b / 00 §4.3 G13、8 §9 D17）：一人一目标、每名在座玩家最多 10 人围观、
# 全房 4×10=40 个名额；观战连接全断后绑定保留 60 秒，超时释放名额。
DEFAULT_SPECTATE_LIMIT_PER_SEAT = 10
DEFAULT_SPECTATE_ROOM_MAX = 40
DEFAULT_SPECTATE_RESERVE_SECONDS = 60


def intInRange(value, low: int, high: int, defaultValue: int) -> int:
    """把 .env 里的值收敛到合法区间；非法/缺失一律回退默认，启动不因此失败。"""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return defaultValue
    if number < low or number > high:
        return defaultValue
    return number

# 皮肤图片上传限制（S8）：单文件 ≤512 KB、单皮肤 ≤8 MB、只认 png/webp，拒绝 svg（01 §10）
UPLOAD_MAX_BYTES = 512 * 1024
UPLOAD_MAX_SKIN_BYTES = 8 * 1024 * 1024
UPLOAD_ALLOWED_SUFFIXES = (".png", ".webp")


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

    # 前端直访的图片站点根（01 §10、11）：
    #   本地缺省 code/backend/data/webserver/majiangapp；
    #   生产必须显式 UPLOAD_DIR=/data/webserver/majiangapp，与 Nginx 的站点根对齐。
    upload_dir: str = ""
    max_upload_bytes: int = UPLOAD_MAX_BYTES

    # 皮肤功能开关（06 §8.3 回滚：SKIN_ENABLED=false → 清单为空、写操作 403，
    # 前端整桌回退 css-classic，不需要发版）
    skin_enabled: bool = True

    token_ttl_hours: int = DEFAULT_TOKEN_TTL_HOURS
    cors_origins: str = DEFAULT_CORS_ORIGINS
    secure_cookies: bool = DEFAULT_SECURE_COOKIES

    # 账号服务与两个开关（01 §11）
    account_service_url: str = DEFAULT_ACCOUNT_SERVICE_URL
    account_allow_register: bool = DEFAULT_ACCOUNT_ALLOW_REGISTER
    account_allow_password_reset: bool = DEFAULT_ACCOUNT_ALLOW_PASSWORD_RESET
    account_default_role: str = DEFAULT_ACCOUNT_DEFAULT_ROLE
    auth_verify_code_cooldown_seconds: int = DEFAULT_AUTH_VERIFY_CODE_COOLDOWN_SECONDS
    auth_verify_code_max_attempts: int = DEFAULT_AUTH_VERIFY_CODE_MAX_ATTEMPTS

    claim_window_seconds: int = DEFAULT_CLAIM_WINDOW_SECONDS
    seat_reserve_seconds: int = DEFAULT_SEAT_RESERVE_SECONDS
    chat_rate_window: int = DEFAULT_CHAT_RATE_WINDOW
    chat_rate_limit: int = DEFAULT_CHAT_RATE_LIMIT

    # 观战上限（S5b）：每名在座玩家最多 10 人、全房 40 个名额、断线保留 60 秒
    spectate_limit_per_seat: int = DEFAULT_SPECTATE_LIMIT_PER_SEAT
    spectate_room_max: int = DEFAULT_SPECTATE_ROOM_MAX
    spectate_reserve_seconds: int = DEFAULT_SPECTATE_RESERVE_SECONDS

    @field_validator(
        "spectate_limit_per_seat", "spectate_room_max", "spectate_reserve_seconds", mode="before"
    )
    @classmethod
    def _spectateFallback(cls, value, info):
        ranges = {
            "spectate_limit_per_seat": (1, 10, DEFAULT_SPECTATE_LIMIT_PER_SEAT),
            "spectate_room_max": (1, 100, DEFAULT_SPECTATE_ROOM_MAX),
            "spectate_reserve_seconds": (0, 3600, DEFAULT_SPECTATE_RESERVE_SECONDS),
        }
        low, high, defaultValue = ranges.get(info.field_name, (0, 0, 0))
        if value is None or value == "":
            return defaultValue
        return intInRange(value, low, high, defaultValue)

    @property
    def account_register_enabled(self) -> bool:
        return bool(self.account_allow_register)

    @property
    def account_password_reset_enabled(self) -> bool:
        return bool(self.account_allow_password_reset)

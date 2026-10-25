"""应用配置：全部来自环境变量或 .env 文件。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    secret_key: str = "dev-only-insecure-key-change-me"
    database_url: str = "sqlite:///./mahjong.db"

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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

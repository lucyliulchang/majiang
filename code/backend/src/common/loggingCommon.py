"""统一日志格式。纪律：绝不记录密码、JWT 明文、任何玩家的手牌明文。

落地位置统一在 `code/backend/log/`（可用 LOG_DIR 覆盖）：
  log/mahjong.log    应用日志，10MB × 5 滚动
  log/schedule/*.log cron 脚本日志，由 crontab 重定向产生
"""

import logging
import sys
from logging.handlers import RotatingFileHandler

from config.localSettings import settings

_FORMAT = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"
_LOG_FILE_NAME = "mahjong.log"
_MAX_BYTES = 10 * 1024 * 1024
_BACKUP_COUNT = 5

_CONFIGURED = False


def _file_handler(formatter: logging.Formatter) -> logging.Handler | None:
    try:
        settings.log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            settings.log_dir / _LOG_FILE_NAME,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
    except OSError:
        # 目录只读等异常不能拖死启动；退回 stdout，由 systemd/journald 兜底
        return None
    handler.setFormatter(formatter)
    return handler


def setup_logging(level: int = logging.INFO) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    formatter = logging.Formatter(fmt=_FORMAT, datefmt=_DATEFMT)

    streamHandler = logging.StreamHandler(sys.stdout)
    streamHandler.setFormatter(formatter)

    handlers: list[logging.Handler] = [streamHandler]
    fileHandler = _file_handler(formatter)
    if fileHandler is not None:
        handlers.append(fileHandler)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = handlers
    # 降低噪音：uvicorn 的 access log 由 Nginx 侧记录
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

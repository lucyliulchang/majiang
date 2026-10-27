"""MySQL 连接配置：读写主机、库名、账号与连接池大小。

分工（与 01 §8、§11 对齐）：
  本文件      —— 环境名 → 默认值映射、.env / 环境变量读取、构造连接池句柄 dbW/dbR；
  common/mysqlHandle.py —— 连接池与游标管理，不含任何地址与口令。

约束：
  1. 口令只从环境变量（或本地 .env）读取，代码、文档、日志里不出现真实值；
  2. 未设置口令时为空串，连接失败由 mysqlHandle 报 DB_UNAVAILABLE，不在导入期抛；
  3. `MYSQL_SKIP_CONNECT=1` 时导入本模块不建连（dbW/dbR 为 None），
     供无库环境（静态检查、CI、仅调用下游服务）安全导入；
  4. 环境名取自 config/localSettings.APP_ENV，与 APP_ENV 联动；
     同一环境变量优先于本文件的默认值（部署时只改 .env / 环境变量）。
"""

import os
from pathlib import Path

from config.localSettings import APP_ENV

_SRC_DIR = Path(__file__).resolve().parents[1]
_ENV_FILE = _SRC_DIR / ".env"

# 环境映射：只放「按环境不同、又适合有默认值」的项；口令一律空，由 .env 注入。
ENV_DEFAULT_MAP: dict[str, dict[str, object]] = {
    "local": {"host": "127.0.0.1", "port": 3306, "db": "mahjong_data", "user": "mjapp"},
    "test_server": {"host": "127.0.0.1", "port": 3306, "db": "mahjong_test", "user": "mjapp"},
    "server_01": {"host": "127.0.0.1", "port": 3306, "db": "mahjong_data", "user": "mjapp"},
}

ENV_NAME = APP_ENV
_PRESET = ENV_DEFAULT_MAP.get(APP_ENV, ENV_DEFAULT_MAP["local"])

# 连接池上限的合法区间（01 §8：默认 10，可配 5–20）
POOL_MAX_MIN = 5
POOL_MAX_MAX = 20
POOL_MAX_DEFAULT = 10


def _loadEnvFile(envPath: Path = _ENV_FILE) -> None:
    """把 .env 灌入 os.environ（不覆盖已有环境变量）。

    优先用 python-dotenv（pydantic-settings 的依赖）；缺失时用最小解析，
    避免在精简环境里因为一个可选依赖导致整条数据链路不可用。
    """
    if not envPath.is_file():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(envPath, override=False)
        return
    except Exception:
        pass

    try:
        for rawLine in envPath.read_text(encoding="utf-8").splitlines():
            line = rawLine.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        return


_loadEnvFile()


def _getText(key: str, default: object) -> str:
    value = os.getenv(key)
    if value is None or value.strip() == "":
        return str(default)
    return value.strip()


def _getInt(key: str, default: object, minValue: int = 0, maxValue: int = 0) -> int:
    try:
        value = int(_getText(key, default))
    except (TypeError, ValueError):
        value = int(str(default))
    if maxValue > 0:
        value = max(minValue, min(value, maxValue))
    return value


# 写库（主）
MYSQL_WRITE_HOST = _getText("MYSQL_WRITE_HOST", _PRESET["host"])
MYSQL_WRITE_PORT = _getInt("MYSQL_WRITE_PORT", _PRESET["port"])
MYSQL_WRITE_DB = _getText("MYSQL_WRITE_DB", _PRESET["db"])
MYSQL_WRITE_USER = _getText("MYSQL_WRITE_USER", _PRESET["user"])
MYSQL_WRITE_PASSWD = _getText("MYSQL_WRITE_PASSWD", "")

# 读库（从；默认与主库同实例）
MYSQL_READ_HOST = _getText("MYSQL_READ_HOST", MYSQL_WRITE_HOST)
MYSQL_READ_PORT = _getInt("MYSQL_READ_PORT", MYSQL_WRITE_PORT)
MYSQL_READ_DB = _getText("MYSQL_READ_DB", MYSQL_WRITE_DB)
MYSQL_READ_USER = _getText("MYSQL_READ_USER", MYSQL_WRITE_USER)
MYSQL_READ_PASSWD = _getText("MYSQL_READ_PASSWD", MYSQL_WRITE_PASSWD)

MYSQL_POOL_MAX = _getInt(
    "MYSQL_POOL_MAX", POOL_MAX_DEFAULT, POOL_MAX_MIN, POOL_MAX_MAX
)

MYSQL_DATABASE_NAME = MYSQL_WRITE_DB

# 是否跳过建立数据库连接（见模块头约束 3）
MYSQL_SKIP_CONNECT = os.getenv("MYSQL_SKIP_CONNECT", "").strip().lower() in (
    "1",
    "true",
    "yes",
    "y",
    "on",
)

dbW = None
dbR = None

if not MYSQL_SKIP_CONNECT:
    from common import mysqlHandle as mysqlHandle

    dbW = mysqlHandle.getMysqlHandle(
        host=MYSQL_WRITE_HOST,
        port=MYSQL_WRITE_PORT,
        user=MYSQL_WRITE_USER,
        passwd=MYSQL_WRITE_PASSWD,
        db=MYSQL_WRITE_DB,
        maxConnections=MYSQL_POOL_MAX,
    )
    dbR = mysqlHandle.getMysqlHandle(
        host=MYSQL_READ_HOST,
        port=MYSQL_READ_PORT,
        user=MYSQL_READ_USER,
        passwd=MYSQL_READ_PASSWD,
        db=MYSQL_READ_DB,
        maxConnections=MYSQL_POOL_MAX,
    )


def pingServer() -> bool:
    """连通性探测：给建表/运维脚本在动手前先判一次，避免一条条报错刷屏。"""
    if dbW is None:
        return False
    try:
        dbW.executeRead("SELECT 1 AS ok")
        return True
    except Exception:
        return False


def describe() -> dict[str, object]:
    """供启动日志与建表脚本打印：只含环境/地址/库/池大小，绝不含口令。"""
    return {
        "env": ENV_NAME,
        "writeHost": MYSQL_WRITE_HOST,
        "writePort": MYSQL_WRITE_PORT,
        "writeDB": MYSQL_WRITE_DB,
        "readHost": MYSQL_READ_HOST,
        "readPort": MYSQL_READ_PORT,
        "readDB": MYSQL_READ_DB,
        "poolMax": MYSQL_POOL_MAX,
        "skipConnect": MYSQL_SKIP_CONNECT,
    }


if __name__ == "__main__":
    for key, value in describe().items():
        print(f"{key}: {value}")

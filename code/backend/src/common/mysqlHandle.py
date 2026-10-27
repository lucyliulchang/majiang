"""MySQL 连接池与执行句柄（pymysql + DBUtils.PooledDB）。

与 contentHub 的差异（有意为之）：那边是「单条长连接 + 复用游标」，本项目按 01 §8
使用连接池——FastAPI 同步路由跑在 AnyIO 线程池，长连接+共享游标会把线程绑死在一条
连接上，且一次异常就会污染后续请求。

约定：
  1. `maxconnections=MYSQL_POOL_MAX`（默认 10，区间 5–20）、`blocking=True`、`ping=1`；
  2. `autocommit=False`：单条写自动提交，事务内（begin/commit/rollback）显式提交；
  3. 取连接前 ping，失败重连一次；池耗尽或连不上统一抛 DB_UNAVAILABLE；
  4. executeRead/executeWrite 沿用基线的返回值语义：成功返回影响行数，SQL 出错返回 -1
     并记日志（生成代码按 `if result` / `> 0` 判断）；连接层故障不走 -1，直接抛
     DBUnavailableError，避免把「库不可用」误判成「条件不匹配」。
"""

import threading
import time
from contextlib import contextmanager

import pymysql
from dbutils.pooled_db import PooledDB

from common.loggingCommon import get_logger

_logger = get_logger("mahjong.mysql")

# 错误码：业务层据此回 DB_UNAVAILABLE（01 §8.1）
DB_UNAVAILABLE = "DB_UNAVAILABLE"

_DEF_ACQUIRE_TIMEOUT = 5.0
_CONNECT_TIMEOUT = 5
_READ_TIMEOUT = 30
_WRITE_TIMEOUT = 30
_CHARSET = "utf8mb4"


class DBUnavailableError(RuntimeError):
    """数据库不可用：连接池耗尽、连接被拒、握手/认证失败。"""

    code = DB_UNAVAILABLE

    def __init__(self, message: str = DB_UNAVAILABLE):
        super().__init__(f"{DB_UNAVAILABLE}: {message}" if DB_UNAVAILABLE not in message else message)


def getPool(
    host: str,
    port: int,
    user: str,
    passwd: str,
    db: str,
    maxConnections: int = 10,
) -> PooledDB:
    """建连接池。此调用不建物理连接（首次 connection() 才连），导入期不会阻塞。"""
    return PooledDB(
        creator=pymysql,
        maxconnections=maxConnections,
        mincached=0,
        maxcached=maxConnections,
        blocking=True,
        ping=1,
        host=host,
        port=int(port),
        user=user,
        password=passwd,
        database=db,
        charset=_CHARSET,
        autocommit=False,
        connect_timeout=_CONNECT_TIMEOUT,
        read_timeout=_READ_TIMEOUT,
        write_timeout=_WRITE_TIMEOUT,
    )


class mysqlHandle:
    """读写句柄：dbW 走主库，dbR 走从库（未配从库时同主库）。"""

    def __init__(self, dbW: PooledDB, dbR: PooledDB | None = None, maxConnections: int = 10):
        if dbW is None:
            raise ValueError("dbW 不能为空")
        self.dbW = dbW
        self.dbR = dbR if dbR is not None else dbW
        self.maxConnections = maxConnections
        # PooledDB 的 blocking=True 会无限等待；这里用自己的槽位做「有界等待」，
        # 超时即报 DB_UNAVAILABLE，不让请求线程无声挂住。
        self._slots = threading.BoundedSemaphore(maxConnections)
        self._local = threading.local()
        self.lastErrMsg = ""
        self.lastRtnMsg = ""

    # ---------- 内部：取还连接 ----------

    def _txConn(self):
        return getattr(self._local, "txConn", None)

    def _acquire(self, write: bool = True):
        txConn = self._txConn()
        if txConn is not None:
            return txConn, False

        if not self._slots.acquire(timeout=_DEF_ACQUIRE_TIMEOUT):
            raise DBUnavailableError("连接池已耗尽，等待超过 %.0f 秒" % _DEF_ACQUIRE_TIMEOUT)

        pool = self.dbW if write else self.dbR
        lastError: Exception | None = None
        # 首次失败重连一次（01 §8.1 的健康检查口径）
        for _ in range(2):
            conn = None
            try:
                conn = pool.connection()
                conn.ping(reconnect=True)
                return conn, True
            except Exception as e:  # 连接被拒 / 认证失败 / 池满
                lastError = e
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass
                time.sleep(0.05)

        self._slots.release()
        raise DBUnavailableError(str(lastError))

    @contextmanager
    def connection(self, write: bool = True):
        """取连接上下文：事务内复用同一连接，事务外即取即还。"""
        conn, owned = self._acquire(write)
        try:
            yield conn
        finally:
            if owned:
                self._release(conn)

    def _release(self, conn) -> None:
        try:
            conn.close()
        except Exception:
            pass
        finally:
            try:
                self._slots.release()
            except ValueError:
                pass

    # ---------- 读 ----------

    def executeRead(self, sqlstr: str, values=()):
        result = 0
        conn, owned = self._acquire(False)
        cursor = None
        try:
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            if values in ((), [], None):
                result = cursor.execute(sqlstr)
            else:
                result = cursor.execute(sqlstr, values)
            self._local.lastRows = list(cursor.fetchall())
        except DBUnavailableError:
            raise
        except Exception as e:
            result = -1
            self.lastErrMsg = f"executeRead:{e},sql:{sqlstr},{values}"
            _logger.error(self.lastErrMsg)
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            if owned:
                self._release(conn)
        return result

    def fetchAll(self):
        return getattr(self._local, "lastRows", [])

    def fetchOne(self):
        rows = getattr(self._local, "lastRows", [])
        return rows[0] if rows else None

    def fetchMany(self, num: int = 2000):
        rows = getattr(self._local, "lastRows", [])
        return rows[:num]

    # ---------- 写 ----------

    def executeWrite(self, sqlstr: str, values=()):
        result = 0
        conn, owned = self._acquire(True)
        cursor = None
        try:
            cursor = conn.cursor()
            if values in ((), [], None):
                result = cursor.execute(sqlstr)
            else:
                result = cursor.execute(sqlstr, values)
            self._local.lastRowID = cursor.lastrowid
            if owned:
                conn.commit()
        except DBUnavailableError:
            raise
        except Exception as e:
            result = -1
            self.lastErrMsg = f"executeWrite:{e},sql:{sqlstr},{values}"
            _logger.error(self.lastErrMsg)
            if owned:
                try:
                    conn.rollback()
                except Exception:
                    pass
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            if owned:
                self._release(conn)
        return result

    def insertID(self):
        return getattr(self._local, "lastRowID", 0)

    def affectedRows(self):
        return self.insertID()

    # ---------- 事务 ----------

    def begin(self):
        if self._txConn() is not None:
            self._local.txDepth = getattr(self._local, "txDepth", 1) + 1
            return
        conn, owned = self._acquire(True)
        if not owned:  # 理论上不会发生
            return
        conn.begin()
        self._local.txConn = conn
        self._local.txDepth = 1

    def commit(self):
        conn = self._txConn()
        if conn is None:
            return
        depth = getattr(self._local, "txDepth", 1)
        if depth > 1:
            self._local.txDepth = depth - 1
            return
        try:
            conn.commit()
        finally:
            self._local.txConn = None
            self._local.txDepth = 0
            self._release(conn)

    def rollback(self):
        conn = self._txConn()
        if conn is None:
            return
        try:
            conn.rollback()
        finally:
            self._local.txConn = None
            self._local.txDepth = 0
            self._release(conn)

    def inTransaction(self) -> bool:
        return self._txConn() is not None

    # ---------- 生命周期 ----------

    def ping(self) -> bool:
        try:
            conn, owned = self._acquire(False)
            if owned:
                self._release(conn)
            return True
        except Exception:
            return False

    def close(self) -> None:
        for pool in {id(self.dbW): self.dbW, id(self.dbR): self.dbR}.values():
            try:
                pool.close()
            except Exception:
                pass


def getMysqlHandle(
    host: str,
    port: int,
    user: str,
    passwd: str,
    db: str,
    maxConnections: int = 10,
    readHost: str = "",
    readPort: int = 0,
    readUser: str = "",
    readPasswd: str = "",
    readDB: str = "",
) -> mysqlHandle:
    """按写库参数建池；读库参数缺省时复用写库池。"""
    poolW = getPool(host, port, user, passwd, db, maxConnections)
    poolR = poolW
    if readHost and (readHost, readPort, readDB, readUser) != (host, port, db, user):
        poolR = getPool(readHost, readPort, readUser, readPasswd, readDB, maxConnections)
    return mysqlHandle(dbW=poolW, dbR=poolR, maxConnections=maxConnections)

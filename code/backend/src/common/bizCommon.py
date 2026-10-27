"""业务异常基类（01 §4.1）。

约定：
  - processor 层只抛 `BizError` 家族，路由层不做 try/except；
  - `main/app.py` 注册一个 handler，统一转成 04 §1 的错误体
    `{"detail": 中文提示, "code": ERROR_CODE}`；
  - `code` 给前端做分支判断，`detail` 给用户看，二者不得泄露资源是否存在
    （跨家庭统一文案见 01 §6.3-2）。
"""

from __future__ import annotations


class BizError(Exception):
    """可预期的业务失败：HTTP 状态 + 错误码 + 中文提示。"""

    def __init__(self, code: str, message: str, httpStatus: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.httpStatus = httpStatus

    def __str__(self) -> str:  # 日志里只出现码与文案，不含敏感数据
        return f"{self.code}: {self.message}"


__all__ = ["BizError"]

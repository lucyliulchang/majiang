#! /usr/bin/env python3
#encoding: utf-8

#Filename: accountClient.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-10-27
#Description:   contentHub(内容中枢) 账号服务(account service) HTTP 客户端。
#
#移植来源：contentHub code/src/common/accountClient.py（保留 CMD 常量、30s 超时、
#异常收敛、「B0 成功 / CI 下游不可达」口径），并按本项目分层去掉 subfunc 层：
#  低层  accountServiceRequestEx / accountServiceRequest  —— 唯一 HTTP 出口
#  薄层  forward(cmd, dataSet, roleName)                   —— 错误码归一 + 角色回写
#  便捷  getUserInfo / chkUserExist / ping
#
#职责边界（01 §2、§5.1）：
#  1) 本文件是账号服务 HTTP 的唯一出口：组包 -> POST -> 解析，异常不外抛；
#  2) 不做任何业务判断、不写库、不落 Redis、不记口令与验证码；
#  3) 业务语义（登录成败映射、USER_BASIC 同步）一律在 processor/accountService.py。

_VERSION = "20261027"

import os
import sys
import traceback
from typing import Any

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)

import requests

from common import miscCommon as misc
from common.loggingCommon import get_logger
from config.basicSettings import ROLE_ACCOUNT_ROLE
from config.localSettings import settings

_LOG = get_logger("mahjong.account")

_processorPID = os.getpid()

#账号服务请求超时(秒): 防止下游无响应时请求线程长时间挂起
_HTTP_REQUEST_TIMEOUT = 30
#启动探活用的短超时: 账号服务不可达时不能用 30 秒拖住启动
_PING_TIMEOUT = 3

#账号服务错误码口径（与 contentHub subfunc/accountSvcClient.py 一致）
ERR_SVC_OK = "B0"
ERR_SVC_OFFLINE = "CI"

#账号服务命令码(与 account service 协议一致, 集中登记避免散落魔数)
ACCOUNT_SVC_CMD_LOGIN = "A0A0"           #登录 / 注册
ACCOUNT_SVC_CMD_MODIFY_USER = "A2A0"     #修改用户资料（含 newPasswd 改密）
ACCOUNT_SVC_CMD_USER_INFO = "A3A0"       #取用户信息
ACCOUNT_SVC_CMD_LOGOUT = "A5A0"          #登出
ACCOUNT_SVC_CMD_SMS_REQUEST = "A6A0"     #短信验证码请求
ACCOUNT_SVC_CMD_SMS_VERIFY = "A7A0"      #短信验证码校验（本项目不启用）
ACCOUNT_SVC_CMD_PING = "A8A0"            #服务探活
ACCOUNT_SVC_CMD_RESET_PASSWD = "A9A0"    #凭验证码重置口令
ACCOUNT_SVC_CMD_MODIFY_ROLE = "AEA0"     #修改角色
ACCOUNT_SVC_CMD_USER_EXIST = "AIA0"      #用户存在性

#固定请求头(与 ylwz 既有体系一致)
_ACCOUNT_HTTP_HEADERS = {"content-type": "application/json"}


def _serviceUrl() -> str:
    return (settings.account_service_url or "").strip()


def accountServiceRequestEx(cmd: str, requestData: Any, timeout: int = _HTTP_REQUEST_TIMEOUT):
    """账号服务低层转发(唯一出口, 带 HTTP 状态码)。

       出参: (statusCode, rtnData)
             statusCode HTTP 状态码; 请求未发起或异常时为 0;
             rtnData    账号服务返回的报文字典; 非 200 / 非 JSON 时为 {}。
       说明: 本函数不抛异常、不做业务语义解释，调用方据 statusCode != 200 判定「下游不可用」。
    """
    statusCode = 0
    result: dict = {}
    url = _serviceUrl()
    if not url:
        _LOG.error("PID:%s, accountServiceRequestEx cmd:%s, ACCOUNT_SERVICE_URL 未配置", _processorPID, cmd)
        return statusCode, result

    try:
        if not isinstance(requestData, dict):
            requestData = {}
        else:
            requestData = dict(requestData)

        requestData["CMD"] = cmd

        payload = misc.jsonDumps(requestData)
        r = requests.post(url, data=payload, headers=_ACCOUNT_HTTP_HEADERS, timeout=timeout)

        statusCode = r.status_code
        if statusCode == 200:
            rtnData = misc.jsonLoads(r.text)
            if isinstance(rtnData, dict):
                result = rtnData

    except Exception as e:
        #账号服务不可达 / 超时 / 非法 JSON: 一律收敛为空报文, 由上层映射 CI
        #日志只留一行结论；完整堆栈仅在 DEBUG 级别输出，避免刷屏与泄露请求体
        _LOG.error(
            "PID:%s, accountServiceRequestEx cmd:%s, errType:%s, errMsg:%s",
            _processorPID,
            cmd,
            type(e).__name__,
            str(e).splitlines()[0] if str(e) else "",
        )
        _LOG.debug("accountServiceRequestEx cmd:%s traceback:\n%s", cmd, traceback.format_exc())

    return statusCode, result


def accountServiceRequest(cmd: str, requestData: Any, timeout: int = _HTTP_REQUEST_TIMEOUT) -> dict:
    """账号服务低层转发(仅返回报文字典)。网络异常 / 非 200 / 非 JSON 一律返回 {}, 不抛异常。"""
    _, rtnData = accountServiceRequestEx(cmd, requestData, timeout=timeout)

    return rtnData


def svcErrCode(rtnData: Any) -> str:
    """从账号服务回包中取错误码: 优先 MSG.errCode(与基线一致), 其次顶层 errCode;
       均缺失时视为成功 B0（acis 成功回包也会带顶层 errCode=B0）。"""
    result = ERR_SVC_OK

    if isinstance(rtnData, dict):
        msgData = rtnData.get("MSG", {})
        if isinstance(msgData, dict) and msgData.get("errCode"):
            result = msgData.get("errCode")
        elif rtnData.get("errCode"):
            result = rtnData.get("errCode")

    return result


def forward(cmd: str, dataSet: Any, roleName: str | None = None):
    """账号服务薄转发(本项目所有账号类 CMD 的唯一入口)。

       入参:
         cmd      账号服务命令码(A0A0/A2A0/A3A0/A5A0/A6A0/A9A0 ...);
         dataSet  请求报文(原样透传, 不修改调用方字典);
         roleName 需要做「本系统角色 -> 账号服务角色」转换时传入, 缺省不转换。

       出参: (errCode, rtnData)
         errCode  账号服务错误码; 下游非 200 / 不可达时统一为 CI;
         rtnData  账号服务原始回包(失败时为空字典)。
    """
    requestData = dict(dataSet) if isinstance(dataSet, dict) else {}

    if roleName is not None:
        if roleName in ROLE_ACCOUNT_ROLE:
            requestData["roleName"] = ROLE_ACCOUNT_ROLE[roleName]
        else:
            #角色无法映射到账号服务: 与 contentHub 一致, 直接判 B8(会话/角色异常), 不再转发
            return "B8", {}

    statusCode, rtnData = accountServiceRequestEx(cmd, requestData)

    if statusCode != 200:
        _LOG.warning(
            "W: PID:%s, account service unavailable, cmd:%s, status:%s",
            _processorPID,
            cmd,
            statusCode,
        )
        return ERR_SVC_OFFLINE, {}

    return svcErrCode(rtnData), rtnData


def getUserInfo(loginID: str, sessionID: str = "") -> dict:
    """A3A0: 取用户基本信息。

    注意: acis 的 A3A0 依赖会话上下文（sessionIDSet.loginID），**必须**带上 A0A0 回包里的
    sessionID；不带会话一律 B8。失败返回 {}（调用方按「取不到资料」处理）。

    不做角色回落（角色映射在 processor/accountService.py 统一处理）。
    """
    if not loginID or not sessionID:
        return {}

    errCode, rtnData = forward(
        ACCOUNT_SVC_CMD_USER_INFO, {"loginID": loginID, "sessionID": sessionID}
    )
    if errCode != ERR_SVC_OK:
        return {}

    return rtnData


def chkUserExist(loginID: str) -> bool:
    """AIA0: 账号服务侧用户存在性。出参 True / False（不抛异常）。

    字段口径以 acis 为准：请求键为 userID，回包键为 userExistFlag（Y/N）。
    """
    if not loginID:
        return False

    statusCode, rtnData = accountServiceRequestEx(
        ACCOUNT_SVC_CMD_USER_EXIST, {"userID": loginID}
    )
    if statusCode != 200:
        return False

    return rtnData.get("userExistFlag") == "Y"


def chkUserExistEx(loginID: str) -> tuple[bool, str]:
    """AIA0 的「可区分下游不可达」版本（S4 添加成员用）。

    出参: (是否存在, errCode)
      - 账号服务正常：(`Y` → True / 其它 → False, "B0")
      - 下游不可达/非 200：(False, "CI")
    这样调用方能区分「账号不存在（404）」与「账号服务挂了（503）」，
    避免把一次网络故障误判成「账号不存在」。
    """
    if not loginID:
        return False, ERR_SVC_OK

    statusCode, rtnData = accountServiceRequestEx(
        ACCOUNT_SVC_CMD_USER_EXIST, {"userID": loginID}
    )
    if statusCode != 200:
        return False, ERR_SVC_OFFLINE

    return rtnData.get("userExistFlag") == "Y", svcErrCode(rtnData)


def ping(timeout: int = _PING_TIMEOUT) -> tuple[bool, str]:
    """启动探活: 出参 (可达, 说明)。不抛异常、不阻塞启动（短超时）。"""
    url = _serviceUrl()
    if not url:
        return False, "ACCOUNT_SERVICE_URL 未配置"

    statusCode, rtnData = accountServiceRequestEx(ACCOUNT_SVC_CMD_PING, {}, timeout=timeout)
    if statusCode == 200:
        return True, f"HTTP 200, errCode={svcErrCode(rtnData)}"
    if statusCode == 0:
        return False, "不可达（连接失败或超时）"

    return False, f"HTTP {statusCode}"


if __name__ == "__main__":
    print("ACCOUNT_SERVICE_URL", _serviceUrl())
    print("account svc cmd list", [
        ACCOUNT_SVC_CMD_LOGIN, ACCOUNT_SVC_CMD_MODIFY_USER, ACCOUNT_SVC_CMD_USER_INFO,
        ACCOUNT_SVC_CMD_LOGOUT, ACCOUNT_SVC_CMD_SMS_REQUEST, ACCOUNT_SVC_CMD_SMS_VERIFY,
        ACCOUNT_SVC_CMD_PING, ACCOUNT_SVC_CMD_RESET_PASSWD, ACCOUNT_SVC_CMD_MODIFY_ROLE,
        ACCOUNT_SVC_CMD_USER_EXIST,
    ])
    print("ping", ping())

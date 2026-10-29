"""S3 账号链路用例：acis 用内存假实现，USER_BASIC 用内存假表。

覆盖验收清单里可在无 MySQL / 无账号服务环境下验证的部分：
  登录成功/失败、CI 503 不落库、首登插入与二次登录零 UPDATE、JWT 篡改/过期 401、
  注册（开关/未发码/错码/重复）、找回口令（旧码作废、只回写镜像）、60 秒冷却与 5 次锁定、
  logout 不因下游异常失败、日志不含口令明文。
"""

from __future__ import annotations

import logging

import jwt
import pytest
from fastapi.testclient import TestClient

from common import accountClient
from config.localSettings import settings
from main.app import app
from processor import accountService

LOGIN_ID = "13800000000"
PASSWD = "secret-pass"
NEW_PASSWD = "another-pass"
ACIS_ROLE = "customer"
ACIS_SESSION = "acis-session-1"


class FakeUserBasic:
    """内存版 USER_BASIC：只实现本模块用到的 3 个函数。"""

    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}
        self.inserts: list[dict] = []
        self.updates: list[dict] = []

    # -- mysqlCommon 的 3 个函数 --
    def queryUserBasic(self, loginID="", **kwargs):
        row = self.rows.get(loginID)
        return [dict(row)] if row else []

    def insertUserBasic(self, loginID, dataSet):
        row = {key: value for key, value in dataSet.items()}
        row["loginID"] = loginID
        self.rows[loginID] = row
        self.inserts.append(row)
        return 1

    def updateUserBasic(self, loginID, dataSet):
        row = self.rows.get(loginID)
        if row is None:
            return 0
        row.update({key: value for key, value in dataSet.items()})
        self.updates.append(dict(dataSet))
        return 1


class FakeAcis:
    """内存版账号服务：按 CMD 返回与 acis 同形状的报文。"""

    def __init__(self) -> None:
        self.users: dict[str, str] = {}          # loginID -> md5(passwd+loginID)
        self.codes: dict[str, str] = {}          # loginID -> verifyCode
        self.offline = False
        self.calls: list[tuple[str, dict]] = []

    def forward(self, cmd, dataSet, roleName=None):
        self.calls.append((cmd, dict(dataSet)))
        if self.offline:
            return "CI", {}

        data = dict(dataSet)
        if cmd == accountClient.ACCOUNT_SVC_CMD_LOGIN:
            return self._login(data)
        if cmd == accountClient.ACCOUNT_SVC_CMD_USER_INFO:
            return self._userInfo(data)
        if cmd == accountClient.ACCOUNT_SVC_CMD_USER_EXIST:
            return "B0", {"userExistFlag": "Y" if data.get("userID") in self.users else "N"}
        if cmd == accountClient.ACCOUNT_SVC_CMD_SMS_REQUEST:
            return "B0", {"loginID": data.get("loginID")}
        if cmd == accountClient.ACCOUNT_SVC_CMD_RESET_PASSWD:
            return self._reset(data)
        if cmd == accountClient.ACCOUNT_SVC_CMD_LOGOUT:
            return "B0", {}
        if cmd == accountClient.ACCOUNT_SVC_CMD_MODIFY_USER:
            return self._modify(data)
        return "BA", {}

    # -- 内部 --
    def _login(self, data):
        loginID = data.get("loginID", "")
        passwd = data.get("passwd", "")
        verifyCode = data.get("verifyCode", "")
        if loginID in self.users:
            if self.users[loginID] != passwd:
                return "B5", {}
            return "B0", {
                "loginID": loginID,
                "sessionID": ACIS_SESSION,
                "roleName": ACIS_ROLE,
                "activeFlag": "1",
            }
        if not verifyCode or self.codes.get(loginID) != verifyCode:
            return "BM", {}
        self.users[loginID] = passwd
        self.codes.pop(loginID, None)
        return "B0", {
            "loginID": loginID,
            "sessionID": ACIS_SESSION,
            "roleName": ACIS_ROLE,
            "activeFlag": "1",
        }

    def _userInfo(self, data):
        loginID = data.get("loginID", "")
        if not data.get("sessionID") or loginID not in self.users:
            return "B8", {}
        return "B0", {
            "loginID": loginID,
            "nickName": "爸爸",
            "sex": "1",
            "avatarID": "",
            "mobilePhoneNo": loginID,
            "activeFlag": "1",
            "roleName": ACIS_ROLE,
        }

    def _reset(self, data):
        loginID = data.get("loginID", "")
        if loginID not in self.users:
            return "BE", {}
        if not data.get("verifyCode") or self.codes.get(loginID) != data["verifyCode"]:
            return "BM", {}
        self.users[loginID] = data.get("passwd", "")
        self.codes.pop(loginID, None)
        return "B0", {}

    def _modify(self, data):
        loginID = data.get("loginID", "")
        if loginID not in self.users:
            return "BE", {}
        if not data.get("sessionID"):
            return "B8", {}
        self.users[loginID] = data.get("newPasswd", "")
        return "B0", {}


@pytest.fixture
def fakeMysql(monkeypatch):
    store = FakeUserBasic()
    monkeypatch.setattr(accountService.mysqlCommon, "queryUserBasic", store.queryUserBasic)
    monkeypatch.setattr(accountService.mysqlCommon, "insertUserBasic", store.insertUserBasic)
    monkeypatch.setattr(accountService.mysqlCommon, "updateUserBasic", store.updateUserBasic)
    # S4：登录与 /auth/me 会读家庭列表与偏好；这里退化为「没有家庭」
    monkeypatch.setattr(
        accountService.mysqlCommon, "query_mj_family_list_by_login", lambda loginID: []
    )
    monkeypatch.setattr(
        accountService.mysqlCommon, "query_mj_user_pref_by_login", lambda loginID: {}
    )
    monkeypatch.setattr(
        accountService.mysqlCommon, "query_mj_family_by_id", lambda familyID: {}
    )
    return store


@pytest.fixture
def fakeAcis(monkeypatch):
    acis = FakeAcis()
    monkeypatch.setattr(accountService.accountClient, "forward", acis.forward)
    monkeypatch.setattr(
        accountService.accountClient,
        "getUserInfo",
        lambda loginID, sessionID="": (
            acis._userInfo({"loginID": loginID, "sessionID": sessionID})[1]
        ),
    )
    monkeypatch.setattr(
        accountService.accountClient,
        "chkUserExist",
        lambda loginID: loginID in acis.users,
    )
    accountService.verifyCodeGuard.resetAll()
    accountService._sessionCache.clear()
    return acis


@pytest.fixture
def client(monkeypatch):
    # 路由只做协议转换，账号动作已被上面的 fixture 替换
    return TestClient(app)


# ---------------------------------------------------------------- 登录


def test_login_inserts_user_basic_and_returns_token(fakeMysql, fakeAcis, client):
    fakeAcis.users[LOGIN_ID] = accountService.hashPasswd(PASSWD, LOGIN_ID)

    resp = client.post("/api/auth/login", json={"login_id": LOGIN_ID, "passwd": PASSWD})
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["token"]
    assert body["families"] == [] and body["current_family_code"] is None
    assert body["user"]["login_id"] == LOGIN_ID
    assert body["user"]["role"] == "member"
    assert body["user"]["nick_name"] == "爸爸"

    # 首次登录：插入一行，列集合与 02 §3.1 的 44 列一致
    assert len(fakeMysql.inserts) == 1
    row = fakeMysql.rows[LOGIN_ID]
    assert set(row) <= set(_userBasicColumns())
    assert row["regID"] == LOGIN_ID
    assert row["regYMDHMS"] and len(row["regYMDHMS"]) == 14
    assert row["gender"] == "1"
    assert row["roleName"] == ACIS_ROLE

    # JWT 载荷只有 sub/role/iat/exp
    payload = jwt.decode(body["token"], settings.secret_key, algorithms=["HS256"])
    assert payload["sub"] == LOGIN_ID
    assert payload["role"] == "member"
    assert set(payload) == {"sub", "role", "iat", "exp"}


def test_second_login_without_changes_skips_update(fakeMysql, fakeAcis, client):
    fakeAcis.users[LOGIN_ID] = accountService.hashPasswd(PASSWD, LOGIN_ID)

    assert client.post("/api/auth/login", json={"login_id": LOGIN_ID, "passwd": PASSWD}).status_code == 200
    fakeMysql.updates.clear()

    assert client.post("/api/auth/login", json={"login_id": LOGIN_ID, "passwd": PASSWD}).status_code == 200
    assert fakeMysql.updates == []


def test_local_nickname_survives_login_sync(fakeMysql, fakeAcis, client):
    """昵称以本地为准：家庭管理员代改后，登录同步不得把 acis 回包写回去。"""
    fakeAcis.users[LOGIN_ID] = accountService.hashPasswd(PASSWD, LOGIN_ID)
    assert client.post("/api/auth/login", json={"login_id": LOGIN_ID, "passwd": PASSWD}).status_code == 200
    assert fakeMysql.rows[LOGIN_ID]["nickName"] == "爸爸"

    assert accountService.updateNickName(LOGIN_ID, "小舅", operatorLoginID="13900000000") is True
    assert fakeMysql.rows[LOGIN_ID]["nickName"] == "小舅"
    assert fakeMysql.rows[LOGIN_ID]["modifyID"] == "13900000000"
    fakeMysql.updates.clear()

    resp = client.post("/api/auth/login", json={"login_id": LOGIN_ID, "passwd": PASSWD})
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["nick_name"] == "小舅"
    assert fakeMysql.rows[LOGIN_ID]["nickName"] == "小舅"
    assert fakeMysql.updates == []


def test_wrong_passwd_is_account_auth_failed(fakeMysql, fakeAcis, client):
    fakeAcis.users[LOGIN_ID] = accountService.hashPasswd(PASSWD, LOGIN_ID)

    resp = client.post("/api/auth/login", json={"login_id": LOGIN_ID, "passwd": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["code"] == "ACCOUNT_AUTH_FAILED"
    assert fakeMysql.inserts == []


def test_account_service_offline_returns_503_and_writes_nothing(fakeMysql, fakeAcis, client):
    fakeAcis.offline = True

    resp = client.post("/api/auth/login", json={"login_id": LOGIN_ID, "passwd": PASSWD})
    assert resp.status_code == 503
    assert resp.json()["code"] == "ACCOUNT_SERVICE_UNAVAILABLE"
    assert fakeMysql.inserts == [] and fakeMysql.rows == {}


def test_tampered_or_expired_token_is_unauthorized(fakeMysql, fakeAcis, client):
    fakeAcis.users[LOGIN_ID] = accountService.hashPasswd(PASSWD, LOGIN_ID)
    token = client.post(
        "/api/auth/login", json={"login_id": LOGIN_ID, "passwd": PASSWD}
    ).json()["token"]

    tampered = token[:-2] + ("aa" if not token.endswith("aa") else "bb")
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"

    expired = jwt.encode(
        {"sub": LOGIN_ID, "role": "member", "iat": 1, "exp": 2},
        settings.secret_key,
        algorithm="HS256",
    )
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401


def test_login_state_change_password(fakeMysql, fakeAcis, client):
    fakeAcis.users[LOGIN_ID] = accountService.hashPasswd(PASSWD, LOGIN_ID)
    token = client.post(
        "/api/auth/login", json={"login_id": LOGIN_ID, "passwd": PASSWD}
    ).json()["token"]

    resp = client.post(
        "/api/auth/password",
        json={"old_passwd": PASSWD, "new_passwd": NEW_PASSWD},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text

    ok = client.post("/api/auth/login", json={"login_id": LOGIN_ID, "passwd": NEW_PASSWD})
    assert ok.status_code == 200
    assert fakeMysql.rows[LOGIN_ID]["passwd"] == accountService.hashPasswd(NEW_PASSWD, LOGIN_ID)


# ---------------------------------------------------------------- 注册


def test_register_disabled_never_touches_account_service(fakeMysql, fakeAcis, client, monkeypatch):
    monkeypatch.setattr(settings, "account_allow_register", False, raising=False)

    resp = client.post(
        "/api/auth/register",
        json={"login_id": LOGIN_ID, "passwd": PASSWD, "verify_code": "123456"},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ACCOUNT_REGISTER_DISABLED"
    assert fakeAcis.calls == []


def test_register_requires_verify_code(fakeMysql, fakeAcis, client, monkeypatch):
    monkeypatch.setattr(settings, "account_allow_register", True, raising=False)

    resp = client.post(
        "/api/auth/register",
        json={"login_id": LOGIN_ID, "passwd": PASSWD, "verify_code": "123456"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "VERIFY_CODE_REQUIRED"
    assert not [call for call in fakeAcis.calls if call[0] == "A0A0"]


def test_register_happy_path_and_duplicate(fakeMysql, fakeAcis, client, monkeypatch):
    monkeypatch.setattr(settings, "account_allow_register", True, raising=False)
    fakeAcis.codes[LOGIN_ID] = "123456"

    sent = client.post("/api/auth/verify-code", json={"login_id": LOGIN_ID, "scene": "register"})
    assert sent.status_code == 200, sent.text
    assert sent.json()["cooldown_seconds"] == 60

    resp = client.post(
        "/api/auth/register",
        json={"login_id": LOGIN_ID, "passwd": PASSWD, "verify_code": "123456", "nick_name": "爸爸"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ok": True, "login_id": LOGIN_ID}
    assert fakeMysql.rows[LOGIN_ID]["passwd"] == accountService.hashPasswd(PASSWD, LOGIN_ID)
    # 注册不签发 JWT
    assert "token" not in resp.json()

    accountService.verifyCodeGuard.clear("register", LOGIN_ID)
    fakeAcis.codes[LOGIN_ID] = "123456"
    client.post("/api/auth/verify-code", json={"login_id": LOGIN_ID, "scene": "register"})
    dup = client.post(
        "/api/auth/register",
        json={"login_id": LOGIN_ID, "passwd": PASSWD, "verify_code": "123456"},
    )
    assert dup.status_code == 409
    assert dup.json()["code"] == "ACCOUNT_LOGIN_ID_EXISTS"


def test_register_wrong_code(fakeMysql, fakeAcis, client, monkeypatch):
    monkeypatch.setattr(settings, "account_allow_register", True, raising=False)
    fakeAcis.codes[LOGIN_ID] = "123456"
    client.post("/api/auth/verify-code", json={"login_id": LOGIN_ID, "scene": "register"})

    resp = client.post(
        "/api/auth/register",
        json={"login_id": LOGIN_ID, "passwd": PASSWD, "verify_code": "000000"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "VERIFY_CODE_INVALID"


# ---------------------------------------------------------------- 找回口令


def test_reset_password_rotates_code_and_mirrors_passwd(fakeMysql, fakeAcis, client, monkeypatch):
    monkeypatch.setattr(settings, "account_allow_password_reset", True, raising=False)
    fakeAcis.users[LOGIN_ID] = accountService.hashPasswd(PASSWD, LOGIN_ID)
    fakeMysql.rows[LOGIN_ID] = {"loginID": LOGIN_ID, "passwd": "", "passwdYMDHMS": ""}
    fakeAcis.codes[LOGIN_ID] = "654321"

    sent = client.post(
        "/api/auth/verify-code", json={"login_id": LOGIN_ID, "scene": "reset_password"}
    )
    assert sent.status_code == 200

    resp = client.post(
        "/api/auth/password/reset",
        json={"login_id": LOGIN_ID, "verify_code": "654321", "new_passwd": NEW_PASSWD},
    )
    assert resp.status_code == 200, resp.text

    # 旧口令失败、新口令成功
    assert client.post("/api/auth/login", json={"login_id": LOGIN_ID, "passwd": PASSWD}).status_code == 401
    assert client.post("/api/auth/login", json={"login_id": LOGIN_ID, "passwd": NEW_PASSWD}).status_code == 200

    # 只回写 passwd/passwdYMDHMS 镜像
    assert fakeMysql.rows[LOGIN_ID]["passwd"] == accountService.hashPasswd(NEW_PASSWD, LOGIN_ID)
    assert fakeMysql.rows[LOGIN_ID]["passwdYMDHMS"]

    # 同一验证码二次提交失败
    again = client.post(
        "/api/auth/password/reset",
        json={"login_id": LOGIN_ID, "verify_code": "654321", "new_passwd": "third-pass"},
    )
    assert again.status_code == 400


def test_reset_unknown_account_still_ok(fakeMysql, fakeAcis, client, monkeypatch):
    monkeypatch.setattr(settings, "account_allow_password_reset", True, raising=False)

    resp = client.post(
        "/api/auth/verify-code", json={"login_id": "13900000000", "scene": "reset_password"}
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


# ---------------------------------------------------------------- 限流


def test_verify_code_cooldown_and_attempt_lock(fakeMysql, fakeAcis, client, monkeypatch):
    monkeypatch.setattr(settings, "account_allow_register", True, raising=False)
    fakeAcis.codes[LOGIN_ID] = "123456"

    first = client.post("/api/auth/verify-code", json={"login_id": LOGIN_ID, "scene": "register"})
    assert first.status_code == 200

    second = client.post("/api/auth/verify-code", json={"login_id": LOGIN_ID, "scene": "register"})
    assert second.status_code == 429
    assert second.json()["code"] == "VERIFY_CODE_SEND_TOO_FAST"

    for _ in range(int(settings.auth_verify_code_max_attempts)):
        resp = client.post(
            "/api/auth/register",
            json={"login_id": LOGIN_ID, "passwd": PASSWD, "verify_code": "000000"},
        )
        assert resp.status_code in (400, 429)

    locked = client.post(
        "/api/auth/register",
        json={"login_id": LOGIN_ID, "passwd": PASSWD, "verify_code": "123456"},
    )
    assert locked.status_code == 429
    assert locked.json()["code"] == "VERIFY_CODE_ATTEMPTS_EXCEEDED"


def test_options_reflect_switches(fakeMysql, fakeAcis, client, monkeypatch):
    monkeypatch.setattr(settings, "account_allow_register", False, raising=False)
    monkeypatch.setattr(settings, "account_allow_password_reset", True, raising=False)

    body = client.get("/api/auth/options").json()
    assert body == {
        "register_enabled": False,
        "password_reset_enabled": True,
        "verify_code_cooldown_seconds": 60,
    }


# ---------------------------------------------------------------- 登出与日志


def test_logout_returns_ok_even_when_account_service_is_down(fakeMysql, fakeAcis, client, monkeypatch):
    fakeAcis.users[LOGIN_ID] = accountService.hashPasswd(PASSWD, LOGIN_ID)
    token = client.post(
        "/api/auth/login", json={"login_id": LOGIN_ID, "passwd": PASSWD}
    ).json()["token"]

    fakeAcis.offline = True
    resp = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_passwd_never_logged(caplog, fakeMysql, fakeAcis, client):
    caplog.set_level(logging.DEBUG)
    fakeAcis.users[LOGIN_ID] = accountService.hashPasswd(PASSWD, LOGIN_ID)

    client.post("/api/auth/login", json={"login_id": LOGIN_ID, "passwd": PASSWD})
    client.post("/api/auth/login", json={"login_id": LOGIN_ID, "passwd": "wrong-pass"})

    text = "\n".join(record.getMessage() for record in caplog.records)
    assert PASSWD not in text
    assert "wrong-pass" not in text
    assert accountService.hashPasswd(PASSWD, LOGIN_ID) not in text


# ---------------------------------------------------------------- 辅助


def _userBasicColumns() -> list[str]:
    """从 database/userBasic.txt 读出 44 列（02 §3.1 的唯一来源）。"""
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "database" / "userBasic.txt"
    columns = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        columns.append(line.split()[0])
    return columns


def test_user_basic_columns_are_44():
    assert len(_userBasicColumns()) == 44

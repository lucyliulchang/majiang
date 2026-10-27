"""S4 家庭实体与数据隔离用例（无 MySQL 环境）。

做法：把 `mysqlCommon.mysqlDB` 换成一个 sqlite3 句柄，`mysqlCommon` 里的
手写查询与生成版 insert/update（含事务）全部照常执行——因此这里验证的是**真实 SQL**：
隔离用例能证明「家庭域查询带 familyID」，而不是内存里过滤出来的假象。

账号服务侧只替换三个外部触点（AIA0 / USER_BASIC 读写），其余走真实代码。
"""

from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from common import accountClient, mysqlCommon
from common.securityCommon import create_access_token
from main import deps
from main.app import app
from processor import accountService, familyService

OWNER = "13800000000"
ADMIN = "13900000000"
MEMBER = "13700000000"
OUTSIDER = "13600000000"
FAMILY_CODE = "lianjia"

# 测试里「账号服务侧存在」的登录号（AIA0 回 Y）
ACCOUNTS = {OWNER, ADMIN, MEMBER, OUTSIDER}


# ---------------------------------------------------------------- sqlite 句柄


class SqliteHandle:
    """把 mysqlCommon 用到的连接句柄 API 映射到 sqlite3（仅测试用）。

    mysqlCommon 只依赖 executeRead / executeWrite / fetchAll / insertID 与事务四件套，
    占位符统一为 %s，这里替换成 sqlite 的 ? 即可。
    """

    def __init__(self) -> None:
        # 同步路由跑在 AnyIO 线程池里，sqlite 默认禁止跨线程使用同一连接
        self.conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._lastRows: list[dict] = []
        self._lastRowID = 0
        self._depth = 0

    def _exec(self, sql: str, values=()):
        return self.conn.execute(sql.replace("%s", "?"), tuple(values or ()))

    def executeRead(self, sqlstr: str, values=()):
        cursor = self._exec(sqlstr, values)
        self._lastRows = [dict(row) for row in cursor.fetchall()]
        return len(self._lastRows)

    def fetchAll(self):
        return self._lastRows

    def executeWrite(self, sqlstr: str, values=()):
        cursor = self._exec(sqlstr, values)
        self._lastRowID = cursor.lastrowid or 0
        return cursor.rowcount

    def insertID(self):
        return self._lastRowID

    def begin(self):
        self._depth += 1
        if self._depth == 1:
            self.conn.execute("BEGIN")

    def commit(self):
        self._depth = max(0, self._depth - 1)
        if self._depth == 0:
            self.conn.execute("COMMIT")

    def rollback(self):
        self._depth = 0
        self.conn.execute("ROLLBACK")

    def ddl(self, *statements: str) -> None:
        for statement in statements:
            self.conn.execute(statement)

    def rows(self, sql: str, values=()) -> list[dict]:
        return [dict(row) for row in self._exec(sql, values).fetchall()]


_DDL = (
    """CREATE TABLE mj_family(
        recID INTEGER PRIMARY KEY AUTOINCREMENT,
        familyCode TEXT NOT NULL UNIQUE,
        familyName TEXT NOT NULL,
        ownerLoginID TEXT NOT NULL,
        defaultRuleFamilyCode TEXT,
        defaultSkinCode TEXT,
        familyStatus TEXT NOT NULL DEFAULT 'ENABLED',
        sortOrder INTEGER NOT NULL DEFAULT 0,
        label TEXT, memo TEXT, regID TEXT, regYMDHMS TEXT,
        modifyID TEXT, modifyYMDHMS TEXT, delFlag TEXT NOT NULL DEFAULT '0')""",
    """CREATE TABLE mj_family_member(
        recID INTEGER PRIMARY KEY AUTOINCREMENT,
        familyMemberKey TEXT NOT NULL UNIQUE,
        familyID INTEGER NOT NULL,
        loginID TEXT NOT NULL,
        memberRole TEXT NOT NULL DEFAULT 'MEMBER',
        memberStatus TEXT NOT NULL DEFAULT 'ACTIVE',
        joinedYMDHMS TEXT,
        label TEXT, memo TEXT, regID TEXT, regYMDHMS TEXT,
        modifyID TEXT, modifyYMDHMS TEXT, delFlag TEXT NOT NULL DEFAULT '0')""",
    """CREATE TABLE mj_user_pref(
        recID INTEGER PRIMARY KEY AUTOINCREMENT,
        loginID TEXT NOT NULL UNIQUE,
        lastFamilyID INTEGER,
        skinCode TEXT,
        soundEnabledFlag TEXT NOT NULL DEFAULT '1',
        soundVolume INTEGER NOT NULL DEFAULT 70,
        chatSoundFlag TEXT NOT NULL DEFAULT '1',
        showTenpaiFlag TEXT NOT NULL DEFAULT '1',
        label TEXT, memo TEXT, regID TEXT, regYMDHMS TEXT,
        modifyID TEXT, modifyYMDHMS TEXT, delFlag TEXT NOT NULL DEFAULT '0')""",
    """CREATE TABLE mj_audit_log(
        recID INTEGER PRIMARY KEY AUTOINCREMENT,
        familyID INTEGER NOT NULL DEFAULT 0,
        operatorLoginID TEXT NOT NULL,
        actionCode TEXT NOT NULL,
        targetType TEXT NOT NULL,
        targetID TEXT,
        detailJson TEXT,
        clientIP TEXT,
        createdYMDHMS TEXT NOT NULL,
        label TEXT, memo TEXT, regID TEXT, regYMDHMS TEXT,
        modifyID TEXT, modifyYMDHMS TEXT, delFlag TEXT NOT NULL DEFAULT '0')""",
    """CREATE TABLE mj_tile_skin(
        recID INTEGER PRIMARY KEY AUTOINCREMENT,
        skinCode TEXT NOT NULL UNIQUE,
        skinName TEXT NOT NULL,
        familyID INTEGER NOT NULL DEFAULT 0,
        previewFileID TEXT,
        tileAspect REAL NOT NULL DEFAULT 0.6667,
        defaultFlag TEXT NOT NULL DEFAULT '0',
        skinStatus TEXT NOT NULL DEFAULT 'ENABLED',
        sortOrder INTEGER NOT NULL DEFAULT 0,
        ownerLoginID TEXT,
        label TEXT, memo TEXT, regID TEXT, regYMDHMS TEXT,
        modifyID TEXT, modifyYMDHMS TEXT, delFlag TEXT NOT NULL DEFAULT '0')""",
    """CREATE TABLE mj_rule_family(
        recID INTEGER PRIMARY KEY AUTOINCREMENT,
        ruleFamilyCode TEXT NOT NULL UNIQUE,
        ruleFamilyName TEXT NOT NULL,
        engineCode TEXT NOT NULL,
        tileSetCode TEXT NOT NULL DEFAULT '136',
        capabilityJson TEXT,
        ruleFamilyStatus TEXT NOT NULL DEFAULT 'ENABLED',
        sortOrder INTEGER NOT NULL DEFAULT 0,
        label TEXT, memo TEXT, regID TEXT, regYMDHMS TEXT,
        modifyID TEXT, modifyYMDHMS TEXT, delFlag TEXT NOT NULL DEFAULT '0')""",
    """CREATE TABLE USER_BASIC(
        loginID TEXT PRIMARY KEY,
        nickName TEXT,
        roleName TEXT,
        avatarID TEXT,
        activeFlag TEXT,
        delFlag TEXT)""",
)


@pytest.fixture
def db(monkeypatch):
    handle = SqliteHandle()
    handle.ddl(*_DDL)
    monkeypatch.setattr(mysqlCommon, "mysqlDB", handle)

    # 账号档案：真实实现走 44 列 USER_BASIC，这里只保留测试需要的列
    for loginID, nickName in ((OWNER, "爸爸"), (ADMIN, "妈妈"), (MEMBER, "小舅"), (OUTSIDER, "路人")):
        handle.executeWrite(
            "INSERT INTO USER_BASIC (loginID, nickName, roleName, activeFlag, delFlag)"
            " VALUES (?,?,?,?,?)",
            (loginID, nickName, "customer", "1", "0"),
        )

    def loadUserRow(loginID: str) -> dict:
        rows = handle.rows("SELECT * FROM USER_BASIC WHERE loginID = ?", (loginID,))
        return rows[0] if rows else {}

    def ensureUserBasic(loginID: str, operatorLoginID: str = "") -> str:
        if loadUserRow(loginID):
            return "exists"
        handle.executeWrite(
            "INSERT INTO USER_BASIC (loginID, nickName, roleName, activeFlag, delFlag)"
            " VALUES (?,?,?,?,?)",
            (loginID, "", "customer", "1", "0"),
        )
        return "inserted"

    monkeypatch.setattr(accountService, "loadUserRow", loadUserRow)
    monkeypatch.setattr(accountService, "ensureUserBasic", ensureUserBasic)
    monkeypatch.setattr(
        accountClient,
        "chkUserExistEx",
        lambda loginID: (loginID in ACCOUNTS, accountClient.ERR_SVC_OK),
    )
    # 预置：全局内置皮肤 + 规则族
    handle.executeWrite(
        "INSERT INTO mj_tile_skin (skinCode, skinName, familyID, skinStatus, defaultFlag, delFlag)"
        " VALUES (?,?,?,?,?,?)",
        ("css-classic", "青玉经典", 0, "ENABLED", "1", "0"),
    )
    handle.executeWrite(
        "INSERT INTO mj_rule_family (ruleFamilyCode, ruleFamilyName, engineCode, delFlag)"
        " VALUES (?,?,?,?)",
        ("generic", "通用家庭标准", "generic", "0"),
    )
    return handle


@pytest.fixture
def client(db):
    return TestClient(app)


def headers(loginID: str, role: str = "member") -> dict:
    return {"Authorization": f"Bearer {create_access_token(loginID, role)}"}


def create_family(client, loginID: str = OWNER, code: str = FAMILY_CODE, name: str = "廉家") -> dict:
    resp = client.post(
        "/api/families",
        json={"family_code": code, "family_name": name},
        headers=headers(loginID),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def add_member(client, loginID: str, target: str, role: str = "MEMBER") -> dict:
    resp = client.post(
        f"/api/families/{FAMILY_CODE}/members",
        json={"login_id": target, "member_role": role},
        headers=headers(loginID),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------- 创建家庭


def test_create_family_writes_owner_member_and_pref(client, db):
    family = create_family(client)

    assert family["family_code"] == FAMILY_CODE
    assert family["family_name"] == "廉家"
    assert family["owner_login_id"] == OWNER
    assert family["member_role"] == "OWNER"
    assert family["status"] == "ENABLED"

    familyID = int(family_row(db)["recID"])
    members = db.rows("SELECT * FROM mj_family_member WHERE familyID = ?", (familyID,))
    assert len(members) == 1
    assert members[0]["loginID"] == OWNER
    assert members[0]["memberRole"] == "OWNER"
    assert members[0]["memberStatus"] == "ACTIVE"
    assert members[0]["familyMemberKey"] == f"{familyID}_{OWNER}"

    pref = db.rows("SELECT * FROM mj_user_pref WHERE loginID = ?", (OWNER,))
    assert len(pref) == 1
    assert int(pref[0]["lastFamilyID"]) == familyID

    # 我的家庭列表（join 成员表，ACTIVE）
    resp = client.get("/api/families", headers=headers(OWNER))
    assert resp.status_code == 200
    assert [item["family_code"] for item in resp.json()] == [FAMILY_CODE]


def family_row(db, code: str = FAMILY_CODE) -> dict:
    rows = db.rows("SELECT * FROM mj_family WHERE familyCode = ?", (code,))
    assert rows, "家庭未落库"
    return rows[0]


def test_duplicate_family_code_returns_409(client, db):
    create_family(client)

    resp = client.post(
        "/api/families",
        json={"family_code": FAMILY_CODE, "family_name": "另一个廉家"},
        headers=headers(OWNER),
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "FAMILY_CODE_EXISTS"
    # 不允许产生第二条家庭
    assert len(db.rows("SELECT * FROM mj_family")) == 1


def test_family_code_invalid_and_generated(client, db):
    resp = client.post(
        "/api/families",
        json={"family_code": "Bad Code", "family_name": "廉家"},
        headers=headers(OWNER),
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "FAMILY_CODE_INVALID"

    resp = client.post(
        "/api/families", json={"family_name": "Lian Family"}, headers=headers(OWNER)
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["family_code"].startswith("lian_family_")


# ---------------------------------------------------------------- 成员：AIA0 / 重复


def test_add_member_account_not_found(client, db):
    create_family(client)

    resp = client.post(
        f"/api/families/{FAMILY_CODE}/members",
        json={"login_id": "13500000000", "member_role": "MEMBER"},
        headers=headers(OWNER),
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "ACCOUNT_USER_NOT_FOUND"
    assert db.rows("SELECT * FROM mj_family_member WHERE loginID = ?", ("13500000000",)) == []


def test_add_member_twice_returns_400(client, db):
    create_family(client)
    member = add_member(client, OWNER, MEMBER)
    assert member["member_role"] == "MEMBER"
    assert member["member_status"] == "ACTIVE"
    assert member["nick_name"] == "小舅"

    resp = client.post(
        f"/api/families/{FAMILY_CODE}/members",
        json={"login_id": MEMBER, "member_role": "ADMIN"},
        headers=headers(OWNER),
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "MEMBER_ALREADY_EXISTS"


def test_add_member_cannot_assign_owner(client, db):
    create_family(client)

    resp = client.post(
        f"/api/families/{FAMILY_CODE}/members",
        json={"login_id": MEMBER, "member_role": "OWNER"},
        headers=headers(OWNER),
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "MEMBER_ROLE_INVALID"


# ---------------------------------------------------------------- 隔离


def test_non_member_get_family_403_without_leaking_existence(client, db):
    create_family(client)

    denied = client.get(f"/api/families/{FAMILY_CODE}", headers=headers(OUTSIDER))
    missing = client.get("/api/families/nonexistent_family", headers=headers(OUTSIDER))

    assert denied.status_code == 403
    assert denied.json()["code"] == "NOT_FAMILY_MEMBER"
    # 统一文案：无权 / 不存在 的响应完全一致，无法用于探测家庭是否存在
    assert missing.status_code == denied.status_code
    assert missing.json() == denied.json()
    assert FAMILY_CODE not in denied.text


def test_non_member_cannot_list_members_nor_see_rooms(client, db):
    create_family(client)

    resp = client.get(f"/api/families/{FAMILY_CODE}/members", headers=headers(OUTSIDER))
    assert resp.status_code == 403
    assert resp.json()["code"] == "NOT_FAMILY_MEMBER"


def test_non_admin_cannot_add_or_disable_member(client, db):
    create_family(client)
    add_member(client, OWNER, MEMBER)

    resp = client.post(
        f"/api/families/{FAMILY_CODE}/members",
        json={"login_id": OUTSIDER, "member_role": "MEMBER"},
        headers=headers(MEMBER),
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "NOT_FAMILY_ADMIN"

    resp = client.patch(
        f"/api/families/{FAMILY_CODE}/members/{MEMBER}",
        json={"member_status": "DISABLED"},
        headers=headers(MEMBER),
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "NOT_FAMILY_ADMIN"

    # 未被改动
    rows = db.rows("SELECT memberStatus FROM mj_family_member WHERE loginID = ?", (MEMBER,))
    assert rows[0]["memberStatus"] == "ACTIVE"


def test_admin_can_add_and_disable_member(client, db):
    create_family(client)
    add_member(client, OWNER, ADMIN, "ADMIN")

    resp = client.post(
        f"/api/families/{FAMILY_CODE}/members",
        json={"login_id": MEMBER, "member_role": "MEMBER"},
        headers=headers(ADMIN),
    )
    assert resp.status_code == 200, resp.text

    resp = client.patch(
        f"/api/families/{FAMILY_CODE}/members/{MEMBER}",
        json={"member_status": "DISABLED"},
        headers=headers(ADMIN),
    )
    assert resp.status_code == 200
    assert resp.json()["member_status"] == "DISABLED"

    # 停用后按非成员处理（隔离一致）
    resp = client.get(f"/api/families/{FAMILY_CODE}", headers=headers(MEMBER))
    assert resp.status_code == 403
    assert resp.json()["code"] == "NOT_FAMILY_MEMBER"


# ---------------------------------------------------------------- owner 保护与转让


def test_owner_cannot_remove_self(client, db):
    create_family(client)

    resp = client.delete(
        f"/api/families/{FAMILY_CODE}/members/{OWNER}", headers=headers(OWNER)
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "MEMBER_OWNER_PROTECTED"
    rows = db.rows("SELECT memberStatus, memberRole FROM mj_family_member WHERE loginID = ?", (OWNER,))
    assert rows[0]["memberStatus"] == "ACTIVE" and rows[0]["memberRole"] == "OWNER"


def test_remove_member_marks_left_and_can_rejoin(client, db):
    create_family(client)
    add_member(client, OWNER, MEMBER)

    resp = client.delete(
        f"/api/families/{FAMILY_CODE}/members/{MEMBER}", headers=headers(OWNER)
    )
    assert resp.status_code == 200 and resp.json()["ok"] is True

    rows = db.rows("SELECT memberStatus FROM mj_family_member WHERE loginID = ?", (MEMBER,))
    assert rows[0]["memberStatus"] == "LEFT"
    # 默认列表不含已退出成员
    resp = client.get(f"/api/families/{FAMILY_CODE}/members", headers=headers(OWNER))
    assert [item["login_id"] for item in resp.json()] == [OWNER]

    # 重新加入：复用原行（familyMemberKey 唯一）
    again = add_member(client, OWNER, MEMBER, "ADMIN")
    assert again["member_status"] == "ACTIVE" and again["member_role"] == "ADMIN"
    assert len(db.rows("SELECT * FROM mj_family_member")) == 2


def test_transfer_owner_keeps_single_owner(client, db):
    create_family(client)
    add_member(client, OWNER, ADMIN, "ADMIN")

    resp = client.patch(
        f"/api/families/{FAMILY_CODE}/members/{ADMIN}",
        json={"member_role": "OWNER"},
        headers=headers(OWNER),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["member_role"] == "OWNER"

    familyID = int(family_row(db)["recID"])
    owners = db.rows(
        "SELECT loginID FROM mj_family_member WHERE familyID = ? AND memberRole = 'OWNER'",
        (familyID,),
    )
    assert [row["loginID"] for row in owners] == [ADMIN]
    old = db.rows(
        "SELECT memberRole FROM mj_family_member WHERE familyID = ? AND loginID = ?",
        (familyID, OWNER),
    )
    assert old[0]["memberRole"] == "ADMIN"
    assert family_row(db)["ownerLoginID"] == ADMIN

    # 新 owner 能管人；老 owner（现 ADMIN）不能转让
    add_member(client, ADMIN, MEMBER)
    resp = client.patch(
        f"/api/families/{FAMILY_CODE}/members/{MEMBER}",
        json={"member_role": "OWNER"},
        headers=headers(OWNER),
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "NOT_FAMILY_ADMIN"


def test_owner_cannot_demote_self(client, db):
    create_family(client)
    add_member(client, OWNER, ADMIN, "ADMIN")

    resp = client.patch(
        f"/api/families/{FAMILY_CODE}/members/{OWNER}",
        json={"member_role": "ADMIN"},
        headers=headers(OWNER),
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "OWNER_MUST_TRANSFER"


# ---------------------------------------------------------------- 家庭停用


def test_disabled_family_blocks_resource_context(client, db):
    create_family(client)
    add_member(client, OWNER, ADMIN, "ADMIN")

    # 家庭管理员不能自行停用（只有系统管理员可改）
    resp = client.patch(
        f"/api/families/{FAMILY_CODE}", json={"status": "DISABLED"}, headers=headers(OWNER)
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "NOT_FAMILY_ADMIN"

    resp = client.patch(
        f"/api/families/{FAMILY_CODE}",
        json={"status": "DISABLED"},
        headers=headers(ADMIN, role="admin"),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "DISABLED"

    # 成员仍可登录、仍能看家庭本身
    resp = client.get(f"/api/families/{FAMILY_CODE}", headers=headers(OWNER))
    assert resp.status_code == 200

    # 资源类接口（房间/模板/皮肤）在 S5/S8 接 current_active_family，这里直接验证该闸门
    with pytest.raises(familyService.FamilyServiceError) as excinfo:
        deps.familyContextOf(OWNER, FAMILY_CODE, requireEnabled=True)
    assert excinfo.value.code == "FAMILY_DISABLED"
    assert excinfo.value.httpStatus == 403

    # 非成员仍然是「无权访问」，不泄露「家庭已停用」
    with pytest.raises(familyService.FamilyServiceError) as excinfo:
        deps.familyContextOf(OUTSIDER, FAMILY_CODE, requireEnabled=True)
    assert excinfo.value.code == "NOT_FAMILY_MEMBER"


# ---------------------------------------------------------------- 偏好


def test_pref_defaults_and_update(client, db):
    create_family(client)

    resp = client.get("/api/user/pref", headers=headers(OWNER))
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "last_family_code": FAMILY_CODE,
        "skin_code": None,
        "sound_enabled": True,
        "sound_volume": 70,
        "chat_sound": True,
        "show_tenpai": True,
    }

    resp = client.put(
        "/api/user/pref",
        json={"sound_volume": 35, "sound_enabled": False, "chat_sound": False, "show_tenpai": False},
        headers=headers(OWNER),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["sound_volume"] == 35
    assert resp.json()["sound_enabled"] is False

    # 持久化：再读一次仍生效
    resp = client.get("/api/user/pref", headers=headers(OWNER))
    assert resp.json()["sound_volume"] == 35
    assert resp.json()["show_tenpai"] is False


def test_pref_rejects_invalid_volume_and_foreign_family(client, db):
    create_family(client)
    create_family(client, loginID=OUTSIDER, code="otherfamily", name="别家")

    resp = client.put(
        "/api/user/pref", json={"sound_volume": 120}, headers=headers(OWNER)
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "SOUND_VOLUME_INVALID"

    # 切到别人家：403（不区分家庭是否存在）
    resp = client.put(
        "/api/user/pref", json={"last_family_code": "otherfamily"}, headers=headers(OWNER)
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "NOT_FAMILY_MEMBER"

    resp = client.put(
        "/api/user/pref", json={"last_family_code": "no_such_family"}, headers=headers(OWNER)
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "NOT_FAMILY_MEMBER"


def test_pref_skin_must_be_visible(client, db):
    create_family(client)
    db.executeWrite(
        "INSERT INTO mj_tile_skin (skinCode, skinName, familyID, skinStatus, defaultFlag, delFlag)"
        " VALUES (?,?,?,?,?,?)",
        ("other-skin", "别家皮肤", 999, "ENABLED", "0", "0"),
    )

    resp = client.put(
        "/api/user/pref", json={"skin_code": "other-skin"}, headers=headers(OWNER)
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "SKIN_NOT_VISIBLE"

    resp = client.put(
        "/api/user/pref", json={"skin_code": "css-classic"}, headers=headers(OWNER)
    )
    assert resp.status_code == 200
    assert resp.json()["skin_code"] == "css-classic"

    # 空串 = 回到默认
    resp = client.put("/api/user/pref", json={"skin_code": ""}, headers=headers(OWNER))
    assert resp.status_code == 200
    assert resp.json()["skin_code"] is None


# ---------------------------------------------------------------- 家庭更新


def test_update_family_by_admin_and_audit(client, db):
    create_family(client)
    add_member(client, OWNER, ADMIN, "ADMIN")

    resp = client.patch(
        f"/api/families/{FAMILY_CODE}",
        json={"family_name": "廉家二号", "default_rule_family_code": "generic"},
        headers=headers(ADMIN),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["family_name"] == "廉家二号"
    assert resp.json()["default_rule_family_code"] == "generic"

    resp = client.patch(
        f"/api/families/{FAMILY_CODE}",
        json={"default_rule_family_code": "no_such_rule"},
        headers=headers(OWNER),
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "RULE_FAMILY_NOT_FOUND"


# ---------------------------------------------------------------- 审计


def test_audit_rows_are_written_and_parseable(client, db):
    create_family(client)
    add_member(client, OWNER, ADMIN, "ADMIN")
    add_member(client, OWNER, MEMBER)
    client.patch(
        f"/api/families/{FAMILY_CODE}/members/{MEMBER}",
        json={"member_status": "DISABLED"},
        headers=headers(OWNER),
    )
    client.delete(f"/api/families/{FAMILY_CODE}/members/{MEMBER}", headers=headers(OWNER))
    client.patch(
        f"/api/families/{FAMILY_CODE}/members/{ADMIN}",
        json={"member_role": "OWNER"},
        headers=headers(OWNER),
    )

    rows = db.rows("SELECT * FROM mj_audit_log ORDER BY recID ASC")
    actions = [row["actionCode"] for row in rows]
    assert actions == [
        "FAMILY_CREATE",
        "MEMBER_ADD",
        "MEMBER_ADD",
        "MEMBER_UPDATE",
        "MEMBER_REMOVE",
        "OWNER_TRANSFER",
    ]
    for row in rows:
        detail = json.loads(row["detailJson"])
        assert isinstance(detail, dict)
        assert row["operatorLoginID"] == OWNER
        assert row["familyID"] == int(family_row(db)["recID"])

    # 通过 mysqlCommon 读回时，detailJson 已按 JSON 列解析成对象（02 §5）
    parsed = mysqlCommon.query_mj_audit_log_list(int(family_row(db)["recID"]))
    assert len(parsed) == len(rows)
    assert all(isinstance(item["detailJson"], dict) for item in parsed)


# ---------------------------------------------------------------- 家庭上下文解析


def test_current_family_resolves_from_path_and_pref(client, db):
    create_family(client)
    create_family(client, code="secondhome", name="第二家")

    # path 解析
    resp = client.get("/api/families/secondhome/members", headers=headers(OWNER))
    assert resp.status_code == 200
    assert [item["login_id"] for item in resp.json()] == [OWNER]

    # 切家庭：pref.lastFamilyID 跟随
    resp = client.put(
        "/api/user/pref",
        json={"last_family_code": "secondhome"},
        headers=headers(OWNER),
    )
    assert resp.status_code == 200
    assert resp.json()["last_family_code"] == "secondhome"

    # query 解析优先于 pref
    resp = client.get(f"/api/families/{FAMILY_CODE}", headers=headers(OWNER))
    assert resp.status_code == 200
    assert resp.json()["family_code"] == FAMILY_CODE


def test_me_returns_families_and_autoselects_pref(client, db):
    """04 §2：/auth/me 带家庭列表；lastFamilyID 为空且仅一个家庭时自动选中。"""
    create_family(client)

    # 模拟「偏好还没写过」：登录侧应能自动补写
    db.executeWrite("DELETE FROM mj_user_pref")

    resp = client.get("/api/auth/me", headers=headers(OWNER))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [item["family_code"] for item in body["families"]] == [FAMILY_CODE]
    assert body["families"][0]["member_role"] == "OWNER"
    assert body["current_family_code"] == FAMILY_CODE

    pref = db.rows("SELECT * FROM mj_user_pref WHERE loginID = ?", (OWNER,))
    assert len(pref) == 1
    assert int(pref[0]["lastFamilyID"]) == int(family_row(db)["recID"])

    # 没有家庭的用户：空数组 + null，不报错
    resp = client.get("/api/families", headers=headers(OUTSIDER))
    assert resp.status_code == 200 and resp.json() == []


def test_bootstrap_family_is_idempotent(db, monkeypatch):
    first = familyService.bootstrapFamily(OWNER, "廉家", FAMILY_CODE)
    assert first["familyCreated"] and first["memberCreated"] and first["prefUpdated"]

    second = familyService.bootstrapFamily(OWNER, "廉家", FAMILY_CODE)
    assert second["familyID"] == first["familyID"]
    assert not second["familyCreated"] and not second["memberCreated"]

    assert len(db.rows("SELECT * FROM mj_family")) == 1
    rows = db.rows("SELECT * FROM mj_family_member")
    assert len(rows) == 1 and rows[0]["memberRole"] == "OWNER"

    pref = db.rows("SELECT * FROM mj_user_pref WHERE loginID = ?", (OWNER,))
    assert int(pref[0]["lastFamilyID"]) == first["familyID"]

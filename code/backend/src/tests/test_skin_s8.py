"""S8 皮肤：上传校验 / 发布完整性 / 家庭隔离 / 默认唯一 / ETag / 静态缓存。

数据层沿用 `test_family_service.py` 的做法：把 `mysqlCommon.mysqlDB` 换成 sqlite3
句柄，业务 SQL 原样执行——因此这里验证的是真实 SQL 与真实落盘，而不是内存桩。
上传根目录通过替换 `skinService.publicRoot` 指向 tmp_path，绝不写仓库 data/。
"""

from __future__ import annotations

import re
import sqlite3
import struct
import zlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from common import accountClient, mysqlCommon
from common.securityCommon import create_access_token
from config.localSettings import settings
from main.app import app
from processor import accountService, familyService, skinService

OWNER_A = "13800000101"
MEMBER_A = "13800000102"
OWNER_B = "13800000103"
FAMILY_A = "skinfama"
FAMILY_B = "skinfamb"


# ---------------------------------------------------------------- sqlite 句柄


class SqliteHandle:
    def __init__(self) -> None:
        self.conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._lastRows: list[dict] = []
        self._lastRowID = 0
        self._depth = 0

    def _exec(self, sql: str, values=()):
        return self.conn.execute(sql.replace("%s", "?"), tuple(values or ()))

    def executeRead(self, sqlstr: str, values=()):
        self._lastRows = [dict(row) for row in self._exec(sqlstr, values).fetchall()]
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


_COMMON_TAIL = (
    "label TEXT, memo TEXT, regID TEXT, regYMDHMS TEXT, "
    "modifyID TEXT, modifyYMDHMS TEXT, delFlag TEXT NOT NULL DEFAULT '0')"
)

_DDL = (
    f"""CREATE TABLE mj_family(
        recID INTEGER PRIMARY KEY AUTOINCREMENT,
        familyCode TEXT NOT NULL UNIQUE, familyName TEXT NOT NULL,
        ownerLoginID TEXT NOT NULL, defaultRuleFamilyCode TEXT, defaultSkinCode TEXT,
        familyStatus TEXT NOT NULL DEFAULT 'ENABLED',
        sortOrder INTEGER NOT NULL DEFAULT 0, {_COMMON_TAIL}""",
    f"""CREATE TABLE mj_family_member(
        recID INTEGER PRIMARY KEY AUTOINCREMENT,
        familyMemberKey TEXT NOT NULL UNIQUE, familyID INTEGER NOT NULL,
        loginID TEXT NOT NULL, memberRole TEXT NOT NULL DEFAULT 'MEMBER',
        memberStatus TEXT NOT NULL DEFAULT 'ACTIVE', joinedYMDHMS TEXT, {_COMMON_TAIL}""",
    f"""CREATE TABLE mj_user_pref(
        recID INTEGER PRIMARY KEY AUTOINCREMENT, loginID TEXT NOT NULL UNIQUE,
        lastFamilyID INTEGER, skinCode TEXT,
        soundEnabledFlag TEXT NOT NULL DEFAULT '1', soundVolume INTEGER NOT NULL DEFAULT 70,
        chatSoundFlag TEXT NOT NULL DEFAULT '1',
        showTenpaiFlag TEXT NOT NULL DEFAULT '1', {_COMMON_TAIL}""",
    f"""CREATE TABLE mj_tile_skin(
        recID INTEGER PRIMARY KEY AUTOINCREMENT, skinCode TEXT NOT NULL UNIQUE,
        skinName TEXT NOT NULL, familyID INTEGER NOT NULL DEFAULT 0, previewFileID TEXT,
        tileAspect REAL NOT NULL DEFAULT 0.6667,
        defaultFlag TEXT NOT NULL DEFAULT '0',
        skinStatus TEXT NOT NULL DEFAULT 'ENABLED',
        sortOrder INTEGER NOT NULL DEFAULT 0, ownerLoginID TEXT, {_COMMON_TAIL}""",
    f"""CREATE TABLE mj_tile_skin_asset(
        recID INTEGER PRIMARY KEY AUTOINCREMENT, skinTileKey TEXT NOT NULL UNIQUE,
        skinID INTEGER NOT NULL, familyID INTEGER NOT NULL DEFAULT 0,
        tileKey TEXT NOT NULL, fileID TEXT NOT NULL, thumbFileID TEXT,
        width INTEGER NOT NULL DEFAULT 0, height INTEGER NOT NULL DEFAULT 0,
        fileSize INTEGER NOT NULL DEFAULT 0,
        sortOrder INTEGER NOT NULL DEFAULT 0, {_COMMON_TAIL}""",
    f"""CREATE TABLE mj_audit_log(
        recID INTEGER PRIMARY KEY AUTOINCREMENT, familyID INTEGER NOT NULL DEFAULT 0,
        operatorLoginID TEXT NOT NULL, actionCode TEXT NOT NULL, targetType TEXT NOT NULL,
        targetID TEXT, detailJson TEXT, clientIP TEXT,
        createdYMDHMS TEXT NOT NULL, {_COMMON_TAIL}""",
    """CREATE TABLE USER_BASIC(
        loginID TEXT PRIMARY KEY, nickName TEXT, roleName TEXT, avatarID TEXT,
        activeFlag TEXT, delFlag TEXT)""",
)


# ---------------------------------------------------------------- 图片构造


def _pngChunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def pngBytes(width: int = 192, height: int = 288) -> bytes:
    """最小合法 PNG 头（IHDR + IEND），足够通过 magic number 与尺寸解析。"""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + _pngChunk(b"IHDR", ihdr) + _pngChunk(b"IEND", b"")


def webpBytes(width: int = 192, height: int = 288) -> bytes:
    """VP8X（扩展格式）头，用来覆盖 webp 的尺寸解析分支。"""
    payload = b"\x00\x00\x00\x00" + (width - 1).to_bytes(3, "little") + (height - 1).to_bytes(3, "little")
    return b"RIFF" + (22).to_bytes(4, "little") + b"WEBP" + b"VP8X" + (10).to_bytes(4, "little") + payload


# ---------------------------------------------------------------- 环境


@pytest.fixture
def env(monkeypatch, tmp_path):
    handle = SqliteHandle()
    handle.ddl(*_DDL)
    monkeypatch.setattr(mysqlCommon, "mysqlDB", handle)

    for loginID, nickName in ((OWNER_A, "爸爸"), (MEMBER_A, "妈妈"), (OWNER_B, "舅舅")):
        handle.executeWrite(
            "INSERT INTO USER_BASIC (loginID, nickName, roleName, activeFlag, delFlag)"
            " VALUES (?,?,?,?,?)",
            (loginID, nickName, "customer", "1", "0"),
        )

    def loadUserRow(loginID: str) -> dict:
        rows = handle.rows("SELECT * FROM USER_BASIC WHERE loginID = ?", (loginID,))
        return rows[0] if rows else {}

    monkeypatch.setattr(accountService, "loadUserRow", loadUserRow)
    monkeypatch.setattr(
        accountClient,
        "chkUserExistEx",
        lambda loginID: (bool(loadUserRow(loginID)), accountClient.ERR_SVC_OK),
    )

    siteRoot = tmp_path / "site"
    monkeypatch.setattr(skinService, "publicRoot", lambda: siteRoot)

    familyA = familyService.bootstrapFamily(OWNER_A, "皮肤 A 家", FAMILY_A)
    familyB = familyService.bootstrapFamily(OWNER_B, "皮肤 B 家", FAMILY_B)
    handle.executeWrite(
        "INSERT INTO mj_family_member (familyMemberKey, familyID, loginID, memberRole,"
        " memberStatus, delFlag) VALUES (?,?,?,?,?,?)",
        (f"{familyA['familyID']}_{MEMBER_A}", familyA["familyID"], MEMBER_A, "MEMBER", "ACTIVE", "0"),
    )
    # 全局内置皮肤（种子口径）
    handle.executeWrite(
        "INSERT INTO mj_tile_skin (skinCode, skinName, familyID, skinStatus, defaultFlag, delFlag)"
        " VALUES (?,?,?,?,?,?)",
        ("css-classic", "青玉经典", 0, "ENABLED", "1", "0"),
    )
    return {
        "db": handle,
        "site": siteRoot,
        "familyA": familyA["familyID"],
        "familyB": familyB["familyID"],
    }


def headers(loginID: str, role: str = "member") -> dict:
    return {"Authorization": f"Bearer {create_access_token(loginID, role)}"}


@pytest.fixture
def client(env):
    return TestClient(app)


def uploadAll(loginID: str, skinCode: str) -> None:
    for tileKey in skinService.TILE_KEYS:
        skinService.uploadAsset(loginID, skinCode, tileKey, pngBytes(), f"{tileKey}.png")


def auditActions(db: SqliteHandle) -> list[str]:
    return [row["actionCode"] for row in db.rows("SELECT actionCode FROM mj_audit_log")]


# ---------------------------------------------------------------- 上传校验


def test_validate_upload_accepts_png_and_webp():
    png = skinService.validateUpload("1m", "1m.png", pngBytes())
    assert (png.ext, png.width, png.height) == ("png", 192, 288)

    webp = skinService.validateUpload("back", "back.webp", webpBytes(96, 144))
    assert (webp.ext, webp.width, webp.height) == ("webp", 96, 144)


def test_validate_upload_rejects_svg_ext_and_svg_content():
    with pytest.raises(skinService.SkinServiceError) as extErr:
        skinService.validateUpload("1m", "1m.svg", pngBytes())
    assert extErr.value.code == "UPLOAD_BAD_TYPE"

    with pytest.raises(skinService.SkinServiceError) as contentErr:
        skinService.validateUpload("1m", "1m.png", b'<svg xmlns="http://www.w3.org/2000/svg"/>')
    assert contentErr.value.code == "UPLOAD_BAD_TYPE"


def test_validate_upload_limits_size_ratio_and_tile_key():
    with pytest.raises(skinService.SkinServiceError) as tooLarge:
        skinService.validateUpload("1m", "1m.png", b"x" * (skinService.MAX_UPLOAD_BYTES + 1))
    assert tooLarge.value.code == "UPLOAD_TOO_LARGE"

    with pytest.raises(skinService.SkinServiceError) as badRatio:
        skinService.validateUpload("1m", "1m.png", pngBytes(200, 100))
    assert badRatio.value.code == "UPLOAD_BAD_DIMENSION"

    with pytest.raises(skinService.SkinServiceError) as badKey:
        skinService.validateUpload("../1m", "1m.png", pngBytes())
    assert badKey.value.code == "SKIN_TILE_KEY_INVALID"

    with pytest.raises(skinService.SkinServiceError) as tiny:
        skinService.validateUpload("1m", "1m.png", pngBytes(16, 24))
    assert tiny.value.code == "UPLOAD_BAD_DIMENSION"


# ---------------------------------------------------------------- 发布与文件


def test_upload_publish_and_incomplete(env):
    skin = skinService.createSkin(OWNER_A, FAMILY_A, "S8 测试皮", "s8test-skin")
    assert skin["status"] == skinService.SKIN_DISABLED
    assert skin["asset_count"] == 0

    uploadAll(OWNER_A, "s8test-skin")
    published = skinService.publish(OWNER_A, "s8test-skin")
    assert published["status"] == skinService.SKIN_ENABLED
    assert published["asset_count"] == 35
    assert published["fallback"] == "css-classic"
    assert published["assets"]["1m"].startswith("/majiangapp/tiles/s8test-skin/1m.")
    assert set(published["assets"]) == skinService.TILE_KEY_SET

    # 文件名完全由服务端生成：{tileKey}.{hash8}.{ext}
    tileDir = env["site"] / "tiles" / "s8test-skin"
    names = sorted(path.name for path in tileDir.iterdir())
    assert len(names) == 35
    assert all(re.fullmatch(r"[a-z0-9]+\.[0-9a-f]{8}\.png", name) for name in names), names

    # 缺一张 → SKIN_ASSET_INCOMPLETE 且列出键
    skinService.deleteAsset(OWNER_A, "s8test-skin", "5p")
    with pytest.raises(skinService.SkinServiceError) as missing:
        skinService.publish(OWNER_A, "s8test-skin")
    assert missing.value.code == "SKIN_ASSET_INCOMPLETE"
    assert "5p" in missing.value.message

    actions = auditActions(env["db"])
    for code in ("SKIN_CREATE", "SKIN_UPLOAD", "SKIN_PUBLISH", "SKIN_DELETE"):
        assert code in actions, actions


def test_preview_is_not_a_tile_key(env):
    skinService.createSkin(OWNER_A, FAMILY_A, "预览皮", "s8prev-skin")

    uploaded = skinService.uploadAsset(
        OWNER_A, "s8prev-skin", "preview", pngBytes(480, 320), "preview.png"
    )
    assert uploaded["tile_key"] == "preview"

    detail = skinService.getSkin(OWNER_A, "s8prev-skin", env["familyA"], FAMILY_A)
    assert detail["preview_url"].startswith("/majiangapp/tiles/s8prev-skin/preview.")
    assert detail["asset_count"] == 0 and "preview" not in detail["assets"]

    # 预览图不参与发布完整性：仍缺 35 张牌
    with pytest.raises(skinService.SkinServiceError) as incomplete:
        skinService.publish(OWNER_A, "s8prev-skin")
    assert incomplete.value.code == "SKIN_ASSET_INCOMPLETE"

    # 预览图是 3:2，牌面图 2:3 不接受
    with pytest.raises(skinService.SkinServiceError) as badRatio:
        skinService.uploadAsset(
            OWNER_A, "s8prev-skin", "preview", pngBytes(192, 288), "preview.png"
        )
    assert badRatio.value.code == "UPLOAD_BAD_DIMENSION"

    skinService.deleteAsset(OWNER_A, "s8prev-skin", "preview")
    assert skinService.getSkin(OWNER_A, "s8prev-skin", env["familyA"], FAMILY_A)["preview_url"] is None


def test_soft_delete_hides_skin_but_keeps_files(env):
    skin = skinService.createSkin(OWNER_A, FAMILY_A, "待删皮", "s8del-skin")
    uploadAll(OWNER_A, "s8del-skin")
    skinService.publish(OWNER_A, "s8del-skin")

    tileDir = env["site"] / "tiles" / skin["skin_code"]
    before = len(list(tileDir.iterdir()))
    assert before == 35

    skinService.softDelete(OWNER_A, "s8del-skin")

    skins, _etag, _ = skinService.listSkins(env["familyA"], FAMILY_A)
    assert "s8del-skin" not in [row["skin_code"] for row in skins]
    assert len(list(tileDir.iterdir())) == before  # 延迟清理：文件还在
    assert "SKIN_DELETE" in auditActions(env["db"])


# ---------------------------------------------------------------- 隔离与默认


def test_list_isolated_by_family_and_global_visible(env):
    skinService.createSkin(OWNER_A, FAMILY_A, "A 家青玉", "s8a-jade")
    uploadAll(OWNER_A, "s8a-jade")
    skinService.publish(OWNER_A, "s8a-jade")

    skinsA, _etagA, _ = skinService.listSkins(env["familyA"], FAMILY_A)
    skinsB, _etagB, _ = skinService.listSkins(env["familyB"], FAMILY_B)

    codesA = {row["skin_code"] for row in skinsA}
    codesB = {row["skin_code"] for row in skinsB}
    assert codesA == {"css-classic", "s8a-jade"}
    assert codesB == {"css-classic"}  # 家庭 A 的自定义皮肤对 B 不可见
    assert next(row for row in skinsA if row["skin_code"] == "css-classic")["family_code"] is None


def test_set_default_keeps_one_per_family(env):
    for code, name in (("s8def-one", "默认一"), ("s8def-two", "默认二")):
        skinService.createSkin(OWNER_A, FAMILY_A, name, code)
        uploadAll(OWNER_A, code)
        skinService.publish(OWNER_A, code)

    skinService.setDefault(OWNER_A, "s8def-one")
    skinService.setDefault(OWNER_A, "s8def-two")

    rows = env["db"].rows(
        "SELECT skinCode FROM mj_tile_skin WHERE familyID = ? AND defaultFlag = '1'",
        (env["familyA"],),
    )
    assert [row["skinCode"] for row in rows] == ["s8def-two"]

    skins, _etag, _ = skinService.listSkins(env["familyA"], FAMILY_A)
    defaults = [row["skin_code"] for row in skins if row["is_default"]]
    assert defaults == ["s8def-two"]  # 全局 css-classic 让位，清单里只有一个 default
    assert "SKIN_DEFAULT" in auditActions(env["db"])


# ---------------------------------------------------------------- HTTP / ETag


def test_http_admin_required_and_etag_304(env, client):
    skin = skinService.createSkin(OWNER_A, FAMILY_A, "HTTP 皮", "s8http-skin")

    # 非管理员上传 → 403 NOT_FAMILY_ADMIN
    denied = client.put(
        f"/api/skins/{skin['skin_code']}/1m",
        files={"file": ("1m.png", pngBytes(), "image/png")},
        headers=headers(MEMBER_A),
    )
    assert denied.status_code == 403, denied.text
    assert denied.json()["code"] == "NOT_FAMILY_ADMIN"

    # 管理员上传 → 200
    ok = client.put(
        f"/api/skins/{skin['skin_code']}/1m",
        files={"file": ("1m.png", pngBytes(), "image/png")},
        headers=headers(OWNER_A),
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["tile_key"] == "1m"
    assert body["file_id"].startswith("tiles/s8http-skin/1m.")
    assert (body["width"], body["height"]) == (192, 288)

    # 非 png/webp → 400 UPLOAD_BAD_TYPE
    badType = client.put(
        f"/api/skins/{skin['skin_code']}/2m",
        files={"file": ("2m.svg", b"<svg/>", "image/svg+xml")},
        headers=headers(OWNER_A),
    )
    assert badType.status_code == 400
    assert badType.json()["code"] == "UPLOAD_BAD_TYPE"

    # 清单 ETag → 304
    first = client.get(f"/api/skins?family_code={FAMILY_A}", headers=headers(OWNER_A))
    assert first.status_code == 200, first.text
    etag = first.headers["ETag"]
    assert etag

    second = client.get(
        f"/api/skins?family_code={FAMILY_A}",
        headers={**headers(OWNER_A), "If-None-Match": etag},
    )
    assert second.status_code == 304
    assert second.content == b""

    # 变更后 ETag 必须变
    uploadAll(OWNER_A, skin["skin_code"])
    skinService.publish(OWNER_A, skin["skin_code"])
    third = client.get(f"/api/skins?family_code={FAMILY_A}", headers=headers(OWNER_A))
    assert third.status_code == 200
    assert third.headers["ETag"] != etag


def test_static_tiles_cache_control(client):
    """`/majiangapp/tiles/**` 必须 immutable（05 §6.3）。"""
    tileDir = Path(settings.public_dir) / "tiles" / "s8cache"
    tileDir.mkdir(parents=True, exist_ok=True)
    target = tileDir / "1m.0badf00d.png"
    target.write_bytes(pngBytes())
    try:
        resp = client.get("/majiangapp/tiles/s8cache/1m.0badf00d.png")
        assert resp.status_code == 200
        assert "immutable" in resp.headers.get("cache-control", "")
    finally:
        target.unlink(missing_ok=True)
        try:
            tileDir.rmdir()
        except OSError:
            pass

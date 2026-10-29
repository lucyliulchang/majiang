"""S9：凭邀请码跨家庭入房的口径（纯 monkeypatch，不依赖测试库）。

覆盖：
  1. 非本家庭登录用户凭码可通过 REST 入房校验与 WS 握手（不再 403）；
  2. 本家庭成员仍解析出成员角色（家庭管理员因此能关房）；
  3. 家庭停用时 WS 握手拒绝（`FAMILY_DISABLED`）；
  4. 房间所属家庭已不存在时按「房间不存在」处理，不留孤儿房。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import mysqlCommon  # noqa: E402
from common.bizCommon import BizError  # noqa: E402
from processor import roomService  # noqa: E402

FAMILY_ID = 7
FAMILY_CODE = "lianjia"
OUTSIDER = "13800000099"

ROOM_ROW = {
    "recID": 33,
    "roomCode": "428915",
    "familyID": FAMILY_ID,
    "roomName": "周末家庭局",
    "hostLoginID": "13800000001",
    "hostName": "爸爸",
    "templateID": 12,
    "templateName": "家庭标准",
    "ruleFamilyCode": "generic",
    "ruleSnapshot": {"rule_family_code": "generic", "config": {}},
    "roomStatus": "OPEN",
    "createdYMDHMS": "20261025193000",
}

FAMILY_ROW = {
    "recID": FAMILY_ID,
    "familyCode": FAMILY_CODE,
    "familyName": "廉家",
    "familyStatus": "ENABLED",
}


def _patch(monkeypatch, *, family=None, member=None) -> None:
    monkeypatch.setattr(
        mysqlCommon, "query_mj_family_by_id", lambda familyID: dict(family or {})
    )
    monkeypatch.setattr(
        mysqlCommon,
        "query_mj_family_member",
        lambda familyID, loginID: dict(member or {}),
    )
    monkeypatch.setattr(mysqlCommon, "query_mj_room_by_code", lambda code: dict(ROOM_ROW))
    monkeypatch.setattr(mysqlCommon, "query_mj_room_by_id", lambda roomID: dict(ROOM_ROW))


def test_outsider_can_join_by_invite_code(monkeypatch):
    _patch(monkeypatch, family=FAMILY_ROW)

    check = roomService.getRoomByCode(OUTSIDER, "428915")
    assert check["room_code"] == "428915"
    assert check["can_join"] is True

    meta = roomService.roomMetaByCode(OUTSIDER, "428915")
    assert meta["room_id"] == ROOM_ROW["recID"]
    assert meta["family_code"] == FAMILY_CODE
    assert meta["family_name"] == "廉家"


def test_member_role_is_still_resolved(monkeypatch):
    _patch(
        monkeypatch,
        family=FAMILY_ROW,
        member={"memberRole": "ADMIN", "memberStatus": "ACTIVE"},
    )

    context, isMember = roomService._roomFamilyContext("13800000001", FAMILY_ID)
    assert isMember is True
    assert context["memberRole"] == "ADMIN"


def test_outsider_gets_no_member_role(monkeypatch):
    _patch(monkeypatch, family=FAMILY_ROW)

    context, isMember = roomService._roomFamilyContext(OUTSIDER, FAMILY_ID)
    assert isMember is False
    assert context["memberRole"] == ""


def test_disabled_family_rejects_ws_handshake(monkeypatch):
    _patch(monkeypatch, family={**FAMILY_ROW, "familyStatus": "DISABLED"})

    with pytest.raises(BizError) as error:
        roomService.roomMetaByCode(OUTSIDER, "428915")
    assert error.value.code == "FAMILY_DISABLED"


def test_missing_family_means_room_not_found(monkeypatch):
    _patch(monkeypatch, family={})

    with pytest.raises(BizError) as error:
        roomService.getRoomByCode(OUTSIDER, "428915")
    assert error.value.code == "ROOM_NOT_FOUND"

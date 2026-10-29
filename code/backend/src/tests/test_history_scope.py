"""S9：客队玩家的战绩口径（纯 monkeypatch，不依赖测试库）。

覆盖：
  1. 列表按 loginID 跨家庭查询（`crossFamily=True`），并带出家庭标识；
  2. 客队参与者能打开场次详情，且**不再**被家庭成员校验挡住；
  3. 非参与者、非该家庭管理员仍然 403。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import mysqlCommon  # noqa: E402
from common.bizCommon import BizError  # noqa: E402
from processor import familyService, historyService  # noqa: E402

HOME_FAMILY_ID = 5
OTHER_FAMILY_ID = 7
GUEST = "13800010001"
HOST = "13910710766"
STRANGER = "13800000099"

GAME_ROW = {
    "recID": 88,
    "familyID": OTHER_FAMILY_ID,
    "roomID": 15,
    "ruleFamilyCode": "generic",
    "ruleSnapshot": {"rule_family_code": "generic", "config": {}},
    "gameStatus": "FINISHED",
    "startedYMDHMS": "20261029120000",
    "endedYMDHMS": "20261029123000",
    "roomName": "周末家庭局",
    "ruleName": "家庭标准",
    "familyCode": "fam_3e7e",
    "familyName": "廉家",
    "myScore": -8,
}

PLAYERS = [
    {"gameID": 88, "seatNo": 0, "loginID": HOST, "displayName": "lianyi", "totalScore": 8},
    {"gameID": 88, "seatNo": 1, "loginID": GUEST, "displayName": "阿一", "totalScore": -8},
]

FAMILY_ROW = {"recID": OTHER_FAMILY_ID, "familyCode": "fam_3e7e", "familyName": "廉家"}


def _no_member_check(*_args, **_kwargs):
    raise AssertionError("客队参与者不应触发家庭成员校验")


def test_guest_sees_cross_family_game_in_list(monkeypatch):
    calls: dict[str, object] = {}

    monkeypatch.setattr(
        familyService,
        "assertMemberOfFamilyID",
        lambda loginID, familyID, requireEnabled=False: {"memberRole": "MEMBER"},
    )

    def fakeList(familyID, loginID="", limit=30, beforeID=0, crossFamily=False):
        calls["crossFamily"] = crossFamily
        calls["loginID"] = loginID
        return [dict(GAME_ROW)]

    monkeypatch.setattr(mysqlCommon, "query_mj_game_list", fakeList)
    monkeypatch.setattr(
        mysqlCommon,
        "query_mj_game_player_list_by_games",
        lambda ids: [dict(row) for row in PLAYERS],
    )

    games = historyService.listGames(GUEST, HOME_FAMILY_ID)

    assert calls["crossFamily"] is True
    assert calls["loginID"] == GUEST
    assert len(games) == 1
    assert games[0]["family_code"] == "fam_3e7e"
    assert games[0]["family_name"] == "廉家"
    assert games[0]["my_score"] == -8
    assert len(games[0]["players"]) == 2


def test_guest_can_open_game_detail(monkeypatch):
    monkeypatch.setattr(
        mysqlCommon,
        "query_mj_game_detail",
        lambda gameID: {
            "game": dict(GAME_ROW),
            "players": [dict(row) for row in PLAYERS],
            "rounds": [],
        },
    )
    monkeypatch.setattr(mysqlCommon, "query_mj_family_by_id", lambda familyID: dict(FAMILY_ROW))
    monkeypatch.setattr(familyService, "assertMemberOfFamilyID", _no_member_check)

    detail = historyService.gameDetail(GUEST, 88)

    assert detail["id"] == 88
    assert detail["family_code"] == "fam_3e7e"
    assert detail["family_name"] == "廉家"
    assert len(detail["players"]) == 2


def test_stranger_without_participation_is_forbidden(monkeypatch):
    monkeypatch.setattr(
        mysqlCommon,
        "query_mj_game_detail",
        lambda gameID: {
            "game": dict(GAME_ROW),
            "players": [dict(row) for row in PLAYERS],
            "rounds": [],
        },
    )
    monkeypatch.setattr(mysqlCommon, "query_mj_family_by_id", lambda familyID: dict(FAMILY_ROW))
    # 外家庭成员但不是参与者、也不是管理员
    monkeypatch.setattr(
        familyService,
        "assertMemberOfFamilyID",
        lambda loginID, familyID, requireEnabled=False: {"memberRole": "MEMBER"},
    )

    with pytest.raises(BizError) as error:
        historyService.gameDetail(STRANGER, 88)
    assert error.value.code == "FORBIDDEN"


def test_family_admin_can_open_game_detail(monkeypatch):
    monkeypatch.setattr(
        mysqlCommon,
        "query_mj_game_detail",
        lambda gameID: {
            "game": dict(GAME_ROW),
            "players": [dict(row) for row in PLAYERS],
            "rounds": [],
        },
    )
    monkeypatch.setattr(mysqlCommon, "query_mj_family_by_id", lambda familyID: dict(FAMILY_ROW))
    monkeypatch.setattr(
        familyService,
        "assertMemberOfFamilyID",
        lambda loginID, familyID, requireEnabled=False: {"memberRole": "ADMIN"},
    )

    detail = historyService.gameDetail(STRANGER, 88)
    assert detail["family_code"] == "fam_3e7e"

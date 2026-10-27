"""S5 数据层验收用例（真实测试库 mahjong_test）。

覆盖验收清单里可自动化断言的部分：
  1. 开桌失败（模板不存在）→ `mj_room` 无新增记录；
  2. 结算失败 → `mj_game_round` 与 `totalScore` 同时回滚（不半更新）；
  3. 战绩列表 SQL 次数与场次数无关（消除 N+1）；
  4. 聊天查询带 LIMIT；
  5. 进程重启口径：PLAYING → ABORTED；
  6. 规则模板 CRUD 与跨家庭隔离。
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import miscCommon as misc  # noqa: E402
from common import mysqlCommon  # noqa: E402
from common.bizCommon import BizError  # noqa: E402
from processor import historyService, roomService, ruleService  # noqa: E402
from realtime import persist  # noqa: E402

pytestmark = pytest.mark.usefixtures("s5_env")

OUTSIDER = "13800000009"


class HandleCounter:
    """给 mysqlCommon 的句柄套一层计数，用来断言 SQL 次数。"""

    def __init__(self, handle) -> None:
        self._handle = handle
        self.reads = 0
        self.writes = 0

    def executeRead(self, sqlstr, values=()):
        self.reads += 1
        return self._handle.executeRead(sqlstr, values)

    def executeWrite(self, sqlstr, values=()):
        self.writes += 1
        return self._handle.executeWrite(sqlstr, values)

    def __getattr__(self, name):
        return getattr(self._handle, name)


def _roomCount(familyID: int) -> int:
    rows = mysqlCommon.queryTableGeneral(
        mysqlCommon.MJ_ROOM_TABLE,
        condList=[["familyID", "=", familyID]],
        columns="recID",
        order="new",
        limitNum=100,
    )
    return len(rows)


def _createGame(s5_env, tag: str) -> int:
    seats = [
        (index, loginID, f"玩家{index}")
        for index, loginID in enumerate(s5_env["members"])
    ]
    return persist.open_game(
        s5_env["room"]["id"],
        s5_env["family_id"],
        "generic",
        {"rule_family_code": "generic", "config": {}},
        seats,
    )


def _settled(round_no: int, winner_seat: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        round_no=round_no,
        dealer_seat=0,
        winner_seat=winner_seat,
        win_type="discard",
        winning_tile=5,
        pattern_id="standard",
        fan_items=[{"id": "ping_hu", "name": "平胡", "fan": 1}],
        fan_total=2,
        fan_raw=2,
        score_delta=[-2, 6, -2, -2],
        payer_json=None,
    )


def _totals(gameID: int) -> dict[int, int]:
    rows = mysqlCommon.query_mj_game_player_list(gameID)
    return {int(row["seatNo"]): int(row["totalScore"]) for row in rows}


def _rounds(gameID: int) -> list[dict]:
    return mysqlCommon.queryTableGeneral(
        mysqlCommon.MJ_GAME_ROUND_TABLE,
        condList=[["gameID", "=", gameID]],
        columns="recID,roundNo,winnerSeat,fanTotal,scoreDeltaJson",
        order="create",
        limitNum=50,
    )


# ---------------------------------------------------------------- 1. 开桌失败不留记录


def test_create_room_with_missing_template_leaves_no_row(s5_env):
    before = _roomCount(s5_env["family_id"])
    with pytest.raises(BizError) as error:
        roomService.createRoom(
            s5_env["owner"], s5_env["family_id"], s5_env["family_code"], "失败房", 99999999
        )
    assert error.value.code == "TEMPLATE_NOT_FOUND"
    assert _roomCount(s5_env["family_id"]) == before


def test_create_room_rejects_other_family_template(s5_env):
    """跨家庭模板连「存在性」都不暴露；同样不落房。"""
    otherCode = "s5other"
    family = mysqlCommon.query_mj_family_by_code(otherCode)
    if not family:
        now = misc.getTime()
        otherFamilyID = mysqlCommon.insert_mj_family(
            mysqlCommon.MJ_FAMILY_TABLE,
            {
                "familyCode": otherCode,
                "familyName": "S5 别人家",
                "ownerLoginID": OUTSIDER,
                "familyStatus": "ENABLED",
                "sortOrder": 0,
                "regID": "pytest",
                "regYMDHMS": now,
                "delFlag": "0",
            },
        )
    else:
        otherFamilyID = int(family["recID"])

    existing = mysqlCommon.query_mj_rule_template_by_code("s5other_tpl")
    otherTemplate = int(existing.get("recID") or 0)
    if otherTemplate <= 0:
        now = misc.getTime()
        otherTemplate = mysqlCommon.insert_mj_rule_template(
            mysqlCommon.MJ_RULE_TEMPLATE_TABLE,
            {
                "templateCode": "s5other_tpl",
                "familyID": otherFamilyID,
                "ruleFamilyCode": "generic",
                "templateName": "别人家的模板",
                "description": "",
                "configJson": {},
                "presetFlag": "0",
                "ownerLoginID": OUTSIDER,
                "activeFlag": "1",
                "sortOrder": 10,
                "regID": "pytest",
                "regYMDHMS": now,
                "delFlag": "0",
            },
        )
    before = _roomCount(s5_env["family_id"])
    with pytest.raises(BizError) as error:
        roomService.createRoom(
            s5_env["owner"], s5_env["family_id"], s5_env["family_code"], "越权房", otherTemplate
        )
    assert error.value.code == "TEMPLATE_NOT_FOUND"
    assert _roomCount(s5_env["family_id"]) == before


# ---------------------------------------------------------------- 2. 结算事务


def test_save_round_is_atomic(s5_env):
    gameID = _createGame(s5_env, "atomic")
    persist.save_round(gameID, s5_env["family_id"], _settled(1))
    assert len(_rounds(gameID)) == 1
    assert _totals(gameID) == {0: -2, 1: 6, 2: -2, 3: -2}

    beforeRounds = len(_rounds(gameID))
    beforeTotals = _totals(gameID)

    def brokenScore(*_args, **_kwargs):
        return 0  # 模拟计分语句失败

    original = mysqlCommon.update_mj_game_player_score
    mysqlCommon.update_mj_game_player_score = brokenScore
    try:
        with pytest.raises(BizError):
            persist.save_round(gameID, s5_env["family_id"], _settled(2))
    finally:
        mysqlCommon.update_mj_game_player_score = original

    # 局记录与总分一起回滚：没有「多一局」也没有「分数先动」
    assert len(_rounds(gameID)) == beforeRounds
    assert _totals(gameID) == beforeTotals


def test_save_round_draw_keeps_winner_null(s5_env):
    gameID = _createGame(s5_env, "draw")
    draw = _settled(1, winner_seat=0)
    draw.winner_seat = None
    draw.win_type = "none"
    draw.winning_tile = None
    draw.score_delta = [0, 0, 0, 0]
    persist.save_round(gameID, s5_env["family_id"], draw)
    rows = _rounds(gameID)
    assert len(rows) == 1
    assert rows[0]["winnerSeat"] == ""  # NULL 出参归一为空串


# ---------------------------------------------------------------- 3. SQL 次数恒定


def test_history_list_sql_count_is_constant(s5_env, monkeypatch):
    loginID = s5_env["owner"]
    handle = mysqlCommon.mysqlDB

    first = _createGame(s5_env, "count1")
    persist.save_round(first, s5_env["family_id"], _settled(1))

    counterOne = HandleCounter(handle)
    monkeypatch.setattr(mysqlCommon, "mysqlDB", counterOne)
    gamesOne = historyService.listGames(loginID, s5_env["family_id"], limit=30)
    readsOne = counterOne.reads

    monkeypatch.setattr(mysqlCommon, "mysqlDB", handle)
    for _ in range(4):
        gameID = _createGame(s5_env, "count")
        persist.save_round(gameID, s5_env["family_id"], _settled(1))

    counterMany = HandleCounter(handle)
    monkeypatch.setattr(mysqlCommon, "mysqlDB", counterMany)
    gamesMany = historyService.listGames(loginID, s5_env["family_id"], limit=30)

    # 测试库可能已积累历史场次，两个列表都会被 limit=30 截断；这里只关心
    # 「本用例新增的 5 场都在」且「SQL 次数不随场次增长」。
    assert len(gamesMany) >= 5
    assert len(gamesMany) == len(gamesOne)
    # 成员校验 3 条 + 场次 1 条 + 参与者 1 条 = 5，与场次数无关
    assert counterMany.reads == readsOne
    assert counterMany.reads <= 6
    assert all(len(game["players"]) == 4 for game in gamesMany)


def test_history_pagination_uses_before_id(s5_env):
    """分页改 `recID < before_id`，不用 OFFSET：跨页不重不漏。"""
    loginID = s5_env["owner"]
    for _ in range(2):
        gameID = _createGame(s5_env, "page")
        persist.save_round(gameID, s5_env["family_id"], _settled(1))

    page1 = historyService.listGames(loginID, s5_env["family_id"], limit=2)
    assert len(page1) == 2
    cursor = page1[-1]["id"]
    page2 = historyService.listGames(loginID, s5_env["family_id"], limit=2, beforeID=cursor)
    assert page2
    assert all(game["id"] < cursor for game in page2)
    assert not ({game["id"] for game in page1} & {game["id"] for game in page2})


# ---------------------------------------------------------------- 4. 聊天 LIMIT


def test_chat_query_has_limit(s5_env):
    roomID = s5_env["room"]["id"]
    for index in range(5):
        persist.save_message(roomID, s5_env["family_id"], s5_env["owner"], "chat", f"第{index}条")
    rows = mysqlCommon.query_mj_room_message_list(roomID, limit=2)
    assert len(rows) == 2
    # 倒序取最近 2 条；调用方（REST/WS）再 reverse 成正序
    assert rows[0]["content"] == "第4条"
    assert rows[1]["content"] == "第3条"


# ---------------------------------------------------------------- 5. 重启中断


def test_abort_playing_games_marks_aborted(s5_env):
    gameID = _createGame(s5_env, "restart")
    assert mysqlCommon.query_mj_game_by_id(gameID)["gameStatus"] == "PLAYING"

    affected = mysqlCommon.update_mj_game_abort_playing()
    assert affected >= 1
    game = mysqlCommon.query_mj_game_by_id(gameID)
    assert game["gameStatus"] == "ABORTED"
    assert game["endedYMDHMS"] != ""


# ---------------------------------------------------------------- 6. 规则模板


def test_rule_template_crud_and_isolation(s5_env):
    owner = s5_env["owner"]
    created = ruleService.createTemplate(
        owner,
        s5_env["family_id"],
        s5_env["family_code"],
        "generic",
        "S5 自定义",
        "测试用",
        {"base_score": 2},
    )
    assert created["family_code"] == s5_env["family_code"]
    assert created["is_preset"] is False
    assert created["config"]["base_score"] == 2

    updated = ruleService.updateTemplate(
        owner, created["id"], templateName="S5 改名", activeFlag=False
    )
    assert updated["template_name"] == "S5 改名"
    assert updated["is_active"] is False

    duplicated = ruleService.duplicateTemplate(
        owner, s5_env["template_id"], s5_env["family_id"], s5_env["family_code"], "预置副本"
    )
    assert duplicated["template_name"] == "预置副本"
    assert duplicated["is_preset"] is False
    assert duplicated["config"] == ruleService.getTemplate(owner, s5_env["template_id"])["config"]

    # 预置模板只读
    with pytest.raises(BizError) as error:
        ruleService.updateTemplate(owner, s5_env["template_id"], templateName="不能改")
    assert error.value.httpStatus == 400

    # 非成员看不到也改不了别人家的模板
    from processor import accountService

    accountService.ensureUserBasic(OUTSIDER)
    with pytest.raises(BizError) as error:
        ruleService.getTemplate(OUTSIDER, created["id"])
    assert error.value.code == "NOT_FAMILY_MEMBER"

    # 能力校验：不存在的族
    with pytest.raises(BizError) as error:
        ruleService.createTemplate(
            owner, s5_env["family_id"], s5_env["family_code"], "no_such_family", "x", "", {}
        )
    assert error.value.code == "RULE_FAMILY_NOT_FOUND"


def test_room_open_requires_ready_family(s5_env):
    """未就绪的族（sichuan / baishi 尚未接入引擎）不允许开桌，且不落房。"""
    family = mysqlCommon.query_mj_rule_family_by_code("baishi")
    assert family, "种子应包含 baishi 族"
    assert ruleService.isReady(family) is False

    existing = mysqlCommon.query_mj_rule_template_by_code("s5_baishi_probe")
    templateID = int(existing.get("recID") or 0)
    if templateID <= 0:
        now = misc.getTime()
        templateID = mysqlCommon.insert_mj_rule_template(
            mysqlCommon.MJ_RULE_TEMPLATE_TABLE,
            {
                "templateCode": "s5_baishi_probe",
                "familyID": s5_env["family_id"],
                "ruleFamilyCode": "baishi",
                "templateName": "柏氏探针",
                "description": "",
                "configJson": {},
                "presetFlag": "0",
                "ownerLoginID": s5_env["owner"],
                "activeFlag": "1",
                "sortOrder": 90,
                "regID": "pytest",
                "regYMDHMS": now,
                "delFlag": "0",
            },
        )
    before = _roomCount(s5_env["family_id"])
    with pytest.raises(BizError) as error:
        roomService.createRoom(
            s5_env["owner"], s5_env["family_id"], s5_env["family_code"], "柏氏房", templateID
        )
    assert error.value.code == "RULE_FAMILY_NOT_READY"
    assert _roomCount(s5_env["family_id"]) == before

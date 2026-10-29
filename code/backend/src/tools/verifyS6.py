"""S6 验收脚本：规则族等价迁移 + 对局流程（抽座/发牌/荒庄）+ 能力校验。

对真实代码 + 真实测试库 `mahjong_test` 跑，不 mock：
  1. 注册表自检：每族的 patterns 已注册、tile_set 可建墙、capability 必备字段齐全；
  2. 预置模板逐字段对比（旧 config ↔ 新 config ↔ 库内行）；
  3. 发牌：同一 seed 下庄家 14 / 闲家各 13，跳牌取第 1、第 5 张；
  4. 抽座与轮庄：每圈抽一次、第 n 局庄家=座位 n-1、局风东南西北；
  5. REST：未知字段 / 族外开关 → 400，未知族 → 404，合法配置 → 200；
  6. 快照不可变：改了模板，已开桌房间的 `mj_room.ruleSnapshot` 与 `mj_game.ruleSnapshot` 不变。

用法（工作目录 = code/backend/src）：
    python tools/verifyS6.py
前置：测试库可连（.env 的 MYSQL_*），表已建好且灌过种子（tools/initTables.py --env test_server --seed）。
"""

import json
import os
import random
import sys

_SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _SRC_DIR)

# 必须在导入 config.* 之前锁定测试库：绝不写开发/生产库
os.environ["APP_ENV"] = "test_server"
os.environ["MYSQL_WRITE_DB"] = "mahjong_test"
os.environ["MYSQL_READ_DB"] = "mahjong_test"
os.environ.setdefault("SECRET_KEY", "s6-verify-only-secret")

from fastapi.testclient import TestClient  # noqa: E402

from common import mysqlCommon  # noqa: E402
from common.securityCommon import create_access_token  # noqa: E402
from game.engine import dealer_of_round, draw_seats, round_wind_of  # noqa: E402
from game.families import registry  # noqa: E402
from game.families.generic.config import RuleConfig  # noqa: E402
from game.tiles import new_wall  # noqa: E402
from main.app import app  # noqa: E402
from processor import roomService  # noqa: E402
from tools.comparePresets import compareDb, compareFiles  # noqa: E402
from tools.seedPresets import installPresets  # noqa: E402
from tools.verifyS5 import MEMBERS, OWNER, ensureEnv  # noqa: E402


class Report:
    def __init__(self) -> None:
        self.failed = 0

    def ok(self, label: str, detail: str = "") -> None:
        print(f"  [OK  ] {label}{('：' + detail) if detail else ''}")

    def fail(self, label: str, detail: str = "") -> None:
        self.failed += 1
        print(f"  [FAIL] {label}{('：' + detail) if detail else ''}")

    def check(self, condition: bool, label: str, detail: str = "") -> None:
        if condition:
            self.ok(label, detail)
        else:
            self.fail(label, detail)


def authHeaders(loginID: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token(loginID, 'member')}"}


# ---------------------------------------------------------------- 1. 注册表


def checkRegistry(report: Report) -> None:
    print("== 1. 规则族注册表自检（导入期已完成）==")
    codes = registry.registered_codes()
    report.check("generic" in codes and "guangdong" in codes, "已注册族", ",".join(codes))
    for plugin in registry.all_families():
        ready, issues = registry.is_ready(plugin.rule_family_code, plugin.capability)
        report.check(ready, f"{plugin.rule_family_code} ready", "；".join(issues) or "capability 自检通过")
        missing = [
            item
            for item in plugin.capability.get("patterns", [])
            if item not in registry.registered_ids()
        ]
        report.check(not missing, f"{plugin.rule_family_code} patterns 均已注册", ",".join(missing))

    ready, issues = registry.is_ready("sichuan")
    report.check(not ready, "未注册族不可开桌", "；".join(issues))
    broken = {**registry.capability_of("generic"), "patterns": ["standard", "no_such_pattern"]}
    ready, _ = registry.is_ready("generic", broken)
    report.check(not ready, "capability 含未注册牌型 → ready=false")


# ---------------------------------------------------------------- 2. 预置模板


def checkPresets(report: Report) -> None:
    print("== 2. 预置模板逐字段对比（基线 tests/fixtures/legacy_presets.json）==")
    ok, lines = compareFiles()
    for line in lines:
        print("    " + line.strip())
    report.check(ok, "4 套预置模板与 S6 之前逐字段一致")

    dbOk, dbLines = compareDb()
    for line in dbLines:
        print("    " + line.strip())
    report.check(dbOk, "库内预置模板行与新 config 一致")


# ---------------------------------------------------------------- 3. 发牌


def checkDeal(report: Report) -> None:
    print("== 3. 发牌（03 §3.5）==")
    seed = 20261028
    seats = registry.create_engine("generic", RuleConfig(), _dummySeats(), rng=random.Random(seed))
    events = seats.start_round()
    deal = events[0]["data"]["deal"]

    rng = random.Random(seed)
    wall = new_wall(rng, "136")
    dice = [rng.randint(1, 6), rng.randint(1, 6)]
    total = dice[0] + dice[1]
    breakSeat = (seats.dealer_seat + total - 1) % 4
    offset = max(0, 17 - total) * 2
    head = wall[breakSeat * 34 : (breakSeat + 1) * 34]
    sequence = head[offset:] + head[:offset]
    for step in range(1, 4):
        left = ((breakSeat + step) % 4) * 34
        sequence.extend(wall[left : left + 34])
    jump = sequence[48:53]

    report.check(deal["dice"] == dice, "掷骰结果", str(dice))
    report.check(deal["break_seat"] == breakSeat, "开牌家", str(breakSeat))
    report.check(deal["break_stack"] == total, "开牌墩数", str(total))

    counts = [sum(seats.seats[seat].counts) for seat in range(4)]
    report.check(counts[0] == 14, "庄家手牌", str(counts[0]))
    report.check(counts[1:] == [13, 13, 13], "闲家手牌", str(counts[1:]))
    report.check(seats.seats[0].counts[jump[0]] >= 1, "跳牌第 1 张归庄家")
    report.check(seats.seats[0].counts[jump[4]] >= 1, "跳牌第 5 张归庄家")
    report.check(
        all(seats.seats[seat].counts[jump[index]] >= 1 for index, seat in enumerate((1, 2, 3), 1)),
        "跳牌第 2/3/4 张依次给下家/对家/上家",
    )
    report.check(seats.phase == "discard" and seats.turn == seats.dealer_seat, "首轮庄家直接出牌")
    report.check(seats.remaining == 136 - 53, "牌墙余量", str(seats.remaining))


def _dummySeats():
    from game.engine import SeatState

    return [
        SeatState(seat=index, login_id=f"1380000000{index}", display_name=f"玩家{index}", color="#C9A063")
        for index in range(4)
    ]


# ---------------------------------------------------------------- 4. 抽座与轮庄


def checkSeatsAndRounds(report: Report) -> None:
    print("== 4. 抽座与轮庄（03 §3.4）==")
    logins = [loginID for loginID, _nick in MEMBERS]
    draw = draw_seats(logins, random.Random(4242))
    assignments = draw["assignments"]
    report.check(draw["dealer_seat"] == 0, "庄家坐东位（座位 0）", str(draw["dealer_seat"]))
    report.check(
        sorted(entry["seat"] for entry in assignments) == [0, 1, 2, 3]
        and {entry["login_id"] for entry in assignments} == set(logins),
        "四家各占一个座位",
        json.dumps([{k: entry[k] for k in ("seat", "dice")} for entry in assignments], ensure_ascii=False),
    )
    report.check(
        draw == draw_seats(logins, random.Random(4242)), "同 seed 可复现"
    )

    dealers = [dealer_of_round(n) for n in (1, 2, 3, 4)]
    winds = [round_wind_of(n) for n in (1, 2, 3, 4)]
    report.check(dealers == [0, 1, 2, 3], "第 n 局庄家 = 座位 n-1", str(dealers))
    report.check(winds == [0, 1, 2, 3], "局风 东→南→西→北", str(winds))

    engine = registry.create_engine("generic", RuleConfig(), _dummySeats(), round_no=4)
    report.check(
        engine.dealer_seat == 3 and engine.next_dealer() == 0, "北位庄家下庄即圈结束", "座位 3 → 座位 0"
    )


# ---------------------------------------------------------------- 5. REST 校验


def checkApi(report: Report, env: dict) -> None:
    print("== 5. 模板接口的族能力校验（04 §5 / §10）==")
    client = TestClient(app)
    headers = authHeaders(OWNER)
    familyCode = env["family_code"]

    good = RuleConfig().model_dump()

    response = client.post(
        "/api/rules",
        headers=headers,
        json={
            "family_code": familyCode,
            "rule_family_code": "generic",
            "template_name": "S6 未知字段",
            "config": {**good, "no_such_field": 1},
        },
    )
    report.check(
        response.status_code == 400 and response.json().get("code") == "RULE_CONFIG_INVALID",
        "未知字段 → 400 RULE_CONFIG_INVALID",
        f"{response.status_code} {response.json().get('code')}",
    )

    response = client.post(
        "/api/rules",
        headers=headers,
        json={
            "family_code": familyCode,
            "rule_family_code": "generic",
            "template_name": "S6 族外开关",
            "config": {**good, "pause": {"enabled": True}},
        },
    )
    report.check(
        response.status_code == 400,
        "族外开关（pause）→ 400",
        f"{response.status_code} {response.json().get('code')}（pause 不在通用族白名单内）",
    )

    response = client.post(
        "/api/rules",
        headers=headers,
        json={
            "family_code": familyCode,
            "rule_family_code": "no_such_family",
            "template_name": "S6 未知族",
            "config": good,
        },
    )
    report.check(
        response.status_code == 404 and response.json().get("code") == "RULE_FAMILY_NOT_FOUND",
        "未知族 → 404 RULE_FAMILY_NOT_FOUND",
        f"{response.status_code} {response.json().get('code')}",
    )

    response = client.post(
        "/api/rules/validate",
        headers=headers,
        json={"rule_family_code": "generic", "config": {**good, "base_score": 999}},
    )
    payload = response.json()
    report.check(
        response.status_code == 200
        and payload.get("ok") is False
        and payload.get("code") == "RULE_BASE_SCORE_INVALID",
        "试算接口：底分越界 → ok=false + RULE_BASE_SCORE_INVALID",
        f"{response.status_code} {payload.get('code')}",
    )

    response = client.post(
        "/api/rules",
        headers=headers,
        json={
            "family_code": familyCode,
            "rule_family_code": "generic",
            "template_name": "S6 合法模板",
            "config": good,
        },
    )
    body = response.json()
    report.check(response.status_code == 200, "合法配置 → 200", f"id={body.get('id')}")
    return body.get("id")


# ---------------------------------------------------------------- 6. 快照不可变


def checkSnapshot(report: Report, env: dict, templateID: int | None) -> None:
    print("== 6. 模板 → 快照不可变（03 §11）==")
    if not templateID:
        report.fail("快照不可变", "上一步没拿到模板 id")
        return
    client = TestClient(app)
    headers = authHeaders(OWNER)
    familyID = env["family_id"]
    familyCode = env["family_code"]

    room = roomService.createRoom(OWNER, familyID, familyCode, "S6 快照房", templateID)
    snapshot = mysqlCommon.query_mj_room_by_id(room["id"])["ruleSnapshot"]
    report.check(snapshot["engine_code"] == "generic", "房间快照含 engine_code", snapshot["engine_code"])
    report.check(bool(snapshot.get("captured_ymdhms")), "房间快照含 captured_ymdhms")
    baseScore = snapshot["config"]["base_score"]

    response = client.put(
        f"/api/rules/{templateID}",
        headers=headers,
        json={"config": {**snapshot["config"], "base_score": baseScore + 4}},
    )
    report.check(response.status_code == 200, "模板可以改", f"base_score={baseScore + 4}")
    after = mysqlCommon.query_mj_room_by_id(room["id"])["ruleSnapshot"]
    report.check(
        after["config"]["base_score"] == baseScore, "改模板不影响已开桌房间的快照", f"base_score={after['config']['base_score']}"
    )
    report.check(after == snapshot, "房间快照整体未变")

    # 开局写入 mj_game 的必须是同一份开桌快照
    from realtime import persist

    gameID = persist.open_game(
        room["id"],
        familyID,
        "generic",
        snapshot,
        [(index, loginID, nick) for index, (loginID, nick) in enumerate(MEMBERS)],
        {"dealer_seat": 0, "assignments": []},
    )
    game = mysqlCommon.query_mj_game_by_id(gameID)
    report.check(game["ruleSnapshot"] == snapshot, "mj_game 快照 = mj_room 快照")
    mysqlCommon.update_mj_game_status(gameID, "FINISHED")
    mysqlCommon.delete_mj_soft(mysqlCommon.MJ_ROOM_TABLE, room["id"], "verifyS6")


def main() -> int:
    report = Report()
    installPresets()
    env = ensureEnv()
    env["family_code"] = "s5test"

    checkRegistry(report)
    checkPresets(report)
    checkDeal(report)
    checkSeatsAndRounds(report)
    templateID = checkApi(report, env)
    checkSnapshot(report, env, templateID)

    print("RESULT:", "PASS" if report.failed == 0 else f"FAIL({report.failed})")
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

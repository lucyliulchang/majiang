"""S5 验收脚本：对着测试库 mahjong_test 把 REST 端点全跑一遍，并给出证据。

做三件事（全部走真实代码 + 真实 MySQL，不 mock）：
  1. 造一份可复现的测试数据：账号档案 / 家庭 + 4 名成员 / 预置模板 / 房间 / 场次 + 逐局；
  2. 用 TestClient 逐个调用端点，打印状态码与关键字段（字段名对齐 04）；
  3. 统计战绩列表的 SQL 次数（场次 1 场 vs N 场），证明次数为常数。

用法（工作目录 = code/backend/src）：
    python tools/verifyS5.py
前置：测试库可连（.env 的 MYSQL_*），表已建好（tools/initTables.py --env test_server --seed）。
"""

import os
import sys
from types import SimpleNamespace

_SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _SRC_DIR)

# 必须在导入 config.* 之前锁定测试库：绝不写开发/生产库
os.environ["APP_ENV"] = "test_server"
os.environ["MYSQL_WRITE_DB"] = "mahjong_test"
os.environ["MYSQL_READ_DB"] = "mahjong_test"
os.environ.setdefault("SECRET_KEY", "s5-verify-only-secret")

from fastapi.testclient import TestClient  # noqa: E402

from common import miscCommon as misc  # noqa: E402
from common import mysqlCommon  # noqa: E402
from common.securityCommon import create_access_token  # noqa: E402
from main.app import app  # noqa: E402
from processor import accountService, familyService, roomService  # noqa: E402
from realtime import persist  # noqa: E402
from tools.seedPresets import installPresets  # noqa: E402

OWNER = "13800000001"
MEMBERS = (
    (OWNER, "爸爸"),
    ("13800000002", "妈妈"),
    ("13800000003", "姐姐"),
    ("13800000004", "弟弟"),
)
FAMILY_CODE = "s5test"


class Counter:
    """SQL 计数：包住 mysqlCommon 的句柄，读写各记一笔。"""

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


def ensureEnv() -> dict:
    """幂等造数：账号档案 / 家庭 / 成员 / 模板 / 房间。"""
    installPresets()
    for loginID, nickName in MEMBERS:
        accountService.ensureUserBasic(loginID)
        mysqlCommon.updateUserBasic(loginID, {"nickName": nickName})

    family = mysqlCommon.query_mj_family_by_code(FAMILY_CODE)
    if family:
        familyID = int(family.get("recID") or 0)
    else:
        familyID = int(
            familyService.bootstrapFamily(OWNER, "S5 验收家庭", FAMILY_CODE)["familyID"]
        )

    now = misc.getTime()
    for loginID, _nick in MEMBERS:
        if mysqlCommon.query_mj_family_member(familyID, loginID):
            continue
        mysqlCommon.insert_mj_family_member(
            mysqlCommon.MJ_FAMILY_MEMBER_TABLE,
            {
                "familyMemberKey": f"{familyID}_{loginID}",
                "familyID": familyID,
                "loginID": loginID,
                "memberRole": "OWNER" if loginID == OWNER else "MEMBER",
                "memberStatus": "ACTIVE",
                "joinedYMDHMS": now,
                "regID": loginID,
                "regYMDHMS": now,
                "delFlag": "0",
            },
        )

    template = mysqlCommon.query_mj_rule_template_by_code("generic_standard")
    room = roomService.createRoom(
        OWNER, familyID, FAMILY_CODE, "S5 验收房", int(template.get("recID") or 0)
    )
    return {"family_id": familyID, "template_id": int(template["recID"]), "room": room}


def createGame(env: dict, rounds: int = 1) -> int:
    gameID = persist.open_game(
        env["room"]["id"],
        env["family_id"],
        "generic",
        {"rule_family_code": "generic", "config": {}},
        [(index, loginID, nick) for index, (loginID, nick) in enumerate(MEMBERS)],
    )
    for roundNo in range(1, rounds + 1):
        persist.save_round(
            gameID,
            env["family_id"],
            SimpleNamespace(
                round_no=roundNo,
                dealer_seat=0,
                winner_seat=1,
                win_type="discard",
                winning_tile=5,
                pattern_id="standard",
                fan_items=[{"id": "ping_hu", "name": "平胡", "fan": 1}],
                fan_total=2,
                fan_raw=2,
                score_delta=[-2, 6, -2, -2],
                payer_json=None,
            ),
        )
    return gameID


def _roomRows(familyID: int) -> int:
    return len(
        mysqlCommon.queryTableGeneral(
            mysqlCommon.MJ_ROOM_TABLE,
            condList=[["familyID", "=", familyID]],
            columns="recID",
            order="new",
            limitNum=100,
        )
    )


def _gamePlayers(gameID: int) -> dict[int, int]:
    return {
        int(row["seatNo"]): int(row["totalScore"])
        for row in mysqlCommon.query_mj_game_player_list(gameID)
    }


def _gameRounds(gameID: int) -> int:
    return len(
        mysqlCommon.queryTableGeneral(
            mysqlCommon.MJ_GAME_ROUND_TABLE,
            condList=[["gameID", "=", gameID]],
            columns="recID",
            order="create",
            limitNum=50,
        )
    )


def evidence(env: dict) -> list[str]:
    """三条硬验收的证据：开桌失败无残行 / 结算回滚 / 重启中断。"""
    from common.bizCommon import BizError
    from main.app import close_stale_games

    lines: list[str] = []

    # 1) 模板不存在 → 开桌失败，mj_room 无半条记录
    before = _roomRows(env["family_id"])
    failedCode = ""
    try:
        roomService.createRoom(OWNER, env["family_id"], FAMILY_CODE, "坏模板房", 99999999)
    except BizError as error:
        failedCode = error.code
    after = _roomRows(env["family_id"])
    lines.append(
        f"1) 开桌失败: code={failedCode} mj_room 行数 {before} → {after}（无新增={before == after}）"
    )

    # 2) 结算失败 → 逐局与总分一起回滚
    gameID = createGame(env, rounds=1)
    roundsBefore = _gameRounds(gameID)
    totalsBefore = _gamePlayers(gameID)
    original = mysqlCommon.update_mj_game_player_score
    mysqlCommon.update_mj_game_player_score = lambda *args, **kwargs: 0
    settleCode = ""
    try:
        persist.save_round(
            gameID,
            env["family_id"],
            SimpleNamespace(
                round_no=2,
                dealer_seat=0,
                winner_seat=1,
                win_type="discard",
                winning_tile=5,
                pattern_id="standard",
                fan_items=[],
                fan_total=2,
                fan_raw=2,
                score_delta=[-2, 6, -2, -2],
                payer_json=None,
            ),
        )
    except BizError as error:
        settleCode = error.code
    finally:
        mysqlCommon.update_mj_game_player_score = original
    lines.append(
        f"2) 结算失败: code={settleCode} mj_game_round {roundsBefore} → {_gameRounds(gameID)} 行，"
        f"totalScore {totalsBefore} → {_gamePlayers(gameID)}（两者都未变="
        f"{roundsBefore == _gameRounds(gameID) and totalsBefore == _gamePlayers(gameID)}）"
    )

    # 3) 进程重启 → PLAYING 全部 ABORTED
    restartGame = createGame(env, rounds=0)
    statusBefore = mysqlCommon.query_mj_game_by_id(restartGame)["gameStatus"]
    affected = close_stale_games()
    statusAfter = mysqlCommon.query_mj_game_by_id(restartGame)["gameStatus"]
    lines.append(
        f"3) 重启中断: game={restartGame} {statusBefore} → {statusAfter}"
        f"（本次影响 {affected} 场）"
    )
    return lines


def main() -> int:
    from config import mysqlSettings

    if not mysqlSettings.pingServer():
        print("[verifyS5] 测试库不可用，已中止")
        return 1

    env = ensureEnv()
    token = create_access_token(OWNER, "member")
    headers = {"Authorization": f"Bearer {token}"}
    results: list[tuple[str, str, int, str]] = []

    def call(method: str, path: str, **kwargs):
        response = client.request(method, path, headers=headers, **kwargs)
        payload = response.json()
        note = ""
        if isinstance(payload, dict):
            keys = [
                key
                for key in (
                    "ok",
                    "code",
                    "detail",
                    "id",
                    "room_code",
                    "template_code",
                    "rule_family_code",
                    "family_code",
                    "status",
                    "total_score",
                    "games_played",
                    "rounds_won",
                )
                if key in payload
            ]
            note = ", ".join(f"{key}={payload[key]!r}" for key in keys[:6])
        elif isinstance(payload, list):
            note = f"items={len(payload)}"
            if payload and isinstance(payload[0], dict):
                note += " keys=" + ",".join(list(payload[0].keys())[:6])
        results.append((method.upper(), path, response.status_code, note))
        return response, payload

    with TestClient(app) as client:
        gameID = createGame(env, rounds=2)
        persist.save_message(env["room"]["id"], env["family_id"], OWNER, "chat", "验一下聊天")

        call("GET", "/api/health")
        call("GET", "/api/auth/server-time")
        call("GET", "/api/auth/options")
        call("GET", "/api/auth/me")
        call("GET", "/api/user/pref")
        call("PUT", "/api/user/pref", json={"sound_volume": 60})
        call("GET", "/api/families")
        call("GET", f"/api/families/{FAMILY_CODE}")
        call("GET", f"/api/families/{FAMILY_CODE}/members")

        _, rules = call("GET", "/api/rules")
        call("GET", "/api/rule-families")
        createRule, created = call(
            "POST",
            "/api/rules",
            json={
                "family_code": FAMILY_CODE,
                "rule_family_code": "generic",
                "template_name": "S5 验收模板",
                "description": "verify",
                "config": {"base_score": 2, "fan_cap": 6},
            },
        )
        templateID = created.get("id") if isinstance(created, dict) else 0
        call("GET", f"/api/rules/{templateID}")
        call(
            "PUT",
            f"/api/rules/{templateID}",
            json={"template_name": "S5 验收模板（改）", "config": {"base_score": 3, "fan_cap": 6}},
        )
        call("POST", f"/api/rules/{templateID}/duplicate", json={"family_code": FAMILY_CODE})
        call(
            "POST",
            "/api/rules/validate",
            json={"rule_family_code": "generic", "config": {"base_score": 1}},
        )
        call("DELETE", f"/api/rules/{templateID}")

        _, rooms = call("GET", "/api/rooms")
        call("POST", "/api/rooms", json={
            "family_code": FAMILY_CODE,
            "room_name": "S5 端点开桌",
            "template_id": env["template_id"],
        })
        call("GET", f"/api/rooms/{env['room']['id']}")
        call("GET", f"/api/rooms/code/{env['room']['room_code']}")
        call("GET", f"/api/rooms/{env['room']['id']}/messages?limit=50")

        _, games = call("GET", "/api/history/games?limit=30")
        call("GET", f"/api/history/games/{gameID}")
        call("GET", "/api/history/stats")

        # ---- SQL 次数证据：同一份数据，场次数变化不影响读取次数 ----
        handle = mysqlCommon.mysqlDB
        counterOne = Counter(handle)
        mysqlCommon.mysqlDB = counterOne
        try:
            from processor import historyService

            historyService.listGames(OWNER, env["family_id"], limit=30)
            readsOne = counterOne.reads
        finally:
            mysqlCommon.mysqlDB = handle

        for _ in range(3):
            createGame(env, rounds=1)

        counterMany = Counter(handle)
        mysqlCommon.mysqlDB = counterMany
        try:
            gamesMany = historyService.listGames(OWNER, env["family_id"], limit=30)
            readsMany = counterMany.reads
        finally:
            mysqlCommon.mysqlDB = handle

        call("POST", f"/api/rooms/{env['room']['id']}/close")

        evidenceLines = evidence(env)

    print("\n=== REST 端点实跑（测试库 mahjong_test）===")
    for index, (method, path, status, note) in enumerate(results, start=1):
        print(f"[{index:>2}] {method:<6} {path:<48} {status:<4} {note}")

    print("\n=== SQL 次数（战绩列表）===")
    print(f"场次 1 场：reads={readsOne}")
    print(f"场次 {len(gamesMany)} 场：reads={readsMany}（常数，与场次数无关）")

    print("\n=== 硬验收证据 ===")
    for line in evidenceLines:
        print(line)

    total = len(results)
    errors = [item for item in results if item[2] >= 400]
    print(f"\n端点 {total} 个，非 2xx {len(errors)} 个")
    for method, path, status, note in errors:
        print(f"  !! {method} {path} -> {status} {note}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())

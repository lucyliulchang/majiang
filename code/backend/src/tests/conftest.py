"""测试公用：手牌解析、引擎构造与测试库指针。

手牌写法：123m 456p 789s 11z
- m 万 / p 筒 / s 条 / z 字（1z=东 … 7z=白）

数据层（S5）：**不再有 SQLite / ORM**，DB 相关用例直连测试库 `mahjong_test`
（02 §6.3：建库建表用 `python tools/initTables.py --env test_server --seed`）。
库不可用时由 `mysql_ready` fixture 跳过相关用例，引擎与纯函数用例照常跑。
"""

import os
import sys
from pathlib import Path

import pytest

_SRC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SRC_DIR))

# 必须在导入 config.* 之前设置：测试库独立，绝不动开发/生产数据。
# mysqlSettings 用 override=False 读 .env，因此这里的值优先于 .env 的 mahjong_data。
os.environ["APP_ENV"] = "test_server"
os.environ["MYSQL_WRITE_DB"] = "mahjong_test"
os.environ["MYSQL_READ_DB"] = "mahjong_test"
os.environ.setdefault("SECRET_KEY", "test-only-secret")
# 账号服务不参与单测：用例里 monkeypatch common/accountClient，禁止任何真实出网
os.environ.setdefault("ACCOUNT_SERVICE_URL", "http://127.0.0.1:1/acis")

from game.engine import GameEngine, SeatState  # noqa: E402
from game.families import registry  # noqa: E402
from game.families.generic.config import RuleConfig  # noqa: E402

_SUITS = {"m": 0, "p": 1, "s": 2}


def parse_hand(text: str) -> list[int]:
    tiles: list[int] = []
    pending: list[int] = []
    for char in text:
        if char.isdigit():
            pending.append(int(char))
            continue
        if char in " ,":
            pending.clear()
            continue
        if char in _SUITS:
            base = _SUITS[char]
            tiles.extend(base * 9 + number - 1 for number in pending)
            pending.clear()
        elif char == "z":
            tiles.extend(27 + number - 1 for number in pending)
            pending.clear()
        else:
            raise ValueError(f"看不懂的牌面写法：{char}")
    return tiles


def make_engine(
    rule: RuleConfig | None = None,
    dealer_seat: int | None = None,
    round_no: int = 1,
    rng=None,
    circle_no: int = 1,
) -> GameEngine:
    """从族注册表取 `generic` 引擎（S6 起测试不再直接 new 骨架类）。

    `dealer_seat` 缺省时由局号推导（第 n 局庄家 = 座位 n-1，03 §3.4）；
    `circle_no` 为 v1.1.0 的圈序（一圈 4 个庄次）。
    """
    seats = [
        SeatState(seat=i, login_id=f"1380000000{i}", display_name=f"玩家{i}", color="#C9A063")
        for i in range(4)
    ]
    return registry.create_engine(
        "generic",
        rule or RuleConfig(),
        seats,
        round_no=round_no,
        dealer_seat=dealer_seat,
        circle_no=circle_no,
        rng=rng,
    )


@pytest.fixture
def hand():
    return parse_hand


@pytest.fixture
def engine_factory():
    return make_engine


@pytest.fixture(scope="session")
def mysql_ready():
    """测试库可用性闸门：不可用时跳过该用例，而不是让整个测试集报连接错误。"""
    from config import mysqlSettings

    if mysqlSettings.dbW is None or not mysqlSettings.pingServer():
        pytest.skip(
            "测试库 mahjong_test 不可用：先建库建表 "
            "`python tools/initTables.py --env test_server --seed`"
        )
    return mysqlSettings


# S5 数据层用例的固定账号（loginID 即账号服务的登录号）
S5_OWNER = "13800000001"
S5_MEMBERS = (
    (S5_OWNER, "爸爸"),
    ("13800000002", "妈妈"),
    ("13800000003", "姐姐"),
    ("13800000004", "弟弟"),
)
S5_FAMILY_CODE = "s5test"


def ensureS5RoomOpen(s5_env) -> dict:
    """保证会话级共享房处于 OPEN。

    v1.1.0（I1）起「打满一圈 / 结束牌局」会把房真正落库 CLOSED，
    而 `s5_env` 是 session 级、被多个测试模块复用：一旦某个用例把房收掉，
    后续模块就会拿到已关的房间（`getRoomByCode` → ROOM_CLOSED、
    WS 握手 → ROOM_NOT_FOUND），这属于用例间污染而不是产品缺陷。
    这里在用例开始前补开一张新房并回写到 `s5_env`，用例内部仍可自行关房。
    """
    from common import mysqlCommon
    from processor import roomService

    room = s5_env["room"]
    row = mysqlCommon.query_mj_room_by_id(room["id"])
    if row and str(row.get("roomStatus") or "").upper() != "CLOSED":
        return room
    newRoom = roomService.createRoom(
        s5_env["owner"],
        s5_env["family_id"],
        s5_env["family_code"],
        room.get("room_name") or "S5 测试房",
        s5_env["template_id"],
    )
    s5_env["room"] = newRoom
    return newRoom


@pytest.fixture(scope="session")
def s5_env(mysql_ready):
    """真实测试库环境：账号档案 + 家庭 + 4 名成员 + 预置模板 + 一个 OPEN 房间。

    全部走业务代码（familyService / roomService / 种子），因此这里验证的是真实 SQL；
    结束只软删本次创建的房间，家庭与账号档案保留（幂等复用）。
    """
    from common import miscCommon as misc
    from common import mysqlCommon
    from processor import accountService, familyService, roomService
    from tools.seedPresets import installPresets

    installPresets()

    for loginID, nickName in S5_MEMBERS:
        accountService.ensureUserBasic(loginID)
        mysqlCommon.updateUserBasic(loginID, {"nickName": nickName})

    family = mysqlCommon.query_mj_family_by_code(S5_FAMILY_CODE)
    if family:
        familyID = int(family.get("recID") or 0)
    else:
        familyID = int(
            familyService.bootstrapFamily(S5_OWNER, "S5 测试家庭", S5_FAMILY_CODE)["familyID"]
        )

    now = misc.getTime()
    for loginID, _nickName in S5_MEMBERS:
        if mysqlCommon.query_mj_family_member(familyID, loginID):
            continue
        mysqlCommon.insert_mj_family_member(
            mysqlCommon.MJ_FAMILY_MEMBER_TABLE,
            {
                "familyMemberKey": f"{familyID}_{loginID}",
                "familyID": familyID,
                "loginID": loginID,
                "memberRole": "OWNER" if loginID == S5_OWNER else "MEMBER",
                "memberStatus": "ACTIVE",
                "joinedYMDHMS": now,
                "regID": loginID,
                "regYMDHMS": now,
                "delFlag": "0",
            },
        )

    template = mysqlCommon.query_mj_rule_template_by_code("generic_standard")
    room = roomService.createRoom(
        S5_OWNER, familyID, S5_FAMILY_CODE, "S5 测试房", int(template.get("recID") or 0)
    )

    s5 = {
        "family_id": familyID,
        "family_code": S5_FAMILY_CODE,
        "owner": S5_OWNER,
        "members": [loginID for loginID, _ in S5_MEMBERS],
        "template_id": int(template.get("recID") or 0),
        "room": room,
    }

    yield s5

    # 尽力清理：只软删本次（及中途补开的）房间，不动物业数据
    for roomID in {room["id"], s5["room"]["id"]}:
        try:
            mysqlCommon.delete_mj_soft(mysqlCommon.MJ_ROOM_TABLE, roomID, "pytest")
        except Exception:  # noqa: BLE001 清理失败不影响用例结论
            pass


@pytest.fixture(autouse=True)
def _keepS5RoomOpen(request):
    """用到 `s5_env` 的用例进入前，保证共享房仍是 OPEN（见 `ensureS5RoomOpen`）。"""
    if "s5_env" not in request.fixturenames:
        yield
        return
    ensureS5RoomOpen(request.getfixturevalue("s5_env"))
    yield

"""一次性修正：按 07 §7.1 v1.16 重算已落库的「包牌」局分差（R-10）。

背景（`plan/改进和错误修复文档.md` §2D · R-10）：
v1.1.8 之前，包牌只看「点炮牌 ∈ 该牌型允许集」，**不看明牌**。于是
「3 组明牌全是字牌 + 混一色（数牌全藏在暗牌）+ 点炮主花色数牌」（生产房间 709486 /
round recID 753）也被判包牌，点炮者独付三家。v1.1.8 起新增第 5 条
「牌型特征牌必须已经亮在明牌里」，这类局不再包。

本脚本把**已落库**的这类局按新口径重算并回写：

口径（安全第一，任何一条不满足就跳过、不写库）：
  - 只处理 `payerJson` 里含 `reason='bao_pai'` 的局（自摸/普通点炮不碰）；
  - 用落库的 `finalHandsJson` + `mj_game.ruleSnapshot` 重建赢家手牌，调
    `engine._settle_fan_delta()` 重算「谁付多少」；**番种与 fanTotal 一律不改**（包牌只改付款方）；
  - 重算的 `fan_total` 必须与落库 `fanTotal` 一致，否则视为数据不可信 → 跳过；
  - 落库的 `scoreDeltaJson` 必须等于「旧包牌口径下的纯番分差」（说明这局没有杠分等额外加减），
    否则 → 跳过（需人工处理）；
  - 重算后**仍然触发包牌** → 跳过；
  - 幂等：`payerJson` 已为空且 `scoreDeltaJson` 已是重算结果 → 跳过。

写库（`--apply` 才执行，单事务）：
  1. `mj_game_round`：`scoreDeltaJson` 换成新分差、`payerJson` 置 NULL、`memo` 记修正说明；
  2. `mj_game_player`：每个座位 `totalScore += (新分差 - 旧分差)`（复用 `update_mj_game_player_score`）。

运行（工作目录 = code/backend/src）：
    python tools/fixBaoPaiSettlement.py --round 753              # 预演（默认不写库）
    python tools/fixBaoPaiSettlement.py --round 753 --apply      # 落库
    python tools/fixBaoPaiSettlement.py --game 66 --apply        # 整场扫一遍
    python tools/fixBaoPaiSettlement.py --round 753 --env server_01 --apply
    python tools/fixBaoPaiSettlement.py --all-bao --apply        # 扫最近 100 局包牌局
"""

from __future__ import annotations

import argparse
import os
import sys

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)

from game.families import registry  # noqa: E402
from game.fan import best_win  # noqa: E402
from game.hand import HandContext, Meld  # noqa: E402
from game.patterns import collect_wins  # noqa: E402
from game.tiles import counts_from_tiles, tile_name  # noqa: E402

MAX_ROWS = 100
ENGINE_CODE = "baishi"


# ---------------------------------------------------------------- 数据读取


def _load_rounds(round_id: int | None, game_id: int | None, all_bao: bool) -> list[dict]:
    from common import mysqlCommon as comMysql

    if round_id:
        cond = [["recID", "=", round_id]]
    elif game_id:
        cond = [["gameID", "=", game_id]]
    elif all_bao:
        cond = None
    else:
        raise SystemExit("请给 --round / --game / --all-bao 之一")
    rows = comMysql.queryTableGeneral(
        comMysql.MJ_GAME_ROUND_TABLE,
        condList=cond,
        delFlag="",
        order="modify" if all_bao else "create",
        limitNum=MAX_ROWS,
    )
    if all_bao:
        rows = [row for row in rows if _has_bao(row)]
    return rows


def _has_bao(row: dict) -> bool:
    payer = row.get("payerJson") or []
    return any(isinstance(item, dict) and item.get("reason") == "bao_pai" for item in payer)


def _load_game(game_id: int) -> dict | None:
    from common import mysqlCommon as comMysql

    rows = comMysql.queryTableGeneral(
        comMysql.MJ_GAME_TABLE,
        condList=[["recID", "=", game_id]],
        delFlag="",
        order="create",
        limitNum=1,
    )
    return rows[0] if rows else None


def _load_players(game_id: int) -> dict[int, dict]:
    from common import mysqlCommon as comMysql

    rows = comMysql.queryTableGeneral(
        comMysql.MJ_GAME_PLAYER_TABLE,
        condList=[["gameID", "=", game_id]],
        delFlag="0",
        order="create",
        limitNum=4,
    )
    return {int(row.get("seatNo") or 0): row for row in rows}


# ---------------------------------------------------------------- 复算


def _rule_of(game_row: dict):
    from processor import ruleService

    snapshot = game_row.get("ruleSnapshot")
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("config"), dict):
        raise ValueError("mj_game.ruleSnapshot 缺失或结构异常")
    code = str(snapshot.get("rule_family_code") or game_row.get("ruleFamilyCode") or "")
    return code, ruleService.validateConfig(code, snapshot["config"])


def _ctx_of(row: dict, winner: int, dealer_seat: int) -> HandContext | None:
    final_hands = row.get("finalHandsJson") or []
    winner_view = next(
        (item for item in final_hands if isinstance(item, dict) and int(item.get("seat", -1)) == winner),
        None,
    )
    if winner_view is None:
        return None
    concealed = [int(tile) for tile in (winner_view.get("concealed") or [])]
    melds: list[Meld] = []
    for item in winner_view.get("melds") or []:
        if not isinstance(item, dict):
            continue
        tiles = [int(tile) for tile in (item.get("tiles") or [])]
        if not tiles:
            continue
        melds.append(
            Meld(
                kind=str(item.get("kind") or "pong"),
                tiles=tiles,
                from_seat=item.get("from_seat"),
                claim_tile=item.get("claim_tile"),
            )
        )
    win_tile = row.get("winningTile")
    # v1.17：圈风刻改按圈风判定，而圈序不落库（历史行只有局风 roundWind）。
    # 这里按东风圈（circle_wind=0）复算；若该局确实含圈风刻且不在东风圈，
    # 复算 fan_total 会与落库 fanTotal 不符 → 上层按「数据不可信」跳过，不会误改。
    return HandContext(
        counts=counts_from_tiles(concealed),
        melds=melds,
        win_tile=None if win_tile is None else int(win_tile),
        is_self_draw=(row.get("winType") == "self_draw"),
        seat_wind=(winner - dealer_seat) % 4,
        round_wind=int(row.get("roundWind") or 0),
        circle_wind=0,
    )


def _seats_of(players: dict[int, dict]) -> list:
    from game.engine import SeatState

    seats = []
    for seat in range(4):
        player = players.get(seat) or {}
        seats.append(
            SeatState(
                seat=seat,
                login_id=str(player.get("loginID") or f"seat{seat}"),
                display_name=str(player.get("displayName") or f"座位{seat + 1}"),
                color="#C9A063",
            )
        )
    return seats


def _plan(row: dict, game_row: dict, players: dict[int, dict]) -> dict:
    """返回 {'skip': 原因} 或 {'old', 'new', 'diff', 'breakdown', 'allocation', 'names'}。"""
    rec_id = int(row.get("recID") or 0)
    game_id = int(row.get("gameID") or 0)
    winner = row.get("winnerSeat")
    if winner is None:
        return {"skip": "荒庄局"}
    winner = int(winner)
    win_type = str(row.get("winType") or "none")
    win_tile = row.get("winningTile")
    old_delta = [int(value or 0) for value in (row.get("scoreDeltaJson") or [])]
    if len(old_delta) != 4:
        return {"skip": "scoreDeltaJson 不是 4 家分差"}

    payer = row.get("payerJson") or []
    bao_record = next(
        (item for item in payer if isinstance(item, dict) and item.get("reason") == "bao_pai"), None
    )
    if bao_record is None:
        return {"skip": "非包牌局"}

    code, rule = _rule_of(game_row)
    if code != ENGINE_CODE:
        return {"skip": f"规则族 {code} 不是 {ENGINE_CODE}"}

    dealer_seat = int(row.get("dealerSeat") or 0)
    ctx = _ctx_of(row, winner, dealer_seat)
    if ctx is None:
        return {"skip": "finalHandsJson 里找不到赢家手牌"}
    breakdown = best_win(collect_wins(ctx, rule), rule)
    if breakdown is None:
        return {"skip": "用落库手牌复算不出胡（数据不可信）"}
    if int(breakdown.fan_total) != int(row.get("fanTotal") or 0):
        return {
            "skip": f"复算番 {breakdown.fan_total} ≠ 落库 {row.get('fanTotal')}（数据不可信）"
        }

    engine = registry.create_engine(
        code,
        rule,
        _seats_of(players),
        round_no=int(row.get("roundNo") or 1),
        dealer_seat=dealer_seat,
        round_wind=int(row.get("roundWind") or 0),
    )
    discard_seat = bao_record.get("bao_pai_seat")
    discard_seat = None if discard_seat is None else int(discard_seat)
    new_delta, allocation, _multipliers = engine._settle_fan_delta(
        winner, breakdown, win_type, discard_seat, ctx, None if win_tile is None else int(win_tile)
    )
    new_delta = [int(value) for value in new_delta]

    # 旧口径的纯番分差（包牌：点炮者独付三家之和）——用来确认这局没有杠分等额外加减
    unit = int(getattr(breakdown, "score", 0) or 0)
    dues = {}
    for seat in range(4):
        if seat == winner:
            continue
        mult = 2 if seat == dealer_seat else 1
        dues[seat] = unit * mult
    total = sum(dues.values())
    expect_old = [0, 0, 0, 0]
    if discard_seat is None:
        return {"skip": "包牌记录缺少 bao_pai_seat"}
    expect_old[discard_seat] -= total
    expect_old[winner] += total
    if old_delta != expect_old:
        return {"skip": f"落库分差 {old_delta} ≠ 旧包牌纯番分差 {expect_old}（疑似含杠分，需人工）"}

    names = {
        seat: str((players.get(seat) or {}).get("displayName") or f"座位{seat + 1}")
        for seat in range(4)
    }
    if allocation:
        return {"skip": f"新口径下仍判包牌（patterns={allocation[0].get('patterns')}），无需修正"}
    if old_delta == new_delta:
        return {"skip": "分差已是新口径结果（幂等跳过）"}

    return {
        "round": rec_id,
        "game": game_id,
        "round_no": int(row.get("roundNo") or 0),
        "winner": winner,
        "fan_total": int(breakdown.fan_total),
        "unit": unit,
        "old": old_delta,
        "new": new_delta,
        "diff": [new_delta[seat] - old_delta[seat] for seat in range(4)],
        "names": names,
        "winning_tile": None if win_tile is None else int(win_tile),
    }


# ---------------------------------------------------------------- 落库


def _memo_of(plan_row: dict) -> str:
    old = "/".join(str(value) for value in plan_row["old"])
    new = "/".join(str(value) for value in plan_row["new"])
    return f"v1.1.8 R-10 包牌口径修正（明牌全字牌不算包）：{old} -> {new}"


def _apply(plan_row: dict) -> bool:
    from common import mysqlCommon as comMysql

    with comMysql.transaction():
        affected = comMysql.updateTableGeneral(
            comMysql.MJ_GAME_ROUND_TABLE,
            "recID = %s",
            [plan_row["round"]],
            {
                "scoreDeltaJson": plan_row["new"],
                "payerJson": None,
                "memo": _memo_of(plan_row),
            },
        )
        if affected <= 0:
            raise RuntimeError(f"更新 mj_game_round(recID={plan_row['round']}) 失败")
        for seat, delta in enumerate(plan_row["diff"]):
            if not delta:
                continue
            written = comMysql.update_mj_game_player_score(plan_row["game"], seat, delta)
            if written <= 0:
                raise RuntimeError(f"更新 mj_game_player(game={plan_row['game']}, seat={seat}) 失败")
    return True


# ---------------------------------------------------------------- 主流程


def run(round_id=None, game_id=None, all_bao=False, apply=False) -> dict:
    from common import miscCommon as misc

    rounds = _load_rounds(round_id, game_id, all_bao)
    result = {
        "scanned": len(rounds),
        "fixed": 0,
        "skipped": 0,
        "failed": 0,
        "apply": apply,
    }
    if not rounds:
        print("[fix-bao] 没有匹配的结算记录")
        return result

    games: dict[int, dict] = {}
    players: dict[int, dict[int, dict]] = {}
    for row in rounds:
        rec_id = int(row.get("recID") or 0)
        game_id_of_row = int(row.get("gameID") or 0)
        if game_id_of_row not in games:
            games[game_id_of_row] = _load_game(game_id_of_row) or {}
            players[game_id_of_row] = _load_players(game_id_of_row)
        game_row = games[game_id_of_row]
        if not game_row:
            print(f"[fix-bao] round={rec_id} 找不到场次 {game_id_of_row}，跳过")
            result["skipped"] += 1
            continue
        try:
            plan_row = _plan(row, game_row, players[game_id_of_row])
        except Exception as exc:  # noqa: BLE001 —— 预演阶段只报错不写
            print(f"[fix-bao] round={rec_id} 复算异常：{exc}")
            result["failed"] += 1
            continue
        if "skip" in plan_row:
            print(f"[fix-bao] round={rec_id} 跳过：{plan_row['skip']}")
            result["skipped"] += 1
            continue

        names = plan_row["names"]
        win_tile = plan_row["winning_tile"]
        print(
            f"[fix-bao] round={plan_row['round']}(场次 {plan_row['game']} 第 {plan_row['round_no']} 局) "
            f"赢家 {names[plan_row['winner']]} 胡 {tile_name(win_tile) if win_tile is not None else '-'} "
            f"{plan_row['fan_total']} 番 = {plan_row['unit']} 分"
        )
        for seat in range(4):
            print(
                f"          {names[seat]}: 旧 {plan_row['old'][seat]:+d} → 新 {plan_row['new'][seat]:+d}"
                f"（差 {plan_row['diff'][seat]:+d}）"
            )
        if not apply:
            print("          dry-run：未写库（加 --apply 才落库）")
            result["fixed"] += 1
            continue
        try:
            _apply(plan_row)
        except Exception as exc:  # noqa: BLE001
            print(f"          写库失败：{exc}")
            result["failed"] += 1
            continue
        print("          已落库（mj_game_round + mj_game_player 同事务）")
        result["fixed"] += 1

    print(f"[fix-bao] {misc.getTime()} -> {result}")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="按 07 §7.1 v1.16 修正历史包牌局分差（R-10）")
    parser.add_argument("--round", type=int, default=None, help="mj_game_round.recID")
    parser.add_argument("--game", type=int, default=None, help="mj_game.recID（整场扫描）")
    parser.add_argument("--all-bao", action="store_true", help="扫最近 100 局里的包牌局")
    parser.add_argument(
        "--env",
        default="",
        choices=["", "local", "test_server", "server_01"],
        help="留空则沿用 .env 里的 APP_ENV（服务器上推荐留空）",
    )
    parser.add_argument("--test", action="store_true", help="指向测试库 mahjong_test")
    parser.add_argument("--apply", action="store_true", help="真正写库（默认只预演）")
    args = parser.parse_args(argv)

    if args.env:
        os.environ["APP_ENV"] = args.env
    if args.test or args.env == "test_server":
        os.environ["MYSQL_WRITE_DB"] = "mahjong_test"
        os.environ["MYSQL_READ_DB"] = "mahjong_test"

    result = run(
        round_id=args.round,
        game_id=args.game,
        all_bao=args.all_bao,
        apply=args.apply,
    )
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

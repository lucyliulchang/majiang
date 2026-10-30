# 家庭麻将 · v1.1.0 分步改进指令（improve step-prompts）

> 配套：[改进和错误修复文档.md](改进和错误修复文档.md)（问题台账与方案）｜[家庭麻将总体规划文档.md](家庭麻将总体规划文档.md)｜[07-柏氏规则细则.md](07-柏氏规则细则.md)｜[04-协议设计.md](04-协议设计.md)｜[05-UI设计.md](05-UI设计.md)｜[06-实施计划.md](06-实施计划.md)
>
> **使用方法**：每一步**单独开一个新对话**，把该步 `text` 围栏内的提示语整段复制过去。
> 前一步验收未通过，不要开始下一步。
> 每步结束统一输出：**改动文件清单 + 验收结果 + 遗留问题**。
>
> 与 [step-prompts.md](step-prompts.md) 的关系：S0–S10 是 v1.0.x 的重制步骤（已完成并上线）；本文 **I0–I8 是 v1.1.0 的运行反馈修复步骤**，接在 S10 之后。

## 当前状态（2026-10-30）

| 步骤 | 范围 | 版本 | 状态 |
| --- | --- | --- | --- |
| S0–S10 | 重制：目录/MySQL/账号/家庭/数据层/观战/规则族/皮肤/音效/前端与部署 | v1.0.x | 已完成并上线（`https://www.iottest.online/majiangapp/`） |
| **I0** | 基线核对与口径冻结（只改文档） | v1.1.0 | 已完成 |
| **I1** | 房间生命周期收尾（B-1） | v1.1.0 | 已实施（I6 已回归，待 I7 发版） |
| **I2** | 柏氏番表：258 赢 / 十三不靠 / 连六 / 断幺（R-1～R-4） | v1.1.0 | 已实施（I6 已回归，待 I7 发版） |
| **I3** | 胡牌优先与过胡（U-1） | v1.1.0 | 已实施（I6 已回归，待 I7 发版） |
| **I4** | 吃牌选两张（U-2） | v1.1.0 | 已实施（I6 已回归，待 I7 发版） |
| **I5** | 结算庄家标记与提示字号（U-3 / U-4） | v1.1.0 | 已实施（I6 已回归，待 I7 发版） |
| **I6** | 全量回归与手测 | v1.1.0 | 已完成（验收报告：[v1.1.0-验收报告.md](v1.1.0-验收报告.md)） |
| **I7** | 发版与验收回写 | v1.1.0 | 待开始 |
| **I8** | 一场时长：默认 4 圈、开桌可选（F-1） | v1.1.0 | 已实施（I6 已回归，待 I7 发版） |

**下一步**：I7（生产发版 + 文档回写）。I1–I5 与 I8 的代码已在工作区但未提交；I6 全量回归结论见 [v1.1.0-验收报告.md](v1.1.0-验收报告.md)（`pytest` 363 passed / 0 failed，无阻塞发版问题）。

**优先级建议**：I1（Bug，影响大厅可用性）> I2（规则正确性）> I3 > I4 > I5 > I6 > I7。
I1 可先单独发一次热修；若时间紧，允许 I1 与 I2 分两次上线，但版本号仍统一为 `1.1.0`（I1 为 `1.1.0-rc1`，全量发版为 `1.1.0`）。

## 全局约定（每步都适用）

| 项 | 约定 |
| --- | --- |
| 代码根 | `d:/StevenLianData/0301. Private Project/gitData/majiang/code/` |
| 文档根 | `d:/StevenLianData/0301. Private Project/gitData/majiang/plan/` |
| 后端根 | `code/backend/src/`（venv 在 `code/backend/.venv`） |
| 前端根 | `code/frontend/`（桌面 `src/`，手机 `src/mobile/`，共用 `src/components/table/*`） |
| 规则权威 | 柏氏数值与判定**只认** `plan/07-柏氏规则细则.md`；番表**只认** `baishi/fan.py` 的 `FAN_TABLE` |
| 协议权威 | 接口/事件/错误码**只认** `plan/04-协议设计.md` |
| 数据访问 | 业务层禁止裸 SQL，一律走 `common/mysqlCommon.py` |
| 数据库 | MySQL 8.0，库 `mahjong_data`；表定义只认 `database/*.txt`；**本轮无 DDL** |
| 番表生效 | 改 `FAN_TABLE` 后必须重跑 `python tools/seedPresets.py --env <env>`（只覆盖 `familyID=0` 预置模板） |
| 测试 | 后端 `pytest -q`；前端 `npm run typecheck` + `npm run build` |
| 版本 | 后端 `config/basicSettings.py` `VERSION`、前端 `package.json` `version`、`plan/07` 标题版本三处统一 |
| 提交 | 每步一个可回退 commit，不混入无关格式改动 |
| 生产 | `ssh -i D:\data\keys\codeops_ed25519 codeops@www.iottest.online`（只读排查）；发版走 `~/mj_deploy2/12_redeploy.sh` |

## 目录

- I0 · 基线核对与口径冻结
- I1 · 房间生命周期收尾（B-1）
- I2 · 柏氏番表（R-1～R-4）
- I3 · 胡牌优先与过胡（U-1）
- I4 · 吃牌选两张（U-2）
- I5 · 结算庄家标记与提示字号（U-3 / U-4）
- I6 · 全量回归与手测
- I7 · 发版与验收回写
- I8 · 一场时长（默认 4 圈，开桌可选）

---

## I0 · 基线核对与口径冻结

> **什么时候做**：现在。只改文档，不改代码。

````text
【家庭麻将 · v1.1.0 · I0 · 基线核对与口径冻结】

## 目标
把 v1.1.0 的 9 个问题（R-1～R-4 / U-1～U-4 / B-1）核对到"可照着写代码"的粒度，冻结番种 id、番值、判定口径、错误码与版本号；不改任何代码。

## 前置
无。`plan/改进和错误修复文档.md` 与本文已定稿。

## 必须先读
- plan/改进和错误修复文档.md（逐条方案）
- plan/07-柏氏规则细则.md（§5 番表、§6.2/§6.3.4/§6.4/§6.7/§6.8、§13 用例）
- plan/03-规则族设计.md（§7 柏氏摘要、§7.3 牌型）
- plan/04-协议设计.md（§9.3/§9.4/§9.5、§10 错误码）
- plan/05-UI设计.md（动作条、结算页、设计系统字号）
- code/backend/src/game/families/baishi/fan.py、config.py、selfcheck.py
- code/backend/src/game/claims.py、code/backend/src/realtime/room.py

## 任务
1. 冻结新增番种：`er_wu_ba_ying`（258赢，1 番，无互斥组，非计数）、`duan_yao`（断幺，1 番，无互斥组，非计数）；番表 32 → 34。
2. 冻结十三不靠"宽松版"判定顺序（14 张、无副露、恰好一对将、中发白必含、风各 ≤1、数牌每门 0–3 张且同门同组、允许缺门），写进 07 §6.3.4。
3. 冻结连六口径（每组合 1 番、可多组累加、龙上位抑制、七对/13不靠/十三幺不判）。
4. 冻结 U-1 两段式询问的状态机命名（`passed_hu` / `available()` / 终态判定）与 04 §9.5 描述；冻结"过胡仅当前这张牌"。
5. 冻结 U-2 的 `chow.tiles` 语义（客户端指定的两张手牌）与错误码 `BAD_CHOW` 文案。
6. 冻结 B-1 的收尾方案（`_close_room` 幂等 + `_finish_game` 落库 CLOSED + `finished` 态 `game.finish` 幂等 + `CLOSE_FAILED`）。
7. 统一版本号：`1.1.0`；`plan/07` 升 `v1.9`；在各文档状态行写入 `v1.1.0（2026-10-30）`。

## 验收清单
- [ ] 34 个番种 id 在 07 §5、`FAN_TABLE`、03 §7.1 三处完全一致（脚本或 grep 比对，零差异）。
- [ ] 07 §6.3.4 的新判定与"14 张构成公式"自洽（数牌张数 = 9 − 风牌数）。
- [ ] 04 中 `chow.tiles`、`legal.actions` 两段式、`game_finished{final}`、`room_closed`、`BAD_CHOW`、`CLOSE_FAILED` 均有明确触发场景与文案。
- [ ] 05 中"提示语 +2 号"写成具体 px 档位（桌面 14 / 手机 13 / 按钮 16）。
- [ ] 全局 grep 校验：`32 项` 仅出现在历史修订记录；`1.0.0` 仅出现在历史版本说明；`待开始` 不再出现于 S6–S10。
- [ ] plan/ 内相对链接无死链。

## 硬约束
- 只改 plan/ 下的 .md 与 07 的 .html；不改代码、不跑构建、不连库写入。
- 不臆造规则数值；07 未覆盖或与用户口径冲突处先问再写。
- 不删除其它文档原文，改为"摘要 + 链接"。

## 完成后必须输出
1. 改动文件清单（路径 + 改了什么）。
2. 34 项番种对照表（id/名称/番/互斥组/计数）与 grep 结果。
3. 未决问题（不超过 5 条，必须明确是否阻塞 I1）。
````

---

## I1 · 房间生命周期收尾（B-1）

> **什么时候做**：I0 通过后立即做。这是本次唯一影响"大厅可用性"的 Bug。

````text
【家庭麻将 · v1.1.0 · I1 · 房间生命周期收尾（B-1）】

## 目标
让"结束牌局/打满一场（所选圈数）"百分百真正关房：`mj_room.roomStatus='CLOSED'` 落库、大厅立即消失、牌桌回大厅；重复操作幂等；WS 断线时 REST 兜底。清除生产遗留的 OPEN 幽灵房。

## 前置
I0 通过（`CLOSE_FAILED`、`game_finished{final}` 语义已冻结）。

## 必须先读
- plan/改进和错误修复文档.md §4（B-1 根因链与方案）
- code/backend/src/realtime/room.py（`_finish_game` `_end_game` `shutdown` `_persist` `on_disconnect`）
- code/backend/src/realtime/persist.py、code/backend/src/common/mysqlCommon.py（`update_mj_room_close`、`query_mj_room_list`）
- code/backend/src/processor/roomService.py（`closeRoom` 权限与落库）
- code/backend/src/main/api/rooms.py（`POST /api/rooms/{id}/close`）
- code/frontend/src/stores/game.ts、src/api/ws.ts、src/views/RoomView.vue、src/views/LobbyView.vue、src/mobile/views/MobileRoomView.vue、src/mobile/views/MobileLobbyView.vue
- plan/04-协议设计.md §9.4、§10

## 任务
1. 后端抽 `RoomActor._close_room(operator_login_id)`：`persist.close_room` → `status="closed"` → `shutdown`；`close_room` 命中 0 行但已是 CLOSED 视为成功。
2. `_finish_game()` 必须落库 CLOSED：先广播 `event.game_finished{..., "final": true}`，随后落库 `close_room`；**不立即广播 `room_closed`**，标记 `finalized=True`，在最后一个连接断开或 60s 兜底时 `shutdown`（幂等）；不得同时保留"立即 shutdown"的第二种收尾路径。
3. `_end_game()` 守卫改为：`closed` → 幂等成功；`finished` → 幂等收摊成功；`playing` → 正常收场；`waiting` → `NOT_PLAYING`，文案改为"牌局还没开始，回大厅关闭牌桌即可"。
4. `_persist()` 对 `close_room`/`close_game` 失败上抛 `PersistError`；`_end_game` 捕获后回 `error{CLOSE_FAILED, "关房失败，请在大厅重试"}`。
5. `persist.close_room` + `mysqlCommon.update_mj_room_close`：区分"命中 1 行 / 已 CLOSED / 未命中"，不加列、不改表。
6. 前端 `stores/game.ts endGame()`：3s 超时未收到 `game_finished`/`room_closed` → `POST /api/rooms/{room_id}/close` 兜底；失败提示"请在大厅关闭牌桌"。
7. `api/ws.ts sendMessage()`：非 OPEN 返回 false / 抛可捕获错误，不得静默 return。
8. `canEndGame` 改用快照 `status !== 'waiting'`；`finished` 态按钮文案"关闭牌桌"（桌面 + 手机）。
9. 大厅 `load()` 增加 `visibilitychange` 刷新 + 30s 轮询；"回到大厅"时若房间未关闭先调关房接口（幂等）。
10. 新增 `code/deploy/14_close_stale_rooms.sh`：mysqldump 备份 → 仅更新 `roomStatus='OPEN' AND closedYMDHMS IS NULL` 的历史房（recID 4、5 白名单）→ 打印影响行数。
11. 补测试：自然打满后 `roomStatus='CLOSED'`；`finished` 态 `game.finish` 幂等；`/api/rooms` 不含 CLOSED；非房主仍 `NOT_HOST`。

## 验收清单
- [ ] `pytest tests/test_ws_flow.py -q` 全绿，新增 3 条用例覆盖上述路径。
- [ ] 本地跑通"4 人打满一场"（I8 之前为 1 圈；之后按所选圈数）：库中 `roomStatus=CLOSED`、`closedYMDHMS` 非空、大厅列表不含该房。
- [ ] 进行中由房主结束：`mj_game.gameStatus=ABORTED`、房间 CLOSED。
- [ ] 重复点击"结束牌局"：无 `NOT_PLAYING` 报错，库中一条 CLOSED。
- [ ] 停掉 WS（浏览器 devtools 断网）后点结束：3s 内 REST 兜底成功并提示。
- [ ] 模拟 `close_room` 抛异常：前端收到 `CLOSE_FAILED` 且**不跳转**，可重试。
- [ ] 桌面与手机两条入口行为一致。
- [ ] 14 脚本在测试库演练通过（备份文件存在、影响行数 = 2）。

## 硬约束
- 不改表结构、不加列；`mj_room` 只有 `roomStatus` / `closedYMDHMS` / `modifyID` / `modifyYMDHMS` 四个字段可写。
- 不引入后台常驻任务框架；延迟回收只能靠 `on_disconnect` 或 `asyncio` 单次定时器。
- 不在本步改番表、不改 UI 视觉。

## 完成后必须输出
1. 改动文件清单 + 关键函数签名变化。
2. 测试输出（用例名 + 结果）与本地手测记录。
3. 生产待执行命令（14 脚本）与回滚方式。
````

---

## I2 · 柏氏番表（R-1～R-4）

> **什么时候做**：I1 通过后。建议与 I1 分两次上线，避免一次改动面过大。

````text
【家庭麻将 · v1.1.0 · I2 · 柏氏番表 34 项（258赢 / 十三不靠 / 连六 / 断幺）】

## 目标
按 07 v1.9 落地 4 个番种：新增 258赢、断幺；按宽松版重写十三不靠；确认并补测连六。番表 32 → 34，预置模板同步。

## 前置
I0 通过；I1 已完成（可同版本不同批次上线）。

## 必须先读
- plan/07-柏氏规则细则.md §5 / §6.2 / §6.3.4 / §6.4 / §6.7 / §6.8 / §6.11 / §13
- code/backend/src/game/families/baishi/fan.py（`FAN_TABLE`、`STACKABLE_FANS`、`unrelated_pair`、`chow_fans`、`calc_fan`、`thirteen_unrelated_fans`）
- code/backend/src/game/families/baishi/config.py、presets.py、selfcheck.py
- code/backend/src/game/hand.py（`HandContext`：`win_tile`、`all_tiles()`）
- code/backend/src/tests/test_baishi_s7.py

## 任务
1. `FAN_TABLE` 增两行：`("er_wu_ba_ying", "258赢", 1, None, False)`、`("duan_yao", "断幺", 1, None, False)`；同步 `config.default_fan_table()` 的 docstring 与 03 的 34 项。
2. 在 `calc_fan()` 出口统一追加"赢张类/花色类全局番"：258 赢读 `ctx.win_tile`（数牌且 `rank+1 in (2,5,8)`）；断幺读 `ctx.all_tiles()`（全为 2–8 数牌）。不要逐个牌型挂。
3. 重写 `unrelated_pair()`：按 I0 冻结的 7 步判定（14 张 / 无副露 / 恰好一对将 / 中发白各 ≥1 / 风各 ≤1 / 数牌每门 0–3 张且同门同组 / 全覆盖），返回将牌；`thirteen_unrelated_fans()` 逻辑不变（10 番 + 将牌 + 独赢 + 门清 + flush + 缺门）。
4. 连六：核对 `chow_fans()` 的 `lian_liu` 计数与龙上位抑制；补齐 4 条用例（单组 / 两组 / 青龙抑制 / 跨花色不叠加）。
5. `selfcheck.REQUIRED_CASES` 增 `07-13-32`（258赢）、`07-13-33`（连六）、`07-13-34`（断幺）；`07-13-09` 注释改宽松口径。
6. 测试：`tests/test_baishi_s7.py` 的 `len(FAN_TABLE)==32` 改 34；新增 4 个番种正反例（含"副露含 1 万不算断幺""将 3 赢 5 只计 258 赢""含东风 13 不靠成立""将牌为东成立""同门跨组不成立"）。
7. 重跑种子：`python tools/seedPresets.py --env <env>`，确认库中 `baishi_default.configJson` 的 `fan_table` 为 34 项。
8. 校验前端无需改动：`FanTableEditor.vue` 由 `config.fan_table` 驱动；新番 1 番不触碰 0–200 上限。

## 验收清单
- [ ] `pytest tests/test_baishi_s7.py -q` 全绿；`len(FAN_TABLE)==34`。
- [ ] 07 §5 表格 34 行与 `FAN_TABLE` 逐项一致（脚本比对 id/番/组/计数）。
- [ ] 258 赢：赢张 8万/2条/5筒 各 +1；赢张 3万/字牌 0；将 5 赢 3 只计将牌 1。
- [ ] 断幺：全 2–8 数牌 +1；含 1/9/字牌 0；副露含 1 万 0；清一色断幺 31；七对断幺 21；13不靠/十三幺恒 0。
- [ ] 十三不靠：含东风成立；单门 1 张成立；将牌为东成立；缺门叠加 1；副露不成立；同门跨组/相邻/重复不成立。
- [ ] 连六：123456万+789万 → 1；123456万+456789筒 → 2；青龙 → 0；跨花色 → 不叠加。
- [ ] `seedPresets` 后 `SELECT fan_table FROM mj_rule_template WHERE templateCode='baishi_default'` 为 34 项。
- [ ] 结算页 `fan_items` 正常显示新番中文名（前端无需改）。

## 硬约束
- 番表以 `FAN_TABLE` 为唯一来源，禁止在 `config.py` / `presets.py` 复制番值。
- 不改 `game/fan.py` 的互斥/取高机制与结算公式。
- 不动通用族（`generic/patterns/thirteen_unrelated.py` 口径完全不同，禁止混改）。
- 不改 `mj_game_round` 表结构；历史局不回填。

## 完成后必须输出
1. 改动文件清单 + 新增/修改的番种函数名。
2. 34 项对照表与测试输出。
3. 种子重跑日志与库内校验结果。
````

---

## I3 · 胡牌优先与过胡（U-1）

> **什么时候做**：I2 通过后。改询问状态机，必须同步改 04 协议描述。

````text
【家庭麻将 · v1.1.0 · I3 · 胡牌优先与过胡（U-1）】

## 目标
同一玩家在一张牌上同时可胡与可吃碰杠时，**先只问胡**；点了"不胡"（过胡）后才补发吃碰杠选项；过胡只对当前这张牌生效。

## 前置
I2 通过（引擎与番表稳定，避免"过胡"与番种同时变动难以定位）。

## 必须先读
- plan/改进和错误修复文档.md §3 U-1
- code/backend/src/game/claims.py（`ClaimWindow` 全部方法）
- code/backend/src/game/engine.py（`_build_claim_window`、`_claim_response`、`timeout_claim`、`_resolve_claim`、`legal_actions`）
- code/backend/src/realtime/room.py（`_on_action`、`_after`、`_sync_timers`、`_claim_timeout`）
- code/frontend/src/components/table/ActionBar.vue、src/stores/game.ts
- plan/04-协议设计.md §9.3、§9.5

## 任务
1. `ClaimWindow` 增 `passed_hu: set[int]`；新增 `available(seat) -> list[dict]`：含 `hu` 且未过胡 → `[hu, pass]`；否则 → 其余动作 + `pass`（不含 hu）。
2. `record()` 两段式：当前处于"胡阶段"且提交 `pass` → 记入 `passed_hu`，**不写终态**；其余动作写终态。`is_complete()` / `pending()` 改为按"是否有终态动作"判断。
3. `engine.legal_actions()` 改用 `window.available(seat)`；`_claim_response()` 用 `available()` 校验（胡阶段提交吃/碰/杠 → `BAD_ACTION`）；`timeout_claim()` 仍把全部 pending 记终态 `pass`。
4. 确认 `room._after([])` 在"仅过胡、窗口未关闭"时仍 `push_all()`，使该玩家立即看到吃碰选项；若否则补一次 `push_all`。
5. 前端：`ActionBar.vue` 无需改结构（服务端已过滤）；"过"按钮文案分阶段（hu 阶段显示"不胡"，第二阶段显示"过"）；`RoomView.vue` / `MobileRoomView.vue` 同步。
6. 协议：更新 04 §9.3（`pass` 在胡阶段 = 过胡，不关闭窗口）、§9.5（`legal.actions` 动态收敛说明）。
7. 测试：引擎级 4 条 + WS 级 2 条（见验收）。

## 验收清单
- [ ] 同座位可胡可碰：快照 `legal.actions == [hu, pass]`。
- [ ] 提交 `pass` 后同窗口下一版快照出现 `pong`/`pass`（无 `hu`），且吃碰可正常执行。
- [ ] 胡阶段直接构造 `{"action":"pong"}` → `BAD_ACTION`，不会静默吃掉胡。
- [ ] 下一张牌重新出现 `hu`（仅当前这张牌生效）。
- [ ] 过胡后不操作 → 超时按终态 pass 收窗，牌局继续，无卡死。
- [ ] 无人可胡时行为与改动前完全一致（回归 `pytest tests/test_engine_flow.py tests/test_ws_flow.py`）。
- [ ] 桌面/手机 UI 文案与行为一致。

## 硬约束
- 不新增接口，不改变 `game.action` 报文字段；仅在 `legal.actions` 内容上收敛。
- 不引入"整局过胡"或"过水"的跨窗口状态（用户口径：仅当前这张牌）。
- 不改 `PRIORITY` 与仲裁规则（胡 > 碰 > 杠 > 吃，同优先级下家优先）。

## 完成后必须输出
1. 改动文件清单 + `ClaimWindow` 新状态机说明（含状态图或伪代码）。
2. 测试输出与两条 WS 手工验证记录。
3. 04 文档改动 diff 摘要。
````

---

## I4 · 吃牌选两张（U-2）

> **什么时候做**：I3 通过后。前后端必须同版本发布。

````text
【家庭麻将 · v1.1.0 · I4 · 吃牌选两张（U-2）】

## 目标
吃牌改为"点吃 → 选两张 → 确认"：修复后端组合枚举漏项（234/456 算不出），前端支持点选/取消/改选/确认，后端严格校验顺子合法性。

## 前置
I3 通过（询问窗口状态机已稳定，避免与两段式冲突）。

## 必须先读
- plan/改进和错误修复文档.md §3 U-2
- code/backend/src/game/claims.py（`chow_options`、`chow_tiles`）
- code/backend/src/game/engine.py（`_do_chow`、`_build_claim_window`）
- code/frontend/src/components/table/ActionBar.vue、src/views/RoomView.vue、src/mobile/views/MobileRoomView.vue
- code/frontend/src/mobile/components/table/MobileHand.vue、src/components/table/HandTiles.vue、src/composables/useHandCursor.ts
- code/frontend/src/stores/game.ts、src/types.ts
- plan/04-协议设计.md §9.3/§9.5、§10；plan/05-UI设计.md 动作条

## 任务
1. 后端 `chow_options()` 重写：枚举被吃牌作为顺子低/中/高三态（示例：`234556万 + 4万` 必须返回 234/345/456 三组），去重并按手中可用过滤。
2. 后端 `_do_chow()` 严格校验：两张同花色、与被吃牌连续三张、手中各 ≥1；失败 `EngineError("BAD_CHOW", "吃牌的两张必须与被吃的牌组成顺子")`。
3. 前端 `ActionBar.vue` 增 `chow-select` 态：点"吃"进入选牌（不直接提交）；默认高亮服务端推荐组合；点手牌增删（最多两张）；点候选可一键套用；两张合法才可"确认吃"；"取消"仅退出选牌态；"过"提交 pass；超时自动退出。
4. 手牌多选：桌面 `useHandCursor`/`HandTiles` 扩为可多选（出牌仍单选）；手机 `MobileHand.vue` 增加多选模式。
5. `stores/game.ts` 新增 `chow(tiles)` 提交；`claim` 结束/窗口关闭时强制清空选牌态，避免污染下一张牌。
6. 协议：04 §9.3 写明 `chow.tiles` 是"客户端指定的两张手牌"（不再要求等于服务端候选之一）；§9.5 写明 `legal.actions[].tiles` 是"推荐组合（默认高亮），非唯一解"；§10 登记 `BAD_CHOW` 文案。
7. 测试：后端 5 条（三组候选、非法两张、跨花色、手中不足、吃后 meld 正确）；前端手测 5 条。

## 验收清单
- [ ] `234556万 + 4万` 候选 3 组；选 234/345/456 均能成副露，`Meld.tiles` 为对应三张。
- [ ] 选两张不相邻（2万+6万）→ 前端确认置灰；构造报文直达后端 → `BAD_CHOW`。
- [ ] 点"取消"回到动作条，可再次进入选牌；牌局未推进。
- [ ] 点"过"→ 窗口关闭，下家摸牌。
- [ ] 超时 → 自动退出选牌态并提示"超时未响应，按过处理"。
- [ ] 桌面与手机横屏行为一致；候选区不遮挡手牌/牌河。
- [ ] 出牌单选未被多选状态污染（回归出牌）。
- [ ] `npm run typecheck` 0 error。

## 硬约束
- 不新增 WS 消息类型；仅复用 `game.action{chow}`。
- 前端不得在本地"发明"合法组合提交给服务端而不做校验（后端必须能独立拒绝非法组合）。
- 不改吃牌的既有结算与副露结构（`Meld(kind="chow")` 字段不变）。

## 完成后必须输出
1. 改动文件清单 + `chow-select` 状态说明。
2. 后端测试输出与前端手测截图/记录（含 234556 万示例）。
3. 04/05 文档改动摘要。
````

---

## I5 · 结算庄家标记与提示字号（U-3 / U-4）

> **什么时候做**：I4 通过后。纯前端，可与 I4 并行但需注意 `ActionBar.vue` 冲突。

````text
【家庭麻将 · v1.1.0 · I5 · 结算庄家标记与提示字号（U-3 / U-4）】

## 目标
结算面板四位牌友中给庄家加"庄"徽标；牌桌吃碰提示语整体放大 2 号（桌面 12→14、手机 11→13、动作条按钮 14→16），桌面与手机同口径。

## 前置
I4 通过（`ActionBar.vue` 已改完，避免同文件冲突）。

## 必须先读
- plan/改进和错误修复文档.md §3 U-3 / U-4
- code/frontend/src/components/table/ResultModal.vue（`:214-241` 四家卡片、`:57` `winnerIsDealer`）
- code/frontend/src/components/table/PlayerSeat.vue（现有庄家徽标样式）
- code/frontend/src/views/RoomView.vue（`:355` 横幅、`:707-716` ResultModal 挂载）
- code/frontend/src/mobile/views/MobileRoomView.vue（`:333` 横幅、`:559-566` 挂载）
- code/frontend/src/components/table/ActionBar.vue（`:39/41/76/85`）
- plan/05-UI设计.md（设计系统、结算页）

## 任务
1. `ResultModal.vue` 四家卡片名字前加"庄"徽标，条件 `seat.seat === dealerSeat`；样式复用 `PlayerSeat.vue` 的 `isDealer` 徽标；荒庄与连庄同样显示。
2. 若"家家手牌区"同步加标，用 `final_hand.seat === dealerSeat`，**不改** `FinalHand` 类型与后端。
3. 字号 +2：桌面横幅 `text-xs` → `text-sm`、`px-3.5 py-1.5` → `px-4 py-2`；手机横幅 `text-[11px]` → `text-[13px]`、`px-3 py-1` → `px-3.5 py-1.5`；`ActionBar.vue` 标签 `text-[11px]/text-xs` → `text-[13px]/text-sm`，按钮 `text-sm` → `text-base`。
4. 05 §设计系统补"牌桌提示语"字号档位表（banner 14/13px、标签 13px、按钮 16px）；§结算页补徽标规格（位置/字号/颜色 token/长名截断）。
5. 自测 375×667 与 667×375 两种视口，确认不折行、不遮挡、无横向滚动。

## 验收清单
- [ ] 桌面与手机结算页：庄家卡片有"庄"标记，其余没有；荒庄、连庄、换庄三种情形正确。
- [ ] 8 字昵称 + 徽标不撑破卡片（`truncate` 生效）。
- [ ] 吃/碰/抢杠提示字号实际为 14/13px，动作条按钮 16px。
- [ ] 最长文案（`妈妈 吃 三四五万`）在 375px 宽下不折行、不遮挡牌河。
- [ ] `npm run typecheck` 与 `npm run build` 通过。
- [ ] 05 文档已回写字号档位与徽标规格。

## 硬约束
- 不改后端、不改协议、不改 `types.ts` 的协议字段（纯渲染）。
- 不引入新组件库或全局 CSS 重写；沿用 Tailwind 类与既有 token。
- 桌面与手机不得只改一处。

## 完成后必须输出
1. 改动文件清单 + 字号前后对照表。
2. 桌面/手机截图或视口自测记录。
3. 05 文档改动摘要。
````

---

## I6 · 全量回归与手测

> **什么时候做**：I1–I5 全部通过后、发版前。

````text
【家庭麻将 · v1.1.0 · I6 · 全量回归与手测】

## 目标
在本地把 v1.1.0 的全部改动做一次端到端回归，产出可直接用于发版的验收报告；不新增功能。

## 前置
I1–I5 全部通过；本地 MySQL（`mahjong_data` 或 `mahjong_test`）已按 `database/*.txt` 建表并跑过 `seedPresets`。

## 必须先读
- plan/改进和错误修复文档.md §6 验收与回归矩阵
- plan/06-实施计划.md 测试矩阵
- plan/07-柏氏规则细则.md §13

## 任务
1. 后端全量：`cd code/backend/src && pytest -q`；记录总数与失败项（应为 0）。
2. 前端：`npm run typecheck`、`npm run build`；确认产物同时含桌面与 `/mjmobile` 入口。
3. 规则手测：按 07 §13-09 / 32 / 33 / 34 逐条核对结算面板（含副露、点炮、自摸、抢杠）。
4. 交互手测：同座位胡+碰（两段式）、234556 万吃 4 万（三选）、取消/改选/过/超时。
5. 收尾手测：打满一场（1 圈房与 4 圈房各一次）、中途结束、重复点击、断网点击、从大厅关桌、回大厅后列表刷新。
6. 视觉手测：庄家徽标、字号 +2、375×667 与 667×375。
7. 产出 `plan/v1.1.0-验收报告.md`（临时文件，发版后可删或并入 06）：逐条勾选 + 证据（命令输出/截图路径）。

## 验收清单
- [ ] `pytest -q` 0 失败（记录总数）。
- [ ] `npm run typecheck` 0 error；`npm run build` 成功。
- [ ] 规则 4 条、交互 5 条、收尾 7 条、视觉 3 条全部通过并留证。
- [ ] 回归专项：出牌单选、观战快照、断线重连、旁观 10 人上限未被破坏。
- [ ] 验收报告已产出，遗留问题清单明确"是否阻塞发版"。

## 硬约束
- 本步只修回归缺陷，不夹带新功能；发现新需求记入遗留问题。
- 不修改 `plan/07` 的既有数值（如发现文档与实现不一致，回到 I0 口径重新确认）。

## 完成后必须输出
1. 测试命令与结果摘要（总数/通过/失败）。
2. 验收报告路径与逐条结论。
3. 阻塞发版的问题清单（应为空）。
````

---

## I7 · 发版与验收回写

> **什么时候做**：I6 报告无阻塞项后。

````text
【家庭麻将 · v1.1.0 · I7 · 发版与验收回写】

## 目标
把 v1.1.0 发布到 `https://www.iottest.online/majiangapp/`，版本号三处统一为 `1.1.0`，清理历史幽灵房，回写文档状态。

## 前置
I6 通过；本机可 `npm run build`；SSH 私钥 `D:\data\keys\codeops_ed25519` 可用。

## 必须先读
- plan/改进和错误修复文档.md §7 风险与回滚
- docs/部署.md、docs/运维与备份.md
- `code/deploy/12_redeploy.sh`、`code/deploy/14_close_stale_rooms.sh`

## 任务
1. 版本号：`config/basicSettings.py` `VERSION="1.1.0"`；`code/frontend/package.json` `"version":"1.1.0"`；提交后确认 `/api/health` 回显 `1.1.0`。
2. 本机构建：`cd code/frontend && npm run build`；打包 `dist` 与 `code/backend/src`（排除 `.env`、`__pycache__`）。
3. 上传：`scp` 到 `~/mj_deploy2/{backend,dist}.tar.gz`；执行 `sudo bash ~/mj_deploy2/12_redeploy.sh`（备份 → rsync --delete → pip → restart → 健康检查）。
4. 种子：`sudo -u majiang /data/majiang/venv/bin/python tools/seedPresets.py --env prod`（或按部署脚本既有方式），确认 `baishi_default` 的 `fan_table` 为 34 项。
5. 数据清理：执行 `14_close_stale_rooms.sh`（先备份，再按白名单关闭遗留 OPEN 房），输出影响行数。
6. 冒烟：登录 → 开柏氏桌 → 打 1 局（验证 258 赢/断幺/13不靠/连六）→ 结束牌局 → 回大厅确认列表无该房；手机端同样跑一遍。
7. 回写文档：`plan/README.md` 变更记录、`plan/step-prompts.md` 的 I 系列状态、`plan/家庭麻将总体规划文档.md` §10 P8、`plan/06-实施计划.md` 勾选；`plan/07` 状态行改 `v1.9 已实施`。
8. 打 tag（如需）：`git tag v1.1.0`（按仓库既有习惯）。

## 验收清单
- [ ] `/api/health` 返回 `1.1.0`；前端页面无版本不一致提示。
- [ ] 生产 `mj_rule_template` 中 `baishi_default.configJson.fan_table` 34 项。
- [ ] `SELECT COUNT(*) FROM mj_room WHERE roomStatus='OPEN'` = 0（无人在玩时）。
- [ ] 打 1 局柏氏：258 赢 / 断幺 / 13不靠 / 连六 至少各命中 1 次并在结算面板正确显示。
- [ ] 结束牌局后大厅列表立即不含该房；重复点击无报错。
- [ ] 桌面与手机各跑通一次完整流程。
- [ ] 文档状态回写完成，`plan/` 内链接无死链。

## 硬约束
- 发版避开对局时段（重启会中断进行中对局）。
- 数据库无 DDL；若脚本要求 MySQL 写权限，走既有 `sudo` 与 `.env` 口令方式，不落明文。
- 生产改动前必须有备份（`/data/backup/`），回滚路径在 07 §7 已写明。

## 完成后必须输出
1. 发布记录（时间、版本、备份文件名、影响行数）。
2. 冒烟结果（逐条 + 证据）。
3. 文档回写清单与遗留问题。
````

---

## I8 · 一场时长（F-1：默认 4 圈，开桌可选）

> **什么时候做**：I1 通过后即可做（与 I2–I5 无文件冲突，但 `snapshot.py` 与 `room.py` 若同时改需串行）。

````text
【家庭麻将 · v1.1.0 · I8 · 一场时长（默认 4 圈，开桌可选）】

## 目标
把「一场 = 一圈（4 局）」改成「一场 = N 圈 × 每圈 4 个庄次」，N 默认 4、开桌时可选 1/2/4/8；整场只抽一次座，保留庄家胡牌连庄；顶栏显示「第 x/y 圈 · 第 a/4 局」。

## 前置
I1 通过（`room.py` 的收尾口径已稳定）；I0 已冻结「圈风刻仍按局风」的口径。

## 必须先读
- plan/改进和错误修复文档.md §4A F-1
- plan/03-规则族设计.md §3.4（抽座、轮庄、场与圈）、§4（配置项）、错误码
- plan/04-协议设计.md §6 #25（开桌 `circles`）、§9.4（`event.round_started/restarts`）、§9.5（圈/局字段）
- plan/05-UI设计.md §4.3 创建牌桌、§4.5 顶栏、§8 验收 15/16
- code/backend/src/game/families/generic/config.py（`ROUNDS_PER_GAME`、`RuleConfig`、`brief()`）
- code/backend/src/realtime/room.py（`_next_dealer_state`、`_next_round`、`_on_settled`、`_begin_game`）
- code/backend/src/realtime/snapshot.py、game/engine.py（`snapshot_options`、`round_started`）
- code/backend/src/processor/roomService.py（`createRoom`）、schemas/room.py、main/api/rooms.py

## 任务
1. 配置：`generic/config.py` 增 `CIRCLES_PER_GAME=4`、`ALLOWED_CIRCLES_PER_GAME=(1,2,4,8)`、字段 `circles_per_game` 与校验文案「一场圈数只能选 1、2、4 或 8 圈」；`brief()` 带上；`baishi/config.py` 同步（同一字段与校验）。
2. 纯函数：`room.py::nextRoundState(dealerSeat, roundWind, circleNo, nextDealer, roundsPerCircle=4, totalCircles=4) -> (dealer, wind, circle, finished)`；连庄不动、下庄 wind+1、wind 攒满换圈、圈数超限收场。
3. 房间：`self.circle_no`（开局置 1）、`self.dealer_continue`；`_next_dealer_state` 调 `nextRoundState` 并把 4 元组传给 `_next_round`；`create_engine(..., circle_no=...)`；`_on_settled` 用第 4 位 `finished`；座位整场只抽一次（换圈不重抽）。
4. 引擎/快照：`GameEngine(circle_no=1)` 并在 `round_started/round_restarted/settled` 事件里带 `circle_no`；`snapshot_options()` 增 `circle_no/rounds_per_circle/circles_per_game`；快照增 `circle_no/total_circles/rounds_per_circle/round_in_circle/dealer_continue`，`game_total_rounds` = 每圈局数 × 圈数。
5. 开桌覆盖：`RoomCreateRequest.circles: int|None`；`createRoom(..., circles=None)` 用 `_applyCirclesOverride` 只改本房 `ruleSnapshot.config/options`，非法值 `RULE_CIRCLES_INVALID`；`_snapshotOptions()` 与错误码映射同步。
6. 前端：`CreateRoomDialog.vue` 与 `MobileCreateRoomSheet.vue` 加「打几圈」选择（默认跟随模板 `circles_per_game`，手选后不被覆盖）并把 `circles` 放进 `POST /rooms`；`RuleForm.vue` 加圈数下拉（缺字段补 4）；`ScoreBoard.vue` / `MobileScoreBoard.vue` 显示圈与局 +「（连庄）」，桌面/手机 `RoomView` 传新 props；`types.ts` 增可选字段。
7. 测试：新增 `tests/test_game_length.py`（配置合法/非法、纯函数连庄/换圈/收场、引擎圈序、开桌覆盖与非法值）；把 `test_four_rounds_close_the_circle` 改成「4 局只换圈」并新增 1 圈房收场用例；`conftest.make_engine` 支持 `circle_no`。
8. 文档：00 §4.7 F-1、G4/G10/G12/G14、D13/D21、P9、验收 15；03 §3.4/§4/错误码/验收 13；04 §6 #25、§9.4、§9.5；05 §4.3/§4.5/验收 15-16；06 §8B；07 §2、§12 Q3/Q11；docs/系统总览.md。

## 验收清单
- [ ] `RuleConfig(circles_per_game=3)` 被拒；`1/2/4/8` 通过；老模板缺字段按 4 圈。
- [ ] 4 圈房打完第 4 局仍 `playing`（`circle_no=2`、`round_in_circle=1`、局风回东、`seats_drawn` 仍 1 次）。
- [ ] 1 圈房 4 个庄次收场；8 圈房 32 个庄次收场；连庄局 `dealer_continue=true` 且局风/圈序不动。
- [ ] 开桌 `circles=2` 只改本房快照（`config`/`options` 均 2），模板仍 4；非法值 400。
- [ ] 桌面/手机顶栏显示「第 x/y 圈 · 第 a/4 局」，单圈房只显示局数，375×667 不折行。
- [ ] `pytest -q` 全绿；`npm run typecheck`、`npm run build` 通过。

## 硬约束
- `rounds_per_game` 仍是「每圈局数」（固定 4），不要复用它当圈数；圈数一律走 `circles_per_game`。
- 圈风刻口径不变（按本局局风判定），圈序只用于显示与收场。
- 开桌覆盖只写房间快照，**不得**改模板 `configJson`。
- 无 DDL：`mj_game_round.roundWind` 仍表示圈内局风，不新增列；不新增 `mj_*` 表。

## 完成后必须输出
1. 改动文件清单 + 圈数在配置/快照/事件三处的字段对照。
2. `pytest tests/test_game_length.py -q` 与全量回归结果。
3. 手测记录：1 圈房收场、4 圈房换圈不重抽、连庄、开桌选 2 圈。
````

---

## 附：步骤依赖与产出

| 步骤 | 依赖 | 主要产出 | 可否独立上线 |
| --- | --- | --- | --- |
| I0 | — | 口径冻结 + 34 项对照表 | 否（文档） |
| I1 | I0 | 房间收尾幂等 + 兜底 + 清理脚本 | 是（`1.1.0-rc1` 热修） |
| I2 | I1 | 番表 34 项 + 预置模板同步 | 是（`1.1.0-rc2`） |
| I3 | I2 | 两段式询问 + 过胡 | 否（需 I4 同版） |
| I4 | I3 | 吃牌选两张 + 严格校验 | 是（与 I3 同版） |
| I5 | I4 | 庄标 + 字号 | 是 |
| I6 | I1–I5、I8 | 验收报告 | 否（内部） |
| I7 | I6 | 生产发布 + 文档回写 | — |
| I8 | I1 | 圈数配置/快照/开桌/顶栏 | 是（与 I1–I5 同版） |

# 家庭麻将 · v1.1.0 分步改进指令（improve step-prompts）

> 配套：[改进和错误修复文档.md](改进和错误修复文档.md)（问题台账与方案）｜[家庭麻将总体规划文档.md](家庭麻将总体规划文档.md)｜[07-柏氏规则细则.md](07-柏氏规则细则.md)｜[04-协议设计.md](04-协议设计.md)｜[05-UI设计.md](05-UI设计.md)｜[06-实施计划.md](06-实施计划.md)
>
> **使用方法**：每一步**单独开一个新对话**，把该步 `text` 围栏内的提示语整段复制过去。
> 前一步验收未通过，不要开始下一步。
> 每步结束统一输出：**改动文件清单 + 验收结果 + 遗留问题**。
>
> 与 [step-prompts.md](step-prompts.md) 的关系：S0–S10 是 v1.0.x 的重制步骤（已完成并上线）；本文 **I0–I8 是 v1.1.0 的运行反馈修复步骤**（接在 S10 之后），**I9–I12 是 2026-10-31 第二轮追加步骤**（一只幺 / 13不靠 判番 / 牌面人声报牌 / 胡张标记），**I13–I14 是 2026-10-31 第三轮追加步骤**（庄家徽标跟随 / 叫牌人声）。

## 当前状态（2026-10-31）

| 步骤 | 范围 | 版本 | 状态 |
| --- | --- | --- | --- |
| S0–S10 | 重制：目录/MySQL/账号/家庭/数据层/观战/规则族/皮肤/音效/前端与部署 | v1.0.x | 已完成并上线（`https://www.iottest.online/majiangapp/`） |
| **I0** | 基线核对与口径冻结（只改文档） | v1.1.0 | 已完成 |
| **I1** | 房间生命周期收尾（B-1） | v1.1.0 | 已实施（已随 v1.1.0 于 2026-10-30 上线生产） |
| **I2** | 柏氏番表：258 赢 / 十三不靠 / 连六 / 断幺（R-1～R-4） | v1.1.0 | 已实施（已随 v1.1.0 于 2026-10-30 上线生产） |
| **I3** | 胡牌优先与过胡（U-1） | v1.1.0 | 已实施（已随 v1.1.0 于 2026-10-30 上线生产） |
| **I4** | 吃牌选两张（U-2） | v1.1.0 | 已实施（已随 v1.1.0 于 2026-10-30 上线生产） |
| **I5** | 结算庄家标记与提示字号（U-3 / U-4） | v1.1.0 | 已实施（已随 v1.1.0 于 2026-10-30 上线生产） |
| **I6** | 全量回归与手测 | v1.1.0 | 已完成（验收报告：[v1.1.0-验收报告.md](v1.1.0-验收报告.md)） |
| **I7** | 发版与验收回写 | v1.1.0 | 已完成（2026-10-30 上线生产，记录见 [I7-发布记录.md](I7-发布记录.md)） |
| **I8** | 一场时长：默认 4 圈、开桌可选（F-1） | v1.1.0 | 已实施（已随 v1.1.0 于 2026-10-30 上线生产） |
| **I9** | 柏氏番表 35 项：一只幺（R-5） | v1.1.1 | **已实施（2026-10-31；番表 35 项 + 用例 35 全绿，`pytest tests/test_baishi_s7.py -q` 90 passed）** |
| **I10** | 十三不靠不再计门清与独赢（R-6） | v1.1.1 | **已实施（2026-10-31；`thirteen_unrelated_fans()` 删 `du_ying`、过滤 `men_qian`（保留 `situational_hits` 其余 5 个番种），`pytest tests/test_baishi_s7.py -q` 93 passed、全量 372 passed）** |
| **I11** | 牌面人声报牌音效（S-1） | v1.1.1 | **已实施（2026-10-31；34 个 mp3 + `voiceMap.ts` + `playVoice()`（P3、全局 250ms）+ `preloadVoices()` 空闲分批预热 + nginx `*/audio/voice/` 30 天缓存，`voice/` 294.3 KB，协议零改动）** |
| **I12** | 结算页明显标记胡牌的那张牌（V-1） | v1.1.1 | **已实施（2026-10-31；`winning_tile_index` + 四档「胡」角标，`pytest -q` 373 passed，`npm run typecheck` / `npm run build` 通过，取证见 `plan/I12-evidence/`）** |
| **I13** | 牌桌「庄」徽标跟随庄家轮转（U-5） | v1.1.2 | **已实施（2026-10-31；判定下沉到座位组件 `isDealerSeat = props.isDealer \|\| props.seat.is_dealer === true`（`PlayerSeat.vue` 1 处 / `MobileSeatChip.vue` 2 处改 `v-if`），两端「自己」内联块各补 1 处徽标（桌面 16px / 手机 14px）；桌面四席 + 手机四席同一时刻仅 1 个徽标且跟随换庄、连庄不动、waiting 无徽标、观战视角反映被观战者；`npm run typecheck` 0 error / `build` / `build:mobile` 通过，自动化断言 70/70 全绿，取证见 `plan/I13-evidence/`；协议零改动、无 DDL）** |
| **I14** | 吃 / 碰 / 胡 / 杠 改用叫牌人声（S-2） | v1.1.2 | **已实施（2026-10-31；`voice/` 扩到 40 个 mp3（372,225 B ≈ 363.5 KB）+ `SoundSpec.dir` 字段 + 6 个 `*_voice` 枚举键（`SOUND_KEYS` 仍 15）+ `useGameSounds` 6 处接线；`audioManager.ts` / `voiceMap.ts` 零改动；旧 6 个合成音文件保留不触发；桩件 87/87 + 降级两场景全绿；`npm run typecheck` / `build` / `build:mobile` 通过；协议零改动、无 DDL）** |

**下一步**：I13 / I14 均已实施完成并**随 v1.1.2 于 2026-10-31 16:28 上线生产**（纯前端、协议零改动、无 DDL；按用户要求本次未做冒烟，发版记录见 [v1.1.2-发布记录.md](v1.1.2-发布记录.md)）。I9–I12 已随 v1.1.1 于 2026-10-31 上线生产（发版记录见 [v1.1.1-发布记录.md](v1.1.1-发布记录.md)）。

> **2026-10-31 第二轮追加（已完成）**：I9–I12 四步的文档口径已全部定稿（07 v1.10、08 修订、04 §9.5、05 §4.5、改进台账 R-5/R-6/S-1/V-1、06 §8C），并已**全部实施**、随 **v1.1.1** 于 2026-10-31 上线生产。历史顺序要求（存档）：I9 与 I10 同改 `fan.py`，必须串行；I11 与 I12 无文件冲突，可并行。
>
> **2026-10-31 第三轮追加（v1.1.2）**：I13（U-5 庄徽标跟随）与 I14（S-2 叫牌人声）两步的文档口径已全部定稿（05 牌桌规格与验收 26、08 v1.2 的 §2.2 / §4.2 / §6.2 / §6.3、改进台账 §3 U-5 与 §3A-2 S-2、06 §8D、00 §4.6 E8 / §4.7 / §9 D24-D25 / §10 P11 / 验收 20–22），**协议零改动、无 DDL**，两步**无文件冲突、可并行**。
>
> **2026-10-31 第三轮实施进度**：**I13（U-5 庄徽标跟随）已实施完成**（判定下沉到 `PlayerSeat.vue` / `MobileSeatChip.vue` 的 `isDealerSeat` computed + 两端「自己」内联块各补 1 处徽标；桌面 / 手机四席全部跟随换庄；自动化断言 70/70 全绿，取证见 `plan/I13-evidence/`）；**I14（S-2 叫牌人声）已实施完成**（`voice/` 40 个 mp3、`SoundSpec.dir` 字段、6 个 `*_voice` 枚举键、`useGameSounds` 6 处接线；`audioManager.ts` / `voiceMap.ts` / `sfx/` / nginx 全部零改动）。两步均协议零改动、无 DDL，待统一重建发布。

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
- I9 · 柏氏番表 35 项：一只幺（R-5）
- I10 · 十三不靠不再计门清与独赢（R-6）
- I11 · 牌面人声报牌音效（S-1）
- I12 · 结算页明显标记胡牌的那张牌（V-1）
- I13 · 牌桌「庄」徽标跟随庄家轮转（U-5）
- I14 · 吃 / 碰 / 胡 / 杠 改用叫牌人声（S-2）

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

## I9 · 柏氏番表 35 项：一只幺（R-5）

> **什么时候做**：**文档已批准后**立即做。与 I10 同改 `fan.py`，**必须串行**（先 I9 后 I10，或反之，但不可并行）。
> 口径已确认（用户 2026-10-31）：**一只幺 = 胡牌后的 14 张牌里面只有一只幺**；成立路径 = 恰有一组 123 / 789 顺子（端张为幺），其余全为 2–8 数牌。

````text
【家庭麻将 · v1.1.1 · I9 · 柏氏番表 35 项：一只幺（R-5）】

## 目标
柏氏番表由 34 项增加到 35 项，新增番种「一只幺」：**胡牌后的 14 张牌（含副露）里只有一只幺牌**（数牌 1、9 与字牌）时计 1 番，不占任何互斥组、非计数型；与「断幺」天然互斥。

## 前置
- 文档已批准：[07-柏氏规则细则.md](07-柏氏规则细则.md) 已是 v1.10（§5 已含 `yi_zhi_yao` 行、§6.4.9 条款、§12 Q12、§13 用例 35）。
- 口径已由用户确认，无需再问：按**张数**计、统计范围是胡牌后的整手 14 张牌（含副露摊平）。

## 必须先读
- plan/07-柏氏规则细则.md §5（番表 35 项）、§6.4.8（断幺）、§6.4.9（一只幺）、§12 Q12、§13 用例 35
- plan/改进和错误修复文档.md §2A R-5
- plan/03-规则族设计.md §7.1、§7.2、§7.3 L11
- code/backend/src/game/families/baishi/fan.py（`FAN_TABLE` `:36-72`、`is_all_simples()` `:314-319`、`duan_yao_hit()` `:333-335`、`global_fans()` `:338-344`、`__all__` `:683-719`）
- code/backend/src/game/families/baishi/config.py（`default_fan_table()` `:40-45`、`FAN_MAX` `:31-34`）
- code/backend/src/game/families/baishi/presets.py（`baishi_default` `:48-56`）、`__init__.py` docstring
- code/backend/src/game/families/baishi/selfcheck.py（`REQUIRED_CASES` `:14-52`）
- code/backend/src/tests/test_baishi_s7.py（`:99-136` 番表一致性断言、`:860-904` 断幺用例）
- code/backend/src/game/hand.py（`HandContext`：`:49-91`、`all_tiles()`、`is_honor`、`rank_of`）

## 任务
1. `fan.py` 的 `FAN_TABLE` 增一行 `("yi_zhi_yao", "一只幺", 1, None, False)`，**必须插在 `duan_yao` 之后**（07 §5 的表格行序 ≡ `FAN_TABLE` 元组序，markdown 比对测试按序断言）。
2. 判定：新增 `yi_zhi_yao_hit(ctx)` —— 用 `ctx.all_tiles()`（手牌 + 全部副露摊平 = 胡牌后的 14 张牌）**逐张**统计「幺牌」张数：数牌 rank ∈ {0, 8}（1、9）或 `is_honor(tile)`（东南西北中发白）。张数**恰好为 1** 时返回 `[FanHit("yi_zhi_yao")]`。
   - ⚠️ **必须逐张计，不要按「组」归类**：幺牌除了出现在 将(2) / 刻(3) / 杠(4) 外，还会出现在 **123 / 789 顺子的端张**（`fan.py:154` 的顺子起点条件 `first % 9 <= 6` 允许 123 与 789）—— 只统计成组的牌会漏判、导致该番永不命中。
   - ⚠️ **按张数、不按「种」**：「1 万 + 东」是 2 张幺（2 种），不成立。
3. 挂接：在 `global_fans()` 里与 `duan_yao_hit(ctx)` 并列追加 `*yi_zhi_yao_hit(ctx)`；`__all__` 导出新函数。不要在具体牌型函数里逐处挂接。
4. 文案同步：`config.py` `default_fan_table()` docstring、`presets.py` 的 `baishi_default` description、`__init__.py` docstring 里的「34 项」改为「35 项」。
5. 自检：`selfcheck.REQUIRED_CASES` 增 `07-13-35`（一只幺，含正例与反例）。
6. 测试（`tests/test_baishi_s7.py`）：
   - `:99-110` 的 `len(RULE.fan_table) == 34` → `35`、`len(FAN_TABLE) == 34` → `35`；`:113-136` 的 markdown 比对断言 `len(rows) == 34` → `35`（解析器按 07 §5 表格顺序逐项比对，**表头与列数不得改动**）；
   - 新增用例：
     - 正例：`123万 456万 678万 234筒 55筒`（幺 = 1 万）→ 一只幺 1；`789万 234万 456万 567条 22条`（幺 = 9 万）→ 一只幺 1；
     - 反例：`123万 789万 456万 234筒 55筒`（2 张）→ 0；`123万 123筒 456万 234筒 55筒`（2 张）→ 0；东东作将（2 张）→ 0；东东东成刻（3 张）→ 0；明杠东（4 张）→ 0；全 2–8 数牌（0 张）→ 0（那是断幺）；
     - 副露：吃出来的 123 顺子同样贡献 1 张幺；副露含 123 顺子 + 暗牌无幺 → 一只幺 1；
     - 恒 0：七对 / 十三幺 / 全幺 / 全文字 / 13不靠；与断幺互斥。
7. 种子：`python tools/seedPresets.py --env <env>`，确认预置模板 `baishi_default` 的 `fan_table` 为 35 项。
8. 文档回写：07 状态行与修订历史、03 §7.1/§7.2/§7.3、06 §8C 勾选、改进台账 R-5 的「修复方案/验收标准」补实际实现细节。

## 验收清单
- [ ] `len(FAN_TABLE) == 35`、`len(RULE.fan_table) == 35`；07 §5 表格与 `FAN_TABLE` **逐项顺序一致**（`test_baishi_fan_table_matches_07_section_5_markdown` 通过）。
- [ ] 一只幺正反例全绿（**按张数**、**顺子端张计入**、副露计入、与断幺互斥、七对与 `quan` 组恒 0）。
- [ ] 07 §6.4.9 / §12 Q12 / §13-35 三处口径与实现一致（均为「胡牌后 14 张牌里恰好 1 张幺牌」）。
- [ ] 断幺、258赢、连六、13不靠 等既有番种用例全部仍通过（`pytest tests/test_baishi_s7.py -q` 全绿）。
- [ ] `python tools/seedPresets.py` 后预置模板 35 项。
- [ ] `pytest -q` 无新增失败。

## 硬约束
- 番表项数、id、名称、番值、互斥组、计数标记必须与 07 §5 表格**逐字一致**（否则 markdown 比对测试直接失败）。
- 新番种一律 **1 番 / 互斥组 `None` / 非计数型**；不臆造倍率。
- **统计范围是胡牌后的整手 14 张牌**（含副露摊平），不是"手牌 13 张"、也不是"不含副露"。
- 不改其它番种的数值与判定；不改协议、不改前端（番表由 `config.fan_table` 动态渲染）。
- 不回溯历史局的 `fanItemsJson`；旧房 `ruleSnapshot` 冻结旧配置。
- 与 I10 同改 `fan.py`，不可并行。

## 完成后必须输出
1. 改动文件清单 + `FAN_TABLE` 新增行与 07 §5 新增行的逐字对照。
2. 一只幺判定实现说明（逐张统计口径 + 顺子端张如何被计入）。
3. `pytest tests/test_baishi_s7.py -q` 与全量 `pytest -q` 结果（总数/通过/失败）。
4. 遗留问题。
````

---

## I10 · 十三不靠不再计门清与独赢（R-6）

> **什么时候做**：I9 之后（与 I9 同改 `fan.py`，必须串行）。

````text
【家庭麻将 · v1.1.1 · I10 · 十三不靠不再计门清与独赢（R-6）】

## 目标
13不靠 的判番范围里删去「门清 1 番」与「独赢 1 番」：13不靠 仍为 10 番，仍计将牌、缺门、混一色/清一色；典型手牌由 13–14 番降为 11–12 番。

## 前置
I9 已通过（`fan.py` 已改过一轮，避免同文件冲突）。

## 必须先读
- plan/07-柏氏规则细则.md §6.3.4（第 4 条 13不靠 判番范围）、§6.6（门清）、§6.7（将牌）、§6.8（独赢）、§12 Q13、§13 用例 36
- plan/改进和错误修复文档.md §2A R-6
- plan/03-规则族设计.md §7.3 L5
- code/backend/src/game/families/baishi/fan.py（`thirteen_unrelated_fans()` `:610-624`、`situational_hits()` `:347-363`、`unrelated_pair()` `:224-261`、`thirteen_orphans_fans()` `:594-607`）
- code/backend/src/tests/test_baishi_s7.py（`:319-386` 13不靠 用例）
- code/backend/src/game/families/baishi/selfcheck.py

## 任务
1. `thirteen_unrelated_fans()`：
   - 删除 `hits.append(FanHit("du_ying"))`；
   - 把 `hits.extend(situational_hits(ctx))` 改为**只保留非 `men_qian` 的命中**（例如 `hits.extend(hit for hit in situational_hits(ctx) if hit.id != "men_qian")`）；
   - **不得整体删掉 `situational_hits(ctx)` 调用** —— 它同时产出天胡、地胡、杠上开花、海底捞月、抢杠胡 5 个番种。
2. `FAN_TABLE` **不改**：`men_qian` / `du_ying` 仍是其它牌型要用的番种，只是 13不靠 不再命中。
3. `thirteen_orphans_fans()`（十三幺）**不改**：十三幺仍为 102 番（100 + 幺将 1 + 门清 1）。
4. 测试（`tests/test_baishi_s7.py` `:319-386`）改写：
   - `ids["du_ying"] == 1` → `"du_ying" not in ids`；
   - `ids["men_qian"] == 1` → `"men_qian" not in ids`；
   - `fan_total == 14` → `== 12`（缺门变体），三门齐变体 13 → 11；
   - 新增断言：命中清一色/混一色时相应减 2；13不靠 的牌型成立条件不变（有副露仍不成立）。
5. 自检：`selfcheck.REQUIRED_CASES` 增 `07-13-36`。
6. 回归重点：标准胡的 `men_qian` / `du_ying` 仍照常判定（07 §13-19、§13-20 用例全绿）；天胡/地胡/杠上开花/海底捞月/抢杠胡 5 个番种的用例全绿。
7. 文档回写：07 状态行与修订历史（v1.10 已写，实施后把状态标为"已实施"）、03 §7.3 L5、06 §8C 勾选、改进台账 R-6 补实现细节。

## 验收清单
- [ ] `147m258p369s5z6z7z9m9m`（三门齐）→ 13不靠 10 + 将牌 1 = **11 番**，`men_qian` 与 `du_ying` 均不在 ids 中。
- [ ] 其缺门变体 → **12 番**。
- [ ] 命中清一色/混一色时相应再减 2。
- [ ] 十三幺仍 102 番；标准胡的门清/独赢不受影响；天胡/地胡/杠上开花/海底捞月/抢杠胡 5 个番种用例全绿。
- [ ] `pytest tests/test_baishi_s7.py -q` 与 `pytest -q` 全绿。
- [ ] `selfcheck.REQUIRED_CASES` 含 `07-13-36`。

## 硬约束
- **只删 13不靠 的两条命中**，不动 `men_qian` / `du_ying` 番种本身，也不动其它牌型。
- 13不靠 的**牌型成立条件不变**（有副露仍不成立）；取消的是"门清番"，不是"允许副露"。
- 番表项数与内容不变（35 项）；本步不碰 `FAN_TABLE`。
- 不改协议、不改前端、不加 DDL。

## 完成后必须输出
1. 改动文件清单 + `thirteen_unrelated_fans()` 改动前后对照。
2. 13不靠 三种情形（三门齐 / 缺门 / 单花色）的番值明细表。
3. `pytest -q` 结果与回归结论。
````

---

## I11 · 牌面人声报牌音效（S-1）

> **什么时候做**：I9 / I10 之后。与 I12 无文件冲突（`src/audio/*` vs `src/components/table/*`、`src/views/*`），**可并行**。

````text
【家庭麻将 · v1.1.1 · I11 · 牌面人声报牌音效（S-1）】

## 目标
出牌后除原有落牌底噪外，叠加播放该张牌的女声报牌音（34 个：一万～九万、一筒～九筒、一条～九条、东南西北中发白），逐张区分。现有 15 个 SFX 与 6 个叫牌音**全部保留不变**。协议零改动。

## 前置
- 08-音效设计.md 已修订（§1.2 放开限制、§2.1 触发口径、§3 规则 6 全局 250ms 间隔、§4.5 实现路径、§6.2 资源规格、§6.3 授权风险登记、§8 验收 13–19）。
- 素材在 `plan/majiang_sound/women_mp3/`（40 个 mp3，取其中 34 个牌面音）。

## 必须先读
- plan/08-音效设计.md §1.2、§2.1、§3（含规则 6）、§4.5、§6.2、§6.3、§8 第 13–19 条
- plan/改进和错误修复文档.md §3A S-1
- code/frontend/src/audio/soundKeys.ts（`SoundKey` `:9-24`、`SoundSpec` `:29-38`、`SOUND_SPECS` `:40-56`、`sfxUrl()` `:70-72`）
- code/frontend/src/audio/audioManager.ts（常量 `:11-16`、`loadOne()` `:202-234`、`preloadSounds()` `:240-246`、`playSound()` `:364-418`、`makeRoom()` `:278-290`、`unavailable` 降级）
- code/frontend/src/audio/useGameSounds.ts（`handleSoundEvent()` `:26-90`，`event.discarded` 在 `:63-65`）
- code/frontend/src/utils/tile.ts（`tileKey()` `:92-98`）
- code/frontend/src/stores/game.ts（`:6-7`、`:204-206`、`:273-275`）
- code/deploy/nginx-majiang.conf（`*/audio/sfx/` 的缓存规则 `:56-61`、`:82-87`）

## 任务
1. **资源**：新建 `code/frontend/public/audio/voice/`，从 `plan/majiang_sound/women_mp3/` 复制 **34 个**牌面 mp3（`1wan…9wan`、`1tong…9tong`、`1tiao…9tiao`、`dongfeng/nanfeng/xifeng/beifeng/zhong/fa/bai`）。**不要复制** `hu`/`pong`/`chow`/`kong_*` 6 个叫牌音。
2. **来源登记**：在 `voice/` 下写 `LICENSE.md`，原样登记：来源仓库 `1RGameSol/Mahjong-1`（<https://github.com/1RGameSol/Mahjong-1>）、路径 `Assets/Resources/Sound/g_*.ogg`、**源仓库未提供 LICENSE、权利归属不明**、**用户已于 2026-10-31 明确接受该风险并要求直接发布**、替换时保持文件名不变即可不改代码。同时在 `public/audio/sfx/LICENSE.md` 增一条指向 `voice/` 的登记。
3. **映射**：新建 `code/frontend/src/audio/voiceMap.ts`，导出 `VOICE_BASENAME_BY_TILE`（长度 34 的数组，tile 0–33 → 基名）与 `voiceUrlOf(tile)`（`${import.meta.env.BASE_URL}audio/voice/${base}.mp3`）。素材基名与 `tileKey()`（`1m`/`east`）**不同**，必须显式映射，不得复用 `tileKey()`。
4. **播放**：`audioManager.ts` 增 `playVoice(base, options?)` —— 复用**同一套**并发/优先级/淡出/降级内核，优先级 **P3**、默认音量 55；**新增人声全局 250ms 最短间隔**（与既有"同键 150ms 去重"并列，两者都要生效）；资源未加载时按需加载并沿用既有语义（**本次静音**、`console.debug` 一次）；加载失败标记 `unavailable`。
5. **加载策略**：**不把 34 个加入 `SOUND_KEYS`**（`preloadSounds()` 仍只拉 15 个 SFX）；进桌后用 `requestIdleCallback`（无则 `setTimeout`）**分批预热**，每批 4 个；`navigator.connection.saveData` 为真时**不预热**。
6. **接线**：`useGameSounds.ts` 的 `event.discarded` 分支 —— 在 `play('discard')` **之后**叠加 `playVoice(voiceUrlOf(data.tile))`（底噪保留、人声叠加）；`data.tile` 缺失或越界时静默跳过，不报错。
7. **nginx**：`code/deploy/nginx-majiang.conf` 为 `*/audio/voice/` 补与 `*/audio/sfx/` 同款的 30 天 `max-age` 规则。
8. **构建**：确认 `vite.config.ts` 的 `base`（`/mjmobile/` 或 `/majiangapp/`）下 `public/audio/voice/` 原样进入产物；`npm run build` 与 `npm run build:mobile` 各跑一次。
9. 文档回写：08 §4.5 与 §6.3 补实际实现细节（文件清单、体积实测）、06 §8C 勾选、改进台账 S-1 补实现细节。

## 验收清单
- [ ] 出 1 万 / 2 筒 / 东风 / 中 / 白，语音逐张可辨，**与落牌底噪同时存在**。
- [ ] 34 张牌面全部命中，无错配（不出万牌音、不错花色、字牌不出数牌音）。
- [ ] 连续快速打出两张**不同**牌时人声不叠成噪音（250ms 间隔生效）；同一张牌 150ms 内连出被去重。
- [ ] 关闭音效总开关 → 人声与 15 个 SFX **全部**静音；重新打开/刷新后恢复；音量滑块对人声同样生效。
- [ ] 删除 `voice/` 中任意一个 mp3 → 该牌面静音、其余 33 个正常、控制台无 `error`、对局可打完；删除整个目录时 15 个 SFX 仍全部正常。
- [ ] `hu`（P0）后 200ms 内的报牌被抑制、不叠响；胡牌后下一手出牌仍正常报牌。
- [ ] Network 面板：进桌预加载仍只有 15 个 SFX；报牌为按需/空闲预热的增量请求；`voice/` 目录 ≤400 KB。
- [ ] `npm run typecheck` 与 `npm run build`、`npm run build:mobile` 均通过；**协议零改动**（`git diff` 中无 WS 事件/字段变更）。

## 硬约束
- **不改协议**：不新增 WS 事件或字段，只消费既有 `event.discarded.tile`。
- **不改现有 15 个 SFX 与 6 个叫牌音**：叫牌音一律保留现有合成音。
- **不扩 `SoundKey` 联合类型**：动态键走 `voiceMap.ts`；否则预加载会一次拉 49 个文件、`audioState.total` 失控。
- **不加数据库列、不加用户偏好字段**：随既有总开关与音量生效。
- 人声音量不得盖过 `hu`（P0）；替换同名资源必须改名或加 `?v=`（30 天强缓存）。
- 版权风险已由用户接受，但**必须在 `voice/LICENSE.md` 与 08 §6.3 双处留痕**，不得省略。

## 完成后必须输出
1. 改动文件清单 + 34 个资源的 tile→基名→文件对照表。
2. 体积实测（`voice/` 合计、单文件最大）与首屏请求数对比。
3. 验收清单逐条结论（含删文件降级测试）。
4. 版权留痕位置（`voice/LICENSE.md` 与 08 §6.3）。
````

---

## I12 · 结算页明显标记胡牌的那张牌（V-1）

> **什么时候做**：I9 / I10 之后。与 I11 无文件冲突，**可并行**。

````text
【家庭麻将 · v1.1.1 · I12 · 结算页明显标记胡牌的那张牌（V-1）】

## 目标
胡牌结算时，能一眼看出**是哪张牌胡的**：该张牌加金色「胡」角标 + 双层描金；覆盖自摸、点炮、抢杠胡；同值多张只标一张；结算页（桌面 + 手机）与战绩回放页三处一致。

## 前置
- 04-协议设计.md §9.5 已补 `result.final_hands` 结构与 `final_hands[].winning_tile_index`；05-UI设计.md §4.5 已补「胡」角标规格。

## 必须先读
- plan/04-协议设计.md §9.5（`result.final_hands`）、§11、§12 第 18 条
- plan/05-UI设计.md §4.5（「胡」角标规格表）、§验收第 25 条
- plan/改进和错误修复文档.md §3B V-1
- code/backend/src/game/engine.py（`final_hands_snapshot()` `:124-157`）
- code/frontend/src/types.ts（`FinalHand` `:261-277`、`RoundResult` `:279-297`、战绩 `rounds[].final_hands` `:391-403`）
- code/frontend/src/components/table/Tile.vue（props `:7-35`、class `:95-107`、角标区 `:108-113`、皮肤图渲染 `:115-125`）
- code/frontend/src/components/table/ResultModal.vue（props `:9-20`、`winnerHand` `:69-78`、渲染 `:142-163`、脚注 `:164`、庄徽标 `:129-135`）
- code/frontend/src/views/HistoryView.vue（`:322-350`）、code/frontend/src/mobile/views/MobileHistoryView.vue（`:315-332`）

## 任务
1. **后端**：`engine.py::final_hands_snapshot()` 增 `winning_tile_index`（`int | None`）—— 胡张在**排序后** `concealed` 中的下标；同值多张取**最后一次出现**；点炮/抢杠的胡张必须在 `tiles.sort()` **之后**再计算索引；非赢家为 `null`。
2. **协议**：04 §9.5 已写好结构（**只增字段、不改既有字段名与语义**）；`mj_game_round.finalHandsJson` 是 JSON 列，**无需 DDL**；旧局缺该字段时前端回退为「`concealed` 中最后一张同值牌」，与后端口径一致。
3. **类型**：`code/frontend/src/types.ts` 的 `FinalHand` 增 `winning_tile_index?: number | null`（可选，旧局缺省不影响解析）。
4. **视觉**：`Tile.vue` 增 `winTile?: boolean` prop —— 牌身 `ring-2 ring-gold-400`；**右上角**金色「胡」角标（`h-3.5 w-3.5 rounded-full bg-gold-400 text-[9px] font-bold leading-none text-felt-950 ring-1 ring-cream-50/70 absolute -top-[4px] -right-[4px] pointer-events-none`）。副露红点 `mark` 在**左上**，两者不重叠。角标必须存在（皮肤图模式 `<img class="object-contain">` 会留白，1px 描边会被吃掉）。
5. **尺寸档位**：`sm`（结算页）14px；`xs`（战绩详情）缩为 `h-2.5 w-2.5 text-[7px]`；`micro`（手机战绩）缩为 12px。桌面与手机共用 `components/table/Tile.vue`，按 `size` 自动切换。
6. **结算页**：`ResultModal.vue` 新增 `winTileIndex` computed —— 优先取 `final_hand.winning_tile_index`，缺失时回退「`concealed` 中最后一张与 `winning_tile` 同值的牌」；暗牌循环改传 `:win-tile="index === winTileIndex"`；脚注由「金框为胡张」改为「**带「胡」角标的是胡张**」。
7. **战绩页**：`HistoryView.vue` 与 `MobileHistoryView.vue` 同步补标记（建议抽一个共用 helper，例如 `frontend/src/utils/finalHand.ts` 的 `winTileIndexOf(finalHand)`，供结算页与战绩页复用，保证口径唯一）。
8. **不需要改动**：`RoomView.vue`（`:769-778`）与 `MobileRoomView.vue`（`:618-627`）的挂载与 props 已含 `result`。
9. 文档回写：04 §9.5 / §12-18、05 §4.5 / §验收-25 补实际实现细节、06 §8C 勾选、改进台账 V-1 补实现细节。

## 验收清单
- [ ] 后端：点炮 / 自摸 / 抢杠三种情形下 `final_hands[].winning_tile_index` 均指向排序后的正确那张牌；非赢家为 `null`。
- [ ] 结算页胡牌手牌区**只有一张**牌带金色「胡」角标，且正是胡牌的那张；副露里的胡张也被标记；与副露红点不重叠。
- [ ] 同值多张时只标一张；旧局（无 `winning_tile_index`）回放时标记仍指向正确的同值牌，不指错。
- [ ] 桌面 1280×800、手机 375×667 与横屏 667×375、战绩详情（`xs`）、手机战绩（`micro`）四处角标均清晰可见；皮肤图模式下不被图片吞掉。
- [ ] 结算面板脚注文案已改为「带「胡」角标的是胡张」；标题行的胡张名保留。
- [ ] `pytest -q` 全绿（含 `final_hands_snapshot` 的断言）；`npm run typecheck` 与 `npm run build` 通过。
- [ ] `git diff` 确认**除新增可选字段外无协议变更、无 DDL**。

## 硬约束
- **只增字段**：`winning_tile_index` 是新增可选字段，不改既有字段名与语义；不加数据库列。
- **前后端口径必须一致**：均为「排序后最后一张同值牌」；否则旧局战绩会指错牌。
- `mark` 与 `highlight` 都用 `ring-1` + 不同 `ring-color`（Tailwind 同一 `--tw-ring-color` 变量会互相覆盖），因此 `winTile` 必须用 `ring-2` + 独立角标，**不得与 `mark`/`highlight` 共用 ring 颜色**。
- 不改 `FinalHand` 的既有字段，不改结算面板整体布局（375px 宽不能因角标换行）。
- 桌面与手机不得只改一处。

## 完成后必须输出
1. 改动文件清单 + `winning_tile_index` 的三种情形取值示例。
2. 角标的四档尺寸对照表（sm / xs / micro / 环视）。
3. `pytest -q`、`npm run typecheck`、`npm run build` 结果与手测截图说明。
````

---

## I13 · 牌桌「庄」徽标跟随庄家轮转（U-5）

> **什么时候做**：**文档已批准后**立即做。纯前端、协议零改动、无 DDL。
> 与 I14 无文件冲突（`src/components/table/*` + `src/views/*` vs `src/audio/*`），**可并行**。

````text
【家庭麻将 · v1.1.2 · I13 · 牌桌「庄」徽标跟随庄家轮转（U-5）】

## 目标
牌桌上的金色「庄」徽标必须**跟随庄家轮转**：庄家换下一家后徽标立刻移动到新庄家身上，旧庄家不再显示；桌面（左 / 右 / 对家 / 自己）与手机（左 / 右 / 对家 / 自己）**四席全部正确**。

## 前置
- 文档已批准：[05-UI设计.md](05-UI设计.md) 已补「牌桌·庄家标记（v1.1.2 修复）」规格行、「牌桌「庄」徽标规格（v1.1.2 修复）」表与验收第 26 条；[改进和错误修复文档.md](改进和错误修复文档.md) §3 U-5 已定稿。
- **后端与协议已就绪，本步不改后端**：`realtime/snapshot.py:78` 已按座位下发 `seats[].is_dealer`，`:102` 已下发 `dealer_seat`；`frontend/src/types.ts:241` 已声明 `SeatView.is_dealer?: boolean`，`:339` 已有 `snapshot.dealer_seat`。
- 口径已由用户确认，无需再问：四席全修（桌面左 / 右 / 对家 / 自己 + 手机四席）。

## 必须先读
- plan/改进和错误修复文档.md §3 U-5（现象 / 复现与证据 / 根因 / 修复方案 4 步 / 验收 6 条 / 风险 4 条）
- plan/05-UI设计.md（牌桌规格表「牌桌·庄家标记（v1.1.2 修复）」+「牌桌「庄」徽标规格（v1.1.2 修复）」表 + 验收清单第 26 条）
- code/backend/src/realtime/snapshot.py（`:78` `is_dealer`、`:102` `dealer_seat`）
- code/frontend/src/types.ts（`SeatView.is_dealer?: boolean` `:241`、`snapshot.dealer_seat` `:339`、`RoundResult` `:281-300`）
- code/frontend/src/components/table/PlayerSeat.vue（props `:8-17`、徽标 `:49-55`）
- code/frontend/src/mobile/components/table/MobileSeatChip.vue（props `:14-23`、两处徽标 `:56-62` / `:112-118`）
- code/frontend/src/views/RoomView.vue（`:64-66` `seatAt()`、`:350-364` 对家、`:370-376` 左、`:481-487` 右、`:497-504` 自己内联头像块、`:274` `bottomView`）
- code/frontend/src/mobile/views/MobileRoomView.vue（`:343-350` 左、`:358-364` 对家、`:439-446` 右、`:455-461` 自己内联头像块、`:277` `bottomView`）
- code/frontend/src/stores/game.ts（`:62-66` `seats` / `mySeatView`；`snapshot.seats[seat]` 就是完整 `SeatView`，自带 `is_dealer`）

## 任务
1. **判定下沉到座位组件**（核心，两个组件各加一个 computed）：
   - `PlayerSeat.vue`：新增 `const isDealerSeat = computed(() => props.isDealer || props.seat.is_dealer === true)`，把 `:50` 的 `v-if="isDealer"` 改成 `v-if="isDealerSeat"`。
   - `MobileSeatChip.vue`：同样新增 computed，把 `:57`（`layout='bar'` 对家）与 `:113`（`layout='side'` 上/下家）**两处** `v-if="isDealer"` 都改成 `v-if="isDealerSeat"`。
   - **保留 `isDealer` prop**（默认 false）不删不改名：组件内 `||` 让「prop」与「快照字段」两套数据源都生效，既有调用方（结算页等）零影响。
2. **桌面「自己」席位补徽标**（`RoomView.vue:497-504`）：此处是**内联实现**的头像 `<span>`，原本**没有徽标**。把头像 `<span>` 包进 `<div class="relative shrink-0">`，并在其后追加与 `PlayerSeat.vue` 完全一致的徽标：
   ```html
   <span
     v-if="bottomView?.is_dealer"
     class="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-gold-400 text-[9px] font-bold text-felt-950"
     title="庄家"
   >庄</span>
   ```
   （桌面尺寸 `h-4 w-4 text-[9px]`；`bottomView` 是 `mySeatView` 或观战目标，二者都是 `SeatView`，天然带 `is_dealer`。）
3. **手机「自己」席位补徽标**（`MobileRoomView.vue:455-461`）：同样包一层 `<div class="relative shrink-0">`，徽标用手机尺寸：
   ```html
   <span
     v-if="bottomView?.is_dealer"
     class="absolute -right-1 -top-1 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-gold-400 text-[8px] font-bold text-felt-950"
     title="庄家"
   >庄</span>
   ```
4. **桌面左 / 右席位**：它们**本来就没传** `:is-dealer`（`RoomView.vue:370-376`、`:481-487`），组件内的 `|| seat.is_dealer` 已让它们正确显示。可顺手补传 `:is-dealer="game.snapshot?.dealer_seat === relative.left"` / `=== relative.right"`（冗余但更直观）—— **二选一即可，不要求两处都改**。
5. **不要动**：`isTurn`（金色边框 + 呼吸光晕）逻辑、`ResultModal.vue` 的结算页庄标、`SeatBox.vue`、任何后端与协议字段。
6. **可选加固（本步不做）**：结算页 `RoundResult`（`types.ts:281-300`）目前没有 `dealer_seat` 字段；若要彻底统一「谁是庄家」的口径，可在 `types.ts` 增可选 `dealer_seat?: number | null` 并在结算页使用 —— **本步不做**，避免扩大改动面。
7. **构建验证**：`npm run typecheck`、`npm run build`（base `/majiangapp/`）、`npm run build:mobile`（base `/mjmobile/`）各跑一次；桌面与手机**两处都必须改**。
8. **文档回写**：05 的「庄」徽标规格表补「实际实现」说明并勾选验收第 26 条；改进台账 U-5 补「实施细节 + 验收结果」；improve step-prompts 状态表把 I13 标为已实施。

## 验收清单（2026-10-31 I13 已实施，逐条已核）
- [x] **桌面四席**：左 / 右 / 对家 / 自己，同一时刻**只有一个**「庄」徽标，且落在当前庄家身上。→ 自动化断言：庄家依次落 0/1/2/3 席，每轮徽标数恒为 1 且所在席位 = 庄家（`plan/I13-evidence/desktop-dealer-seat0..3.png`）。
- [x] **手机四席**：同上（竖屏 375×667 与横屏 667×375 都要看）。→ 竖屏 / 横屏各 4 轮全绿（`手机竖屏-*.png`、`手机横屏-*.png`）；注：手机竖屏按既有设计显示「把手机横过来打牌」引导层（牌桌仍在下层渲染，徽标 DOM 已渲染并通过断言），肉眼查看以横屏为准。
- [x] **换庄后徽标跟随**：庄家胡牌连庄 → 徽标**不动**；庄家下庄 → 徽标**移动到下一家**，旧庄家**不再显示**。→ 断言「换庄后徽标坐标移动 + 所在席位 = 新庄家」「连庄后坐标不变」。
- [x] **荒庄**：仍显示「庄」徽标（当前庄不变）。→ 荒庄由后端 `next_dealer` 决定下一局庄位，本局 `dealer_seat` 不变 → 徽标随快照自然停留原庄家（快照驱动，无需额外分支）。
- [x] **未开局（waiting）**：徽标显示正确（快照已有 `dealer_seat` / `is_dealer`）。→ waiting 时后端 `engine is None` → `dealer_seat=null`、`is_dealer=false` → 四席**均无**徽标（正确口径：第一局开局后才产生庄家），断言徽标数 = 0。
- [x] **观战视角**：`bottomView` 为观战目标时，底部「自己」区域的徽标反映的是**被观战者**是否庄家；别家徽标正常。→ 观战（`self_seat=null`，跟随座位 2）：庄家=2 时徽标落在被观战者（底部）1 个；庄家=0 时徽标落在别家 1 个（`desktop-spectate-dealer*.png`）。
- [x] **金色边框不受影响**：「轮到你」的边框 + 呼吸光晕仍只在当前出牌者身上，与「庄」徽标**互不覆盖**（两者是独立元素、不同数据源）。→ `turn` 与 `dealer` 取不同座位时，`animate-breathe` 只在 `turn` 席位、徽标只在 `dealer` 席位；「自己」席位为内联块、本就不带边框高亮（出牌提示走底部 ActionBar，既有实现）。
- [x] **尺寸与位置**：桌面徽标 `h-4 w-4 text-[9px]`、手机 `h-3.5 w-3.5 text-[8px]`，均 `absolute -right-1 -top-1`；不遮挡昵称、分数与「已准备」标记。→ 断言徽标 16×16（桌面）/ 14×14（手机）、文案「庄」、位置 `absolute -right-1 -top-1`（头像右上角），未压昵称与分数。
- [x] `npm run typecheck` 0 error；`npm run build` 与 `npm run build:mobile` 均通过。
- [x] `git diff` 确认**只动前端 4 个文件**（`PlayerSeat.vue`、`MobileSeatChip.vue`、`RoomView.vue`、`MobileRoomView.vue`）：**无 WS 事件 / 字段变更、无 DDL、无 `code/backend/**` 改动**。（工作区另有并行会话 I14 的 `src/audio/*` 改动，非本步内容。）

## 硬约束
- **不改后端**：`snapshot.py` 已下发 `is_dealer`，本步**不得修改** `code/backend/**`。
- **不改协议**：不新增 / 修改任何 WS 事件或字段；不新增数据库列。
- **不删 `isDealer` prop**：`||` 兜底，既有调用方必须零影响。
- **不混淆两个视觉元素**：「庄」徽标（数据源 `dealer_seat`）与金色边框（数据源 `turn`）语义不同，不得互相替代。
- 桌面与手机**不得只改一处**；四席**不得只改一席**。
- 不顺手改其它 UI（字号、皮肤、动画），不夹带 I14 的音效改动。

## 完成后必须输出
1. 改动文件清单（4 个文件，逐处说明改了什么）。
2. 徽标判定链路说明（`snapshot.seats[].is_dealer` → 组件 computed → `v-if`），并说明为什么父组件不必再传 `is-dealer`。
3. 验收清单逐条结论（含桌面 / 手机换庄前后的截图或录屏说明）。
4. `npm run typecheck` / `npm run build` / `npm run build:mobile` 结果。
5. 遗留问题（不超过 5 条，必须明确是否阻塞 I14 或发版）。
````

---

## I14 · 吃 / 碰 / 胡 / 杠 改用叫牌人声（S-2）

> **什么时候做**：**文档已批准后**立即做。纯前端、协议零改动、无 DDL。
> 与 I13 无文件冲突，**可并行**。
> 口径已由用户确认，无需再问：**6 个叫牌音全部换成女声**；**新增独立人声键**，旧合成音**文件保留但不再触发**。

````text
【家庭麻将 · v1.1.2 · I14 · 吃 / 碰 / 胡 / 杠 改用叫牌人声（S-2）】

## 目标
把「吃 / 碰 / 胡 / 明杠 / 暗杠 / 补杠」六种叫牌提示音，从 `public/audio/sfx/` 的**自制合成音**换成 `public/audio/voice/` 的**女声人声**；旧合成音**文件保留在磁盘上但不再触发**；与 34 个牌面报牌人声**互不干扰**；协议零改动。

## 前置
- 文档已批准：[08-音效设计.md](08-音效设计.md) 已升 v1.2 —— §2 触发映射表换成 6 个 `*_voice` 键、新增 §2.2「叫牌人声」、§3 优先级表键名同步、§4.1 目录树（`voice/` 40 个 mp3）、§4.2 新增「枚举键 + `SoundSpec.dir` 字段」选型、§4.5、§6.2（人声资源 40 个）、§6.3（取用登记）、§8 验收第 20–24 条；[改进和错误修复文档.md](改进和错误修复文档.md) §3A-2 S-2 已定稿。
- 素材在 `plan/majiang_sound/women_mp3/`：`hu.mp3`（≈2.5s）、`pong.mp3`、`chow.mp3`、`kong_exposed.mp3`、`kong_hidden.mp3`、`kong_added.mp3`。

## 必须先读
- plan/08-音效设计.md §2（触发映射表）、§2.2（叫牌人声）、§3（优先级与限流）、§4.1（目录树）、§4.2（选型：枚举键 + `dir` 字段）、§4.5、§6.2（人声资源规格）、§6.3（授权风险登记）、§8（第 20–24 条）
- plan/改进和错误修复文档.md §3A-2 S-2
- code/frontend/src/audio/soundKeys.ts（`SoundKey` `:9-24`、`SoundSpec` `:29-38`、`SOUND_SPECS` `:40-56`、`SOUND_KEYS` `:58`、`SOUND_URLS` `:61-64`、`sfxUrl()` `:70-72`、`priorityOf()` `:75-77`）
- code/frontend/src/audio/useGameSounds.ts（`play()` `:15-17`、`event.settled` `:41-54`、`event.kongged` `:55-61`、`event.claimed` `:69-72`）
- code/frontend/src/audio/audioManager.ts（`playSound()` `:513-547`、`sfxUrl` 调用点 `:528`、`loadOne()` `:244`、`preloadSounds()` `:320-326`、`preloadVoices()` `:345`、`previewSound()` `:670`、`audioState.total` `:51`）
- code/frontend/src/audio/voiceMap.ts（34 项牌面映射 + `voiceBaseFromTarget()` 白名单）
- code/frontend/public/audio/voice/LICENSE.md（授权留痕，本步要改写「取用」段）
- code/frontend/public/audio/sfx/LICENSE.md（旧合成音来源登记，**不改**）
- code/deploy/nginx-majiang.conf（`*/audio/voice/` 30 天强缓存规则 —— **已存在，本步无需改**）

## 任务
1. **资源**：`code/frontend/public/audio/voice/` 从 34 个 mp3 扩到 **40 个**，从 `plan/majiang_sound/women_mp3/` 复制 6 个：`hu.mp3`、`pong.mp3`、`chow.mp3`、`kong_exposed.mp3`、`kong_hidden.mp3`、`kong_added.mp3`。**不要删除 / 覆盖 / 修改 `public/audio/sfx/` 里的同名文件**（旧合成音保留在磁盘，只是不再触发）。
2. **`soundKeys.ts` 改造（核心）**：
   - `SoundKey`：删掉 6 个旧键 `hu` / `pong` / `chow` / `kong_exposed` / `kong_hidden` / `kong_added`，加上 6 个新键 `hu_voice` / `pong_voice` / `chow_voice` / `kong_exposed_voice` / `kong_hidden_voice` / `kong_added_voice`。其余 9 键（`exhausted` / `claim` / `turn` / `discard` / `draw` / `timeout` / `dice` / `deal` / `chat`）不变 —— **总数仍为 15**。
   - `SoundSpec` 增可选字段 `dir?: 'sfx' | 'voice'`（缺省视为 `'sfx'`），并补一行注释说明「同名文件在 `sfx/` 与 `voice/` 各一份，靠 `dir` 区分」。
   - `SOUND_SPECS`：6 个新键的 `file` 分别为 `hu.mp3` / `pong.mp3` / `chow.mp3` / `kong_exposed.mp3` / `kong_hidden.mp3` / `kong_added.mp3`，并写 `dir: 'voice'`；**音量与优先级沿用旧值**（`hu` 90 / P0；`kong_*` 75 / P1；`pong` 70 / P2；`chow` 65 / P2）；其余键的 `file` / `volume` / `priority` **一律不动**。
   - `sfxUrl()` 改按 `dir` 拼目录：`${import.meta.env.BASE_URL}audio/${SOUND_SPECS[key].dir ?? 'sfx'}/${SOUND_SPECS[key].file}`。
   - `SOUND_KEYS` / `SOUND_URLS` / `priorityOf()` 全部由 `SOUND_SPECS` 派生，**不需要手改**；改完必须满足 `SOUND_KEYS.length === 15`。
3. **`audioManager.ts` 零改动**：`playSound()` 通过 `sfxUrl(key)` 取 URL，新键自然指向 `voice/`；并发上限、优先级、淡出、`unavailable` 降级、`preloadSounds()`（仍 15 个请求）全部沿用。**不要**为叫牌人声新增 `playVoice()` 分支，也**不要**把 6 个叫牌音加进 `voiceMap.ts` 的 34 项白名单（`preloadVoices()` 只预热 34 个牌面音）。
4. **`useGameSounds.ts` 接线**：把 6 处 `play(...)` 换成新键 —— `event.settled` 的 `play('hu')` → `play('hu_voice')`；`event.kongged` 的 3 处 → `kong_exposed_voice` / `kong_hidden_voice` / `kong_added_voice`；`event.claimed` 的 `play('pong')` / `play('chow')` → `pong_voice` / `chow_voice`。
   - **荒庄分支不变**：`data.is_draw` 时只播 `exhausted` 并**直接 return**，绝不播 `hu_voice`。
   - `event.settled` 的「一局只播一次」去重（`settledRoundKey`）保持不变，多赢家不叠加。
5. **全局排查旧键引用**：`grep -rn "'hu'\|'pong'\|'chow'\|'kong_exposed'\|'kong_hidden'\|'kong_added'" code/frontend/src`。当前前端 UI **不直接引用** `SoundKey`（音效设置面板未做逐键试听），因此预计只有 `useGameSounds.ts` 需要改；但**必须实际 grep 确认**，有残留就一并改掉，`npm run typecheck` 必须 0 error。
6. **`voice/LICENSE.md` 改写**：把「本项目取用」从「仅 34 个牌面音」改为「**40 个全部取用**（34 牌面 + 6 叫牌：`hu` / `pong` / `chow` / `kong_exposed` / `kong_hidden` / `kong_added`）」；删掉「**未取用**」那一行；更新「目录内文件清单：40 个 mp3 + 本 LICENSE.md」与体积 / 时长实测。**授权风险登记段必须原样保留**（源仓库未提供 LICENSE、权利归属不明、用户已于 2026-10-31 接受该风险、两处留痕）。
7. **08 同步**：§2 触发映射表核对新键；§4.5 / §6.2 补实际实现细节与实测体积；§6.3「实际落地」表把「未取用」改为「已取用，走枚举键通道（`dir: 'voice'`）」；§8 第 20–24 条勾选。
8. **构建验证**：`npm run typecheck`、`npm run build`、`npm run build:mobile` 各一次；确认 `dist/audio/voice/` 与 `dist-mobile/audio/voice/` 各 **40 个 mp3**；确认 `dist/audio/sfx/` 里 6 个旧合成音**仍在**（保留但不触发）；确认运行时 URL 为 `/majiangapp/audio/voice/hu.mp3` 与 `/mjmobile/audio/voice/hu.mp3`（与 nginx 两条 `location` 前缀一致）。
9. **文档回写**：改进台账 S-2 补「实施细节 + 验收结果」；06 §8D 勾选；improve step-prompts 状态表把 I14 标为已实施。

## 验收清单
- [ ] **吃 / 碰 / 胡 / 明杠 / 暗杠 / 补杠** 六种情形各播一次**女声**；旧合成音**不再响**（`sfx/` 的 6 个文件仍在磁盘上）。
- [ ] **互斥不叠加**：同一个事件不同时播旧音与人声（只可能听到人声）。
- [ ] **荒庄只播 `exhausted`**、不播 `hu_voice`；一局结算只播一次 `hu_voice`（多赢家不叠加）。
- [ ] **与牌面报牌互不干扰**：出牌报牌（`playVoice()` 动态通道）与叫牌人声（`playSound()` 枚举通道）同时发生时各自可辨。
- [ ] **优先级不变**：`hu_voice` 仍为 P0；`kong_*_voice` 为 P1；`pong_voice` / `chow_voice` 为 P2；`hu` 在播时 200ms 内的低优先级音仍被抑制。
- [ ] **总开关与音量**：关闭音效总开关 → 15 个 SFX **全部**静音；音量滑块对 6 个叫牌人声同样生效；不新增用户偏好字段、不加 DDL。
- [ ] **降级**：删除 `voice/` 中任意一个叫牌 mp3 → 该叫牌静音、其余 39 个正常、控制台**无 `error`**、对局可打完；删除整个 `voice/` 目录 → 15 个 SFX 仍全部正常。
- [ ] **预加载与体量**：Network 面板预加载仍为 **15 个 SFX 请求**（其中 6 个指向 `voice/`）；`voice/` 目录 **40 个 mp3、合计 ≤400 KB**（预估 ≈370 KB）。
- [ ] `npm run typecheck` 0 error；`npm run build` 与 `npm run build:mobile` 均通过；产物中 `audio/voice/` 40 个、`audio/sfx/` 15 个。
- [ ] `git diff` 确认**协议零改动**（无 WS 事件 / 字段变更）、**无 DDL**、**无 `code/backend/**` 改动**。
- [ ] 授权留痕：`public/audio/voice/LICENSE.md` 与 08 §6.3 **双处**均写明「6 个叫牌音已取用」，且风险登记段未删。

## 硬约束
- **不改协议**：不新增 WS 事件或字段，只消费既有 `event.claimed.action` / `event.kongged.kind` / `event.settled.winners`。
- **不删旧合成音文件**：`public/audio/sfx/` 的 6 个文件**保留**（只是不再触发），便于回滚。
- **不扩 `SOUND_KEYS` 数量**：必须仍是 15 项，预加载请求数不得增加。
- **不把叫牌音加进 `voiceMap.ts`**：那 34 项白名单只服务牌面报牌的动态通道。
- **不裁剪素材**：`hu.mp3` ≈2.5s，08 §6.2 已单列「叫牌人声 ≤2.6s」，**不裁剪、不变速**。
- **不改 `audioManager.ts`**：若发现非改不可，先说明原因再改，并确保并发 / 优先级 / 淡出 / 降级语义不变。
- 不顺手改 UI（字号、皮肤、动画），不夹带 I13 的庄徽标改动。
- 版权风险已由用户接受，但**必须在 `voice/LICENSE.md` 与 08 §6.3 双处留痕**，不得省略。

## 完成后必须输出
1. 改动文件清单 + `SoundKey` 改造前后对照表（旧 6 键 → 新 6 键，含 `file` / `dir` / 音量 / 优先级）。
2. `SOUND_KEYS.length`、`voice/` 文件数与体积实测、`dist` 与 `dist-mobile` 产物文件数。
3. 验收清单逐条结论（含删文件降级测试与 Network 面板请求数）。
4. 授权留痕位置（`voice/LICENSE.md` 与 08 §6.3）。
5. 遗留问题（不超过 5 条，必须明确是否阻塞发版）。
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
| I9 | 文档批准 | 番表 35 项（一只幺）+ 用例 35 | 是（与 I10 同版） |
| I10 | I9 | 13不靠 判番调整 + 用例 36 | 是（与 I9 同版） |
| I11 | 文档批准 | 34 个牌面人声音效 + voiceMap + playVoice | 是（协议零改动） |
| I12 | 文档批准 | `winning_tile_index` + 「胡」角标 | 是（只增可选字段） |
| I13 | 文档批准 | 庄徽标判定下沉到座位组件 + 两端自己席位补徽标 | 是（纯前端、协议零改动） |
| I14 | 文档批准 | 6 个叫牌人声（枚举键 + `SoundSpec.dir`）+ `useGameSounds` 接线 | 是（纯前端、协议零改动） |

> I9–I12 与 I7 的关系见「当前状态」下的说明：四步同属 `1.1.0`，建议在 I7 之前完成并同版发布。
> I13 / I14 属 **v1.1.2 第三轮**：两项均为纯前端、协议零改动、无 DDL，**互不冲突可并行**，可同批发版。

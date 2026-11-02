---
name: majiang-v1.1.4-admin-end-and-chow
overview: v1.1.4 两项改动：①把「结束整场并收桌」的权限从房主扩展到房主 + 房间所属家庭 OWNER/ADMIN（WS 与大厅同一判定口径，牌桌上按能力位控制按钮）；②针对「桌面 + 柏氏下 2 张 1 万 + 2、3 万遇 1 万却只有碰没有吃」做取证与修复——现有代码已能下发吃（已用 generic/baishi 双配置复现通过），故先补结构化日志与回归用例锁定，再按证据修 UI/规则提示或后端漏发。同步更新 plan 下台账与各文档到 v1.1.4。
todos:
  - id: backend-end-permission
    content: 用 [subagent:code-explorer] 清点权限调用面；实现 isFamilyAdmin、角色缓存与 can_end_room，放行管理员并补快照 viewer
    status: completed
  - id: frontend-end-permission
    content: 前端 canEndGame 改服务端能力位，桌面/手机与确认弹层文案同步，保留 REST 兜底
    status: completed
    dependencies:
      - backend-end-permission
  - id: chow-diagnostics
    content: 开窗取证日志 + 快照 legal.chow_hint + ActionBar 不可吃提示（桌面与手机）
    status: completed
  - id: chow-regression-tests
    content: 补柏氏重复张吃碰并存、非下家提示、WS 副露断言与 isFamilyAdmin 单测
    status: completed
    dependencies:
      - chow-diagnostics
  - id: sync-proto-ui-docs
    content: 同步 04 协议（viewer/chow_hint/权限文案）、05 UI（收桌入口与提示）、07 吃仅限下家
    status: completed
    dependencies:
      - backend-end-permission
      - chow-diagnostics
  - id: sync-plan-docs
    content: 同步改进文档 U-6/B-2、improve I15/I16、06 §8E P12、00、README 与 docs 摘要
    status: completed
    dependencies:
      - backend-end-permission
      - chow-diagnostics
  - id: regression-and-release
    content: 用 [skill:playwright-cli] 冒烟；pytest/typecheck/build 全绿后发 v1.1.4 并回写验收
    status: completed
    dependencies:
      - frontend-end-permission
      - chow-regression-tests
      - sync-plan-docs
---

## 用户需求

### 一、结束牌局的权限（U-6）

- 现状：牌桌上「结束牌局」只有房主能点，家庭管理员在大厅能关桌、在牌桌上却没有入口。
- 目标：**房主 + 房间所属家庭的 OWNER/ADMIN** 都能结束；语义为**结束整场并收桌**（场次作废/结算、`mj_room.roomStatus='CLOSED'`、大厅立即消失、全员回大厅），与现有房主行为完全一致。
- 权限范围：仅房间所属家庭的 OWNER/ADMIN；不含系统管理员；不要求必须入座（管理员观战也可结束）。

### 二、吃牌入口缺失（B-2）

- 现象：桌面端 + 柏氏，手牌 `1 万 1 万 2 万 3 万`，上家打出 `1 万`，动作条只有「碰/杠/胡/过」，没有「吃」。
- 期望：同时出现「碰」和「吃」，吃可以是 `1 万 + 2 万 + 3 万`。
- 已核实：现有代码与该手牌下**后端会同时下发碰与吃**（generic 与 baishi 双配置均复现通过，生产 1.1.3 后端亦为三态实现），因此需要先补齐取证链路再按证据修，避免盲改；同时把「为什么不能吃」直接显示给玩家（只有下家能吃 / 两张牌凑不成顺子），消除误判。

### 三、交付形态

- 版本 v1.1.4；桌面与手机两端同步；协议只增可选字段；无 DDL；不改番表语义与结算口径。
- 同步更新 `plan/` 台账与各层文档，保持版本、字段、错误码一致。

## 产品概述

家庭麻将 Web 应用（FastAPI + Vue3，桌面 `src/` 与手机横屏 `src/mobile/`）。本次是权限口径统一 + 交互可解释性修复：让「谁能收桌」在 WS 与 HTTP 两条链路上只有一个判定，并让「为什么这张牌不能吃」在牌桌上可见。

## 核心功能

- 管理员在牌桌内看到并可执行「结束牌局」，与房主同效（二次确认、系统播报、关房幂等、失败可重试）。
- 动作条按钮可用性由服务端能力位驱动，前端不再用 `is_host` 自行推导。
- 可吃时同时给「碰」与「吃」；不可吃时给出明确原因提示。
- 新增柏氏 + 被吃牌在手中有重复张的自动化用例，锁死该场景。

## 技术栈与基线

- 后端：FastAPI + Uvicorn（同步路由 + 原生 WS），`common/mysqlCommon.py` 为唯一 SQL 出口，`run_in_threadpool`（`realtime/room.py:449 _persist`）承接同步落库。
- 前端：Vue 3 + TS + Vite 5 + Pinia + Tailwind 3；桌面 `code/frontend/src/`、手机 `code/frontend/src/mobile/`，共用 `components/table/*`。
- 版本锚点：`config/basicSettings.py VERSION`、`code/frontend/package.json version`、`plan/*` 文档状态行，本次统一 `1.1.4`。
- 无表结构变更；`mj_room.ruleSnapshot` 不动。

## 根因归纳

| 编号 | 问题 | 根因（已核实） |
| --- | --- | --- |
| U-6 | 管理员不能结束牌局 | 权限判定有**两套口径**：HTTP 侧 `roomService.closeRoom`（roomService.py:356-374）已支持 `OWNER/ADMIN`，WS 侧 `_end_game`（room.py:1037-1074）只认 `host_login_id`，且先要求有座位（`NO_SEAT`）；快照里也没有「本连接能否收桌」的能力位，前端只能用 `isHost` 猜（RoomView.vue:46/211、MobileRoomView.vue:231） |
| B-2 | 柏氏 + `1万1万2万3万` 遇 `1万` 无「吃」 | 代码层无法复现（`chow_options` 三态枚举正确、`engine.py:718` 仅下家吃、`ActionBar.vue:186-197` 渲染无嵌套条件、`stores/game.ts:105 legal` 不过滤）。因此只剩三种可能：**本家不是下家**、**手牌实际不含 2/3 万**、**前端产物/快照陈旧**。当前缺的是可取证日志与「不可吃」的可解释提示 |


## U-6 实现方案

### 1. 单一权限口径

- 在 `processor/familyService.py` 新增纯领域函数：

```python
def isFamilyAdmin(familyID: int, loginID: str) -> bool:
"""该登录号是否为该家庭 ACTIVE 的 OWNER/ADMIN（读 mj_family_member）。"""
```

复用现有 `query_mj_family_member` + `STATUS_ACTIVE` + `ROLE_OWNER/ROLE_ADMIN` 常量（familyService.py:33-43, 183）。

- `roomService.closeRoom` 改为调用它（行为不变，去掉内联判定）；**不**从 `realtime` 反向 import `processor`（roomService 不依赖 realtime，保持分层；权限函数放在 familyService 这一层，realtime 只在启动/握手期调用一次）。

### 2. 牌桌侧判定与缓存

- `RoomActor.__init__`（room.py:117-140）新增 `self._roles: dict[str, tuple[str, str]]`（`loginID -> (memberRole, displayName)`）与 `self._roleAt: dict[str, float]`。
- 新增 `def role_of(self, login_id) -> str`（同步读缓存；未命中返回 `""`），以及 `async def refresh_role(self, login_id, display_name="")`：命中未过期（60s）直接返回，否则 `run_in_threadpool(familyService.isFamilyAdmin, self.family_id, login_id)`，把 `"ADMIN"/"OWNER"` 或 `""` 写入缓存。
- `main/ws.py` 握手处（已解析 `roomMetaByCode`、拿到 `family_id`）在 `attach` 前调用一次 `await actor.refresh_role(...)`；`state.resync` 与 `attach` 时按 TTL 刷新，避免每次快照都查库。
- 新增 `def can_end_room(self, login_id) -> bool`：`login_id == host_login_id` 或 `role_of(login_id) in {"OWNER","ADMIN"}`（沿用 familyService 常量）。
- `_end_game` 重排判定顺序：

1. `self.can_end_room(login_id)` 为假 → `FORBIDDEN "只有房主或家庭管理员可以结束牌局"`；
2. `finalized / finished / closed` → 走现有幂等 `_close_room` 分支（保留 `CLOSE_FAILED`）；
3. 无座位但为管理员 → 允许，播报用 `role_of` 缓存的昵称或「管理员」；
4. `playing` → 现有 `_abort_game → _close_room` 路径不变。

- 播报统一：`"{昵称}（管理员）结束了本场牌局"` / `"{昵称} 结束了本场牌局"`。

### 3. 快照能力位

- `realtime/snapshot.py::build_snapshot(actor, viewer_seat, viewer_login_id)` 增：

```python
"viewer": {
"is_host": viewer_login_id == actor.host_login_id,
"member_role": actor.role_of(viewer_login_id),   # "" | OWNER | ADMIN
"can_end_game": actor.can_end_room(viewer_login_id),
},
```

仅为**新增可选字段**；`room.welcome` 复用 `_room_view` 不改。

- 前端 `types.ts Snapshot` 增 `viewer?: {is_host, member_role, can_end_game}`；`stores/game.ts` 增 `viewer` / `canEndGame` 计算属性（缺字段时回退 `isHost`，兼容旧快照）。

### 4. 前端

- `views/RoomView.vue`、`mobile/views/MobileRoomView.vue`：`canEndGame` 改读 `game.canEndGame && phase !== 'waiting'`（不再 `isHost`）；二次确认文案由「只有房主」改为「房主或家庭管理员」；`endGameLabel` 不对管理员显示「房主收桌」字样。
- `components/table/ScoreBoard.vue`、`mobile/components/table/MobileScoreBoard.vue`：沿用既有 `canEndGame` prop，无需改判定；只校文案。
- 3s REST 兜底 `endGame()` 已走 `POST /api/rooms/{id}/close`（该接口支持管理员），保持不动。

## B-2 实现方案（取证优先 + 可解释提示）

### 1. 服务端取证日志

- `engine._build_claim_window`（engine.py:695-742）末尾补一条结构化 INFO：
`开窗 room/from/tile/allow_chow/next_seat/{seat: [action...]}`，并对「本可吃却未给」显式标注原因：
- `reason=not_next_seat`（`seat != (from_seat+1)%4`）；
- `reason=no_partner`（`chow_options` 为空）；
- 命中则记 `chow_skipped`。日志只打动作名与张数，不打手牌明细，避免牌面泄露到日志。

### 2. 可解释提示（服务端下发，前端只展示）

- 快照 `legal` 增可选 `chow_hint: string`：当本座位**不可吃**且存在碰/杠时给出原因文本（`"只有下家能吃"` / `"这两张牌凑不成顺子"`），可吃时为空。
- `ActionBar.vue` 在动作条来牌区下方渲染 `chowHint`（`text-[13px] text-ink-300/80`，桌面/手机同款，375×667 不折行）；`stores/game.ts` 透传。

### 3. 用例锁死

- `tests/test_engine_flow.py` 增：柏氏 + `1万×2 + 2万 + 3万` + 上家打 `1万` → `legal_actions` 必须同时含 `pong` 与 `chow(tiles=[1,2])`；非下家 → 只有 `pong` 且 `chow_hint="只有下家能吃"`。
- `tests/test_claim_stage_ws.py` 增：同上场景走 WS，断言 `state.snapshot.legal.actions` 含 chow、提交 `chow tiles=[1,2]` 后副露为 `123万`。
- 前端：`npm run typecheck` + 手工/自动化断言「吃」按钮存在且候选 1 种。

### 4. 分支处置

- 若日志证明后端确实漏发 → 修 `chow_options` / `_build_claim_window`，并把该日志降级为 DEBUG。
- 若证明是「非下家」→ 不改规则，以提示收口，并在 07 补「吃仅限下家」表述。
- 若证明是前端产物陈旧 → 走发版缓存刷新（`index.html` 不缓存 + 资源指纹），不改逻辑。

## 架构与数据流

```mermaid
graph LR
  U[浏览器/手机] -->|game.finish| A[RoomActor]
  A -->|can_end_room| C[role cache]
  C -->|首次/过期| F[familyService.isFamilyAdmin]
  F --> DB[(mj_family_member)]
  A -->|_abort_game + _close_room| DB2[(mj_room.roomStatus=CLOSED)]
  A -->|event.room_closed| U
  A -->|快照 viewer.can_end_game / legal.chow_hint| U
  H[HTTP POST /rooms/{id}/close] --> RS[roomService.closeRoom] --> F
```

## 目录结构（改动清单）

```
code/backend/src/
├── processor/familyService.py        # [MODIFY] 新增 isFamilyAdmin(familyID, loginID)，复用 ROLE_/STATUS_ 常量
├── processor/roomService.py          # [MODIFY] closeRoom 改用 isFamilyAdmin，权限文案与 WS 对齐
├── realtime/room.py                  # [MODIFY] 角色缓存 + role_of/refresh_role/can_end_room；_end_game 判定重排与管理员播报
├── realtime/snapshot.py              # [MODIFY] 快照增 viewer{is_host,member_role,can_end_game}；legal 增 chow_hint
├── game/engine.py                    # [MODIFY] _build_claim_window 末补取证日志；chow_hint 计算（legal_actions/available 层）
├── main/ws.py                        # [MODIFY] 握手与重连时刷新角色缓存（run_in_threadpool）
└── tests/
    ├── test_engine_flow.py           # [MODIFY] 柏氏重复张吃/碰并存；非下家提示；chow_hint
    ├── test_claim_stage_ws.py        # [MODIFY] WS 版同上
    ├── test_ws_flow.py               # [MODIFY] 管理员/观战管理员可结束；普通成员 FORBIDDEN；非本家庭 FORBIDDEN
    └── test_family_service.py        # [MODIFY] isFamilyAdmin 单测（OWNER/ADMIN/MEMBER/DISABLED/非成员）
code/frontend/src/
├── types.ts                          # [MODIFY] Snapshot.viewer、legal.chow_hint
├── stores/game.ts                    # [MODIFY] viewer/canEndGame/chowHint 计算属性；旧快照回退
├── components/table/ActionBar.vue    # [MODIFY] 渲染 chowHint（不可吃原因）
├── components/table/ScoreBoard.vue   # [MODIFY] 收桌按钮文案与权限文案
├── views/RoomView.vue                # [MODIFY] canEndGame 改服务端能力位；确认弹层文案
├── mobile/components/table/MobileScoreBoard.vue  # [MODIFY] 同上
└── mobile/views/MobileRoomView.vue   # [MODIFY] 同上
plan/                                 # [MODIFY] 改进文档 U-6/B-2、improve I15/I16、06 §8E、00、04、05、07、README
docs/系统总览.md、docs/规则设计.md     # [MODIFY] 摘要级同步（权限与吃牌提示）
```

## 实施要点

- 权限只在服务端判定，前端只用能力位；`closeRoom` 与 `_end_game` 必须调同一个 `isFamilyAdmin`，避免再次漂移。
- 角色查询不在快照路径上做 DB：握手/重连刷新 + 60s TTL；观战管理员同样缓存。
- 日志只记结构化摘要（seat/action/张数），不落手牌明文；`chow_skipped` 首次上线先 INFO，确诊后降 DEBUG。
- 兼容性：`viewer`、`chow_hint` 均为可选新增字段，旧前端忽略后回到 `isHost` 判定与无提示；`event.room_closed`、`CLOSE_FAILED` 语义不变。
- 发版：v1.1.4 三处版本号一致；后端可先 `41_backend_only.sh` 灰度，前端随 `12_redeploy.sh` 同发；重启会中断进行中对局，避开牌局时段。

## Agent Extensions

### SubAgent

- **code-explorer**
- Purpose: 实施前做一次调用面清点（`_end_game` / `closeRoom` / `canEndGame` / `legal_actions` 的全部调用点与测试夹具），确保改动不遗漏桌面与手机两条渲染链。
- Expected outcome: 输出「文件:行号」级影响清单，与本文目录结构逐项对齐，无未覆盖调用点。

### Skill

- **playwright-cli**
- Purpose: 桌面与手机横屏的自动化冒烟：管理员可见并点击「结束牌局」、吃牌场景动作条出现「吃」且不可吃时出现原因提示。
- Expected outcome: 两份可复现的截图/脚本输出，作为 v1.1.4 验收证据存入 `plan/v1.1.4-evidence/`。
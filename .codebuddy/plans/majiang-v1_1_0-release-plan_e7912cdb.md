---
name: majiang-v1.1.0-release-plan
overview: 基于 v1.1.0 运行反馈，先问题定位与根因归纳，再在 plan/ 下产出《改进和错误修复文档.md》《improve step-prompts.md》两份新文档，并同步修订总体规划、03/04/05/06/07/README/step-prompts 与 docs/ 相关章节，统一到 v1.1.0 版本口径，形成可执行的 7 步发布计划（本轮只写文档，不改代码）。
todos:
  - id: write-fix-report
    content: 新建 plan/改进和错误修复文档.md，逐条写 R/U/B 的现象、生产证据、根因、修复方案与验收
    status: completed
  - id: write-improve-prompts
    content: 新建 plan/improve step-prompts.md，编写 I0–I7 分步提示语与每步验收清单
    status: completed
    dependencies:
      - write-fix-report
  - id: sync-rules-docs
    content: 同步 07 柏氏细则 md/html 至 v1.9：番表 34 项、13 不靠宽松口径、258 赢、断幺、连六
    status: completed
    dependencies:
      - write-fix-report
  - id: sync-plan-docs
    content: 同步总体规划、03 规则族、06 实施计划、README 与 step-prompts，统一 v1.1.0
    status: completed
    dependencies:
      - write-fix-report
  - id: sync-proto-ui-docs
    content: 同步 04 协议（chow 校验/房态收尾/错误码）、05 UI（选牌态/庄标/字号）与 docs 说明
    status: completed
    dependencies:
      - write-fix-report
  - id: verify-consistency
    content: 核对链接、版本号 1.1.0、番表 34 项、错误码一致，输出一致性检查结论
    status: completed
    dependencies:
      - write-improve-prompts
      - sync-rules-docs
      - sync-plan-docs
      - sync-proto-ui-docs
---

## 用户需求

针对家庭麻将 v1.1.0 的运行反馈，**只产出文档与发布计划，不写业务代码**：先逐条定位每个问题的根本原因并归纳，再给出修复方案，最终形成可执行的 v1.1.0 发布计划；在 `plan/` 下新建《改进和错误修复文档.md》与《improve step-prompts.md》，并同步修订总体规划等相关文档，保证内容一致、版本统一为 1.1.0。

## 产品概述

一套部署在自有服务器上的家庭麻将 Web 应用（桌面 + 手机横屏两套界面），服务端权威判定吃碰杠胡、规则族可选、战绩落库。本次 v1.1.0 是"运行反馈修复版"：修正柏氏番种口径、重构吃牌与胡牌询问的交互模型、补齐结算页信息，并修复"结束牌局后房间仍挂在大厅"的生命周期缺陷。

## 核心功能

### 一、柏氏规则（番表 32 → 34 项）

- **258 赢**：最后赢张为 2/5/8 的数牌计 1 番，可与其它番种叠加（新增）。
- **十三不靠**：按"宽松版"重写——14 张，中发白各 1 必含，东南西北可选（各至多 1），数牌每门 0–3 张且同门同组（147/258/369），恰好一对将牌（可为数牌或字牌）；允许缺门。
- **连六**：确认"同花色连续 6 张（123456/234567/456789）计 1 番、可多组累加"，补条款与正反用例。
- **断幺**：整手牌（含副露）不含 1/9 数牌且不含任何字牌，计 1 番（新增）。

### 二、界面交互

- **胡牌优先**：同一玩家同时可胡与可吃碰时先出胡；选了"过"仅对当前这张牌生效，下一张照常提示胡。
- **吃牌选两张**：点"吃"进入选牌态，默认高亮候选组合，可点选/取消/改选两张后确认（如 234556 万配 4 万可选 234/345/456）；"取消"只退出选牌态，放弃需点"过"。
- **结算页庄家标记**：下方四位牌友卡片为庄家加"庄"徽标。
- **吃碰提示字号**：牌桌横幅与动作条"来牌/抢杠"提示字号整体放大 2 号，桌面与手机同口径。

### 三、Bug 修复

- 房主"结束牌局"后房间必须真正关闭（`roomStatus=CLOSED`、大厅立即消失、牌桌回大厅）；自然打满一圈同样收桌；重复点击幂等；WS 断线时以 HTTP 兜底，避免"以为结束了其实没结束"。

### 四、文档交付

- 新增《改进和错误修复文档.md》：逐条编号（R-1…R-4 / U-1…U-4 / B-1），含现象、复现与生产证据、根因（文件:行号）、修复方案、验收标准、风险与回滚。
- 新增《improve step-prompts.md》：I0 基线核对 → I1 房间生命周期 → I2 柏氏番表 → I3 胡牌优先 → I4 吃牌选两张 → I5 结算与字号 → I6 回归测试 → I7 发版，每步可直接开新对话执行。
- 同步总体规划、规则族、协议、UI、实施计划、柏氏细则（含 HTML）、文档索引与 `docs/` 说明文档，版本号统一为 v1.1.0。

## 技术栈与现状基线

- 后端：FastAPI + Uvicorn（同步路由 + 原生 WebSocket），`common/mysqlCommon.py` 为唯一 SQL 出口，MySQL 8.0 库 `mahjong_data`；前端：Vue 3 + TS + Vite 5 + Pinia + Tailwind 3，桌面 `src/` 与手机 `src/mobile/` 共用 `components/table/*`。
- 本次交付物为**文档**（`plan/*.md`、`plan/07-柏氏规则细则.html`、`docs/*.md`），实现步骤在文档中定义，供后续按步执行。
- 版本锚点：`code/backend/src/config/basicSettings.py:21 VERSION="1.0.0"`、`code/frontend/package.json "version":"1.0.0"`、`main/app.py` 的 `/api/health` 回显；目标统一为 `1.1.0`，柏氏细则升 `v1.9`。

## 根因归纳（写入文档的总纲）

| 类别 | 问题 | 根因（已核实） |
| --- | --- | --- |
| 规则实现漂移 | R-1 258 赢、R-4 断幺缺失；R-2 十三不靠口径不符 | 番表 `baishi/fan.py:34-67` 由元组驱动但只覆盖 32 项；`unrelated_pair():219-244` 用"扣将后 rest"校验，导致"明面禁风却可用风作将"的自相矛盾；规则修订只在代码里演进，07 细则与验收用例未同步 |
| 交互模型缺陷 | U-1 胡被吃碰抢先；U-2 吃牌只能点预算好的组合 | 询问是**窗口制并发**（`claims.py:12-56`、`engine.py:673-720`），一个座位一行窗口内只能提交一个动作，点吃即放弃胡，且 `passed*` 状态全仓为 0；吃牌由后端 `chow_options` 预算 3 组合 → 前端一按钮一组合（`ActionBar.vue:72-80`），无"选两张/取消/改选"，后端 `_do_chow():802-806` 也不校验顺子合法性 |
| 生命周期单路径 | B-1 结束牌局后大厅仍可见 | 自然打满走 `room.py:904-917 _finish_game()`，只关场次、`status="finished"`，**不写 mj_room、不 shutdown**；房主再点"结束"被 `room.py:933 status!="playing"` 拒绝；前端 `canEndGame` 用 `phase` 猜、`endGame()` 纯 WS 无 REST 兜底（`api/ws.ts:106-109` 静默丢弃），大厅仅 onMounted 拉取无自愈；`_persist` 吞异常可留幽灵房 |


生产证据（2026-10-30 只读核查）：`mj_room` 5 号房（10/30）与 4 号房（10/29）为 `OPEN` 且 `closedYMDHMS` 为 NULL，对应 `mj_game` 5/4 均为 `FINISHED`（各 5 局、4 局，自然打满）；日志中该路径无任何关房记录，而大厅关房入口（room 3）有 `关房 room=878437` 记录——证明"打满/结束不落 CLOSED"是主因，SQL 查询条件本身正确。

## 交付物设计

### 1. `plan/改进和错误修复文档.md`（新建）

结构：版本头部（v1.1.0 / 2026-10-30）→ §1 结论摘要（三类根因）→ §2 规则问题 R-1…R-4 → §3 交互问题 U-1…U-4 → §4 缺陷 B-1 → §5 修复方案总览（按文件）→ §6 验收与回归矩阵 → §7 风险与回滚 → §8 与其它文档的对应关系。每条统一模板：**现象 / 复现步骤与证据 / 根因（文件:行号）/ 修复方案（后端/前端/协议/数据）/ 验收标准 / 风险**。
关键口径：258 赢读 `ctx.win_tile`、可叠加；断幺基于 `ctx.all_tiles()` 含副露；十三不靠按宽松版重写（中发白必含、风牌可选、每门 0–3 张同组、恰好一对将）；连六确认"同花色 6 连、可多组"。

### 2. `plan/improve step-prompts.md`（新建）

I0 基线核对与口径冻结（不动代码）→ I1 房间生命周期（`realtime/room.py` `_finish_game/_end_game/shutdown/_persist`、`persist.py`、`mysqlCommon.update_mj_room_close`、`stores/game.ts` endGame+兜底、`RoomView/MobileRoomView` 口径对齐、大厅刷新）→ I2 柏氏番表（`baishi/fan.py` 加 `er_wu_ba_ying`/`duan_yao`、重写 `unrelated_pair`、`config.py`/`selfcheck.py`/`test_baishi_s7.py` 32→34、重跑 `tools/seedPresets.py`）→ I3 胡牌优先与过胡（`claims.py` 窗口内弃胡集合、`engine.py` 短路仲裁与 `legal.actions` 过滤）→ I4 吃牌选两张（`ActionBar.vue` 选牌态、`useHandCursor`/`MobileHand` 多选、`stores/game.ts` 提交、后端 `_do_chow` 严格校验 + 新错误码）→ I5 结算庄家徽标与字号 +2（`ResultModal.vue`、`RoomView.vue:355`、`MobileRoomView.vue:333`、`ActionBar.vue:39/41/76`）→ I6 回归（pytest + `npm run typecheck` + 建构建 + 手测清单）→ I7 发版（VERSION 1.1.0、备份、rsync、seed、restart、健康检查、验收回写）。每步含 目标/前置/必读/任务/验收清单/硬约束/完成后输出。

### 3. 文档同步矩阵

| 文档 | 同步内容 |
| --- | --- |
| `家庭麻将总体规划文档.md` | 状态行升 v1.1.0/2026-10-30；§4 功能清单补 R/U/B 条目；§9 新增 D18（房间结束即关房、幂等收尾+HTTP 兜底）、D19（番表 34 项、13 不靠宽松口径、窗口内过胡）；§10 加 P8（v1.1.0 修复发布）；§12 验收总则补 4 条；§13 索引改"34 项"并加两份新文档 |
| `03-规则族设计.md` | 番种 32→34（`:357/:377/:399`）、柏氏 §7.3 十三不靠口径与能力声明 |
| `07-柏氏规则细则.md` + `.html` | 标题版本 v1.9 与修订历史；§5 番表加 258 赢、断幺（32→34）；§6.2 连六条款确认；§6.3.4 十三不靠四条重写；§6.4 新增断幺；§6.7 区分"258 将"与"258 赢"；§13 补正反用例编号 |
| `04-协议设计.md` | §9.3 `game.action{chow}` 需两张合法牌 + 新错误码 `CHOW_TILES_INVALID`；§9.4 `event.claimed` 与胡的先后、`event.room_closed` 语义、`event.game_finished` 收场标记；§9.5 快照 `status` 权威语义 |
| `05-UI设计.md` | 动作条吃牌选牌态（默认组合、取消/改选、确认）、结算页庄家徽标、吃碰提示字号基线（+2 号） |
| `06-实施计划.md` | 新增 P8/v1.1.0 阶段、文件级改动清单、测试矩阵、回滚 |
| `plan/README.md` | 索引表加两份新文档、07 版本改 v1.9、术语表补 258 赢/断幺/过胡/收桌、变更记录追加 2026-10-30 |
| `step-prompts.md` | 回填 S6–S10 已完成（与实际代码一致），追加 I 系列并指向新文档 |
| `docs/系统总览.md`、`docs/规则设计.md` | 版本、番表项数、房间生命周期（结束即关房）、十三不靠口径 |


## 实施要点

- **本轮零代码改动**：只写/改 `.md` 与 `07` 的 `.html`；不跑构建、不改配置、不连库写入。
- **权威源不越界**：规则语义只落 `07`，其余文档做摘要 + 链接；表字段只认 `02`，协议只认 `04`。
- **口径一致性硬要求**：`34 项`、`1.1.0`、`v1.9`、错误码 `CHOW_TILES_INVALID` 在全部文档中编号与数值一致；改完执行链接死链检查与关键字 grep 校验（`32 项` 残留、`1.0.0` 残留、`待开始` 残留）。
- **发版风险记录**：无 DDL（`configJson` 已是 JSON）；番表生效依赖重跑 `tools/seedPresets.py`（仅覆盖 `familyID=0`，生产无自建模板，风险低）；旧房 `ruleSnapshot` 冻结旧番表；重启会中断进行中对局；前端须在本机构建后上传。
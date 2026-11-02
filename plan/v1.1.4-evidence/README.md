# v1.1.4 验收证据（U-6 收桌权限 / B-2 吃牌可解释性）

- 采集时间：2026-11-02
- 采集方式：`python plan/tools/smoke_v114.py`（本地「静态 + 假 REST + 假 WS」孪生后端，接真实构建产物 `dist` / `dist-mobile`，不动数据库、不需要真实账号）
- 产物：`01`～`08` 截图、`smoke-v114.log`（逐项 PASS/FAIL）、`smoke-v114-ws-messages.json`（假后端收到的客户端消息，可验证 `game.finish` 真的发了出去）

## 结果：12 项全 PASS

| # | 场景 | 断言 | 证据 |
| --- | --- | --- | --- |
| 1 | 桌面·家庭 ADMIN（观战，未入座） | `viewer.can_end_game=true` 时顶栏出现「结束牌局」 | `01-desktop-admin-endgame-entry.png` |
| 2 | 桌面·二次确认 | 点击后弹层出现（同文案按钮 2 个：入口 + 确认） | `02-desktop-admin-endgame-confirm.png` |
| 3 | 桌面·提交 | 确认后 WS 收到 `game.finish`（`sent=['state.resync','game.finish']`） | `03-desktop-admin-endgame-done.png` + `smoke-v114-ws-messages.json` |
| 4 | 桌面·无异常 | 无 `pageerror` | `smoke-v114.log` |
| 5 | 桌面·碰与吃并存 | 动作条同时出现「碰」「吃」（`1万1万2万3万` 遇 `1万`） | `04-desktop-chow-available.png` |
| 6 | 桌面·可吃时不提示 | 页面不含「只有下家能吃」 | `04` |
| 7 | 桌面·无权限不收桌 | 普通 MEMBER 无「结束牌局」入口 | `04` |
| 8 | 桌面·不可吃原因 | 非下家时显示「只有下家能吃」 | `05-desktop-chow-hint.png` |
| 9 | 手机·不可吃原因（667×375） | 提示同款显示且不折行、不挤掉按钮 | `06-mobile-chow-hint.png` |
| 10 | 手机·碰与吃并存 | 动作条「碰」「吃 1 种」「过」 | `07-mobile-chow-available.png` |
| 11 | 手机·更多入口 | `button[aria-label^="更多"]` 存在 | `08-mobile-admin-more-sheet.png` |
| 12 | 手机·更多里可收桌 | 面板内出现「结束牌局」 | `08` |

## 说明

1. 假后端按房间号选快照：`428915` = 观战 ADMIN 可收桌、`428916` = 可吃、`428917` = 非下家不可吃；快照字段严格按 [04 §9.5](../04-协议设计.md) 构造。
2. WebSocket 需要与静态页同源，脚本用 `add_init_script` 把 WS 端口重写到假后端（8899 → 8900），**不改动任何构建产物**。
3. 手机产物入口是 `mobile.html`（vite 多页构建），静态回退必须指向它，否则 404（本脚本已按部署同款处理）。
4. 本证据只覆盖**前端渲染与交互**；服务端权限与服务端 `chow_hint` 计算由 `tests/test_ws_flow.py`、`tests/test_family_service.py`、`tests/test_engine_flow.py`、`tests/test_claim_stage_ws.py` 覆盖（其中 `test_ws_flow` 需连测试库）。

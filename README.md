# 家庭麻将 · 一桌一世界

一套面向家庭成员、部署在自有服务器上的在线麻将 Web 应用。家人用账号登录，凭 6 位邀请码开桌入座，系统自动洗牌发牌、判定吃碰杠胡并结算积分，牌桌旁配有实时文字聊天与系统播报。

核心差异化能力是**规则模板**：房主开桌时选定一套可自定义的积分规则（底分、番种与番值、特殊牌型开关、杠分、封顶、出牌限时、听牌提示），选定后本局固定不变，让"自己定规矩"成为一等公民。

## 技术栈

| 层 | 选型 |
| --- | --- |
| 前端 | Vue 3 + TypeScript + Vite 5 + Pinia + Vue Router + Tailwind CSS |
| 后端 | FastAPI + Uvicorn（原生 WebSocket）+ SQLAlchemy 2.0 + Pydantic 2 |
| 数据库 | SQLite（WAL 模式），单文件、零运维，可用 `DATABASE_URL` 切 PostgreSQL |
| 认证 | PyJWT + 标准库 `hashlib.scrypt`（存储格式 `scrypt$n$r$p$salt$hash`） |

## 目录结构

```
004-majiang/
├── README.md
├── docs/
│   ├── 规则设计.md        # 规则模板字段、番种与三组开关的语义
│   ├── 协议.md            # WebSocket 信封、消息类型与错误码
│   └── 部署.md            # 阿里云部署全流程（Nginx + WSS + systemd + 备份）
├── backend/
│   ├── requirements.txt
│   ├── .env.example
│   ├── mahjong.db         # 运行后生成（WAL）、备份即拷文件
│   ├── app/
│   │   ├── main.py        # 应用装配、预置模板安装、SPA 静态托管
│   │   ├── core/          # 配置、scrypt + JWT、依赖注入、日志
│   │   ├── db/            # Declarative Base、7 张表 ORM
│   │   ├── schemas/       # RuleConfig（含三组开关）与 WS 消息契约
│   │   ├── api/           # REST 路由 + /ws 端点
│   │   ├── game/          # 纯逻辑牌引擎：牌、判胡插件、番种、结算、状态机
│   │   ├── realtime/      # RoomActor 房间、连接管理、分座位快照、落库
│   │   └── seeds/         # 4 套预置规则模板
│   └── tests/             # 76 个 pytest 用例（牌型/番种/开关/结算/流程/WS）
└── frontend/
    └── src/
        ├── views/         # 登录、大厅、规则、牌桌、战绩
        ├── components/table/  # Tile/HandTiles/DiscardRiver/PlayerSeat/ActionBar/...
        ├── stores/        # auth / game（快照 + 事件规约）/ chat
        └── api/           # http 封装、WS 单例（重连退避 + seq 去重 + resync）
```

## 本地启动

**运行时要求**：Node.js ≥ 20（Vite 5 硬性要求）、Python ≥ 3.11（开发用 3.13）。

### 后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env      # 改掉 SECRET_KEY；ADMIN_INIT_PASSWORD 留空会随机生成并打印一次
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

首次启动会自动建表、安装 4 套预置规则模板，并按 `ADMIN_INIT_USERNAME` / `ADMIN_INIT_PASSWORD` 创建管理员（`ADMIN_INIT_PASSWORD` 为空时随机生成，日志打印一次）。

### 前端

开发模式（热更新，代理 `/api` 与 `/ws` 到 8000）：

```powershell
cd frontend
npm install
npm run dev        # http://127.0.0.1:5173
```

生产模式（构建产物由后端同源托管，只需跑 8000）：

```powershell
cd frontend
npm run build      # 产出 frontend/dist，后端启动时自动挂载
```

> 后端检测到 `frontend/dist` 存在时，会把 `/assets` 静态挂载并把未知前端路由回退到 `index.html`；未匹配的 `/api/*` 一律返回 JSON 404，不会误落 HTML。

### Node 16 环境的备选降级

Vite 5 需要 Node 18+。若机器上只能停留 Node 16，可降级为 `vite@4.5.5` + `@vitejs/plugin-vue@4.6` + `vue@3.4` + `typescript@5.4`，其余代码无需改动。

## 验证

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q        # 76 passed
```

覆盖范围：牌编码与造墙 136 张、标准胡/七对/十三幺/十三不靠正反例、番种互斥去重与封顶、线性与 2^N 两种折算、三组开关的取值纪律（关闭时杠不计分仍可杠、超时关闭不产生 deadline、听牌关闭不下发）、自摸/点炮/荒庄分账、完整一局流程与仲裁优先级、WS 多人流程与聊天。

## 设计要点

- **判胡插件注册表**：`standard / seven_pairs / thirteen_orphans / thirteen_unrelated` 各自实现 `match` 与 `calc_fan`，新增牌型只加文件不动引擎。
- **牌用 0-33 计数数组**：34 长度递归拆解在微秒级，听牌提示对 34 种牌各试一次也远小于 1ms，不做缓存。
- **番种由规则数据驱动**：番种表是模板 JSON 的一部分，互斥组与前置条件在求值器里裁决，改规则不需要发版。
- **可选规则统一用「开关 + 从属配置」**：`turn_timeout` / `kong_score` / `ting_hint` 都是 `{enabled, ...}` 嵌套对象。关闭时服务端不计算、不下发、前端不渲染；从属值保留不清空，禁止用 `0`/`null`/`-1` 表达"未启用"。
- **服务端权威 + 分座位快照**：所有合法性在服务端判定，快照按座位生成，只给自己的手牌明文，从协议层杜绝抓包看牌。
- **claim 窗口仲裁**：出牌后开启固定 8 秒询问窗口，按「胡 > 碰/杠 > 吃」仲裁、同优先级按逆时针下家优先，结果与网络快慢无关。窗口超时与"出牌限时"是两个独立机制，后者关闭不影响前者。
- **单进程内存房间**：家庭规模（<20 用户、<3 桌）用 `dict[str, RoomActor]` + `asyncio.Lock` 足够。代价是进程重启会丢进行中的一局，因此每局结束立即落库，历史积分不受影响；`RoomStore` 接口留好了换 Redis 的口子。

## 已知取舍

- 房间状态在内存，重启最多丢"当前未结束的那一局"（历史场次、规则模板、账号不受影响）。启动时会把库里遗留的"进行中"场次自动标记为 `aborted`（战绩页显示"中断"），避免僵尸场次一直挂着。
- 同一账号可同时在多个设备/标签页在线，连接按用户维护列表，任一连接断开不影响其余连接。
- 未做语音：协议与数据表不含音频字段，沟通只有文字 + 系统播报。

## 部署

见 [docs/部署.md](docs/部署.md)：Nginx 反代与 WSS、systemd 守护、HTTPS 证书、SQLite 备份与回滚。

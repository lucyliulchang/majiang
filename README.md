# 家庭麻将 · 一桌一世界

面向家庭成员、部署在自有服务器上的在线麻将 Web 应用。家人用账号登录，凭 6 位数字邀请码开桌入座，系统自动洗牌发牌、判定吃碰杠胡并结算积分，牌桌旁配有实时文字聊天与系统播报。房主开桌时选定一套规则模板（规则族 + 族内参数），选定后本局固定不变。

## 当前状态

**重构规划阶段。** 代码已迁入 `code/`，后端代码在 `code/backend/src/`，运行时产物分离到 `code/backend/log`（日志）与 `code/backend/data`（附属数据）；现有实现仍是 SQLite + SQLAlchemy 版本。目标结构与实施顺序以 [`plan/`](plan/README.md) 为准，按 [`plan/step-prompts.md`](plan/step-prompts.md) 逐步执行。

## 目标技术栈

| 层 | 选型 |
| --- | --- |
| 前端 | Vue 3 + TypeScript + Vite 5 + Pinia + Vue Router + Tailwind CSS |
| 后端 | FastAPI + Uvicorn（原生 WebSocket）+ Pydantic 2 |
| 数据库 | MySQL 8.0（utf8mb4），pymysql + DBUtils 连接池 |
| 数据访问 | `mysqlCommon` 单一入口（表定义 `database/*.txt` + `mysqlCodeGenerator.py` 生成） |
| 账号 | contentHub 账号服务（A0A0/A3A0）+ `USER_BASIC` 档案表 + 本地 JWT |
| 文件 | 前端直访图片在 `code/backend/data/webserver/majiangapp/`（生产 `/data/webserver/majiangapp`） |

## 目录结构

```
majiang/
├── README.md
├── plan/                    # 规划（唯一来源）
│   ├── 家庭麻将总体规划文档.md
│   ├── 01-系统架构设计.md … 06-实施计划.md
│   └── step-prompts.md      # 分步实施提示语
├── docs/                    # 系统说明（总览/开发指南/部署/运维）
└── code/
    ├── backend/
    │   ├── src/             # 只有代码，运行时产物一律不落这里
    │   │   ├── app/         # 现有实现：FastAPI 装配 + api/core/db/game/realtime/schemas/seeds
    │   │   ├── schedule/    # crontab 驱动：dataClean、dataBackup、logslice + restore_*.sh
    │   │   ├── monitor/     # monitor.py（原样复制）+ monitorConfig.py（按项目维护）
    │   │   ├── scripts/     # 一次性运维脚本
    │   │   ├── tests/
    │   │   ├── .env.example
    │   │   ├── requirements.txt
    │   │   └── pytest.ini
    │   ├── log/             # 所有日志：应用日志 + cron 脚本日志（log/schedule/）
    │   └── data/            # 所有附属数据
    │       ├── db/          # SQLite（开发用）
    │       ├── test/        # 测试库
    │       ├── backup/      # 定时备份产物
    │       └── webserver/majiangapp/   # 前端可直接访问的图片（皮肤在 tiles/ 下）
    └── frontend/            # Vue 3 源码与构建产物（dist 不提交）
```

纪律：

- `src/` 只放代码；日志只写 `backend/log`，其他附属数据只写 `backend/data`。
- 前端需要直访的图片放 `backend/data/webserver/majiangapp/tiles/`，URL 前缀统一 `/majiangapp`（本地由后端挂载，生产由 Nginx 从 `/data/webserver/majiangapp` 出）。

## 部署映射（本仓库 → 服务器）

本仓库是**代码存储目录**，服务器只放代码与运行期目录，对应关系固定如下：

| 本仓库 | 服务器 | 说明 |
| --- | --- | --- |
| `code/backend/src/` | `/data/majiang/src/` | 唯一需要发布的代码树（rsync `--delete`） |
| `code/backend/log/` | `/data/majiang/log/` | 运行期生成，不随发布覆盖 |
| `code/backend/data/` | `/data/majiang/data/` | 运行期生成，不随发布覆盖（`db/`、`test/`、`backup/`） |
| `code/backend/data/webserver/majiangapp/` | `/data/webserver/majiangapp/` | **例外**：图片目录不在 `/data/majiang` 下；生产 `.env` 用 `UPLOAD_DIR=/data/webserver/majiangapp` 显式指过去 |
| `code/frontend/` | 不部署 | 前端源码只在本机/CI 构建；构建产物 `dist/` 平铺到 `/data/webserver/majiangapp/`（`tiles/` 除外） |

即 `code/backend` 整体对应 `/data/majiang`（其下 `src`、`log`、`data` 一一对应），`code/frontend/dist` 对应 `/data/webserver/majiangapp`。

## 文档导航

| 想知道 | 看 |
| --- | --- |
| 项目目标、范围、决策、里程碑 | [plan/家庭麻将总体规划文档.md](plan/家庭麻将总体规划文档.md) |
| 目录迁移、分层、账号链路、连接池 | [plan/01-系统架构设计.md](plan/01-系统架构设计.md) |
| 表与字段、生成流程 | [plan/02-数据库设计.md](plan/02-数据库设计.md) |
| 规则族与模板、番种、柏氏细则 | [plan/03-规则族设计.md](plan/03-规则族设计.md) |
| REST/WS 契约、错误码 | [plan/04-协议设计.md](plan/04-协议设计.md) |
| 视觉规范、牌面皮肤与切图 | [plan/05-UI设计.md](plan/05-UI设计.md) |
| 阶段与验收 | [plan/06-实施计划.md](plan/06-实施计划.md) |
| 分步开新对话实施 | [plan/step-prompts.md](plan/step-prompts.md) |
| 本地怎么跑、表怎么改、时间怎么存 | [docs/开发指南.md](docs/开发指南.md) |
| 上线与备份 | [docs/部署.md](docs/部署.md)、[docs/运维与备份.md](docs/运维与备份.md) |

## 本地启动（迁移完成后）

前置：Python 3.11+、Node 20+、MySQL 8.0、可达的 contentHub 账号服务。

```powershell
# 1. 数据库
mysql -u root -p -e "CREATE DATABASE mahjong_data DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"

# 2. 后端（运行目录是 src，日志与数据落在它上一层的 log/ 与 data/）
cd code/backend/src
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env      # 填 MySQL 口令、SECRET_KEY、ACCOUNT_SERVICE_URL
.\.venv\Scripts\python.exe tools\initTables.py --env local --seed
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 3. 前端
cd code/frontend
npm install
npm run dev        # http://127.0.0.1:5173，代理 /api、/ws、/majiangapp 到 8000

# 4. 生产构建（产物由 Nginx 托管；本地开发时后端同源托管）
npm run build      # 产出 code/frontend/dist
```

未装 MySQL 时可先用默认 SQLite：库文件自动落在 `code/backend/data/db/mahjong.db`，应用日志落在 `code/backend/log/mahjong.log`。

## 验证

```powershell
cd code/backend/src
.\.venv\Scripts\python.exe -m pytest -q
```

覆盖：牌编码与造墙（136/108）、牌型正反例、番种互斥与封顶、两种折算、三组开关取值纪律、自摸/点炮/荒庄分账、四族差异、家庭隔离、邀请码、皮肤上传与回退、WS 多人流程与聊天。

## 设计要点

- **账号不自建**：登录/注册/改密转发 contentHub 账号服务，`USER_BASIC` 只做档案镜像，本地 JWT 供 REST/WS 使用。
- **家庭隔离**：`mj_family` + `mj_family_member`；房间、模板、自定义皮肤、审计均带 `familyID`，跨家庭一律 403。
- **规则族 × 模板**：族决定引擎插件与可用开关（通用/广东/四川/柏氏），模板是族内预设；开桌与开局双快照，历史不可变。
- **多套牌面皮肤**：35 个资源键（34 张牌 + 牌背），后台可上传/启停/设默认；前端图片优先、缺图回退 CSS。
- **6 位数字邀请码**：`100000–999999` 全局唯一，冲突重试；入房校验家庭成员。
- **服务端权威 + 分座位快照**：只给自己的手牌明文，暗杠对他人不可见。
- **单进程内存房态**：家庭规模够用；每局结束立即落库，重启只丢当前局。

## 已知取舍

- 未迁移旧 SQLite 数据；账号在账号服务侧初始化。
- 未实现语音、录像、观战列表、排行榜。
- 广东/四川首期按文档默认值实现；柏氏细则已冻结于 `plan/07-柏氏规则细则.md`，引擎验收前禁止开桌。
- 单进程运行（`--workers 1`），多实例需先实现 `RoomStore` 共享。
- 前端生产前缀未接入：`vite base`、路由 base、REST base 仍是本地形态（`/`、`/api`），上线前按 [docs/部署.md §5.3](docs/部署.md) 的三项改完再构建。

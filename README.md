# 家庭麻将 · 一桌一世界

面向家庭成员、部署在自有服务器上的在线麻将 Web 应用。家人用 contentHub 账号登录，凭 6 位数字邀请码开桌入座，服务端权威洗牌发牌、判定吃碰杠胡并结算积分；牌桌旁有实时聊天与系统播报，桌面版与手机版共用一套后端。房主开桌时选定一套规则模板（规则族 + 族内参数），选定后本场固定不变。

## 当前状态

| 项 | 现状 |
| --- | --- |
| 版本 | **v1.1.5**（2026-11-03 上线）。后端 `config/basicSettings.py`、前端 `package.json`、桌面/手机登录页三处版本号一致，`GET /api/health` 回显同版本 |
| 阶段 | 开发与线上迭代并行，功能闭环已跑通真实家庭牌局；无「重构中」的未完成模块 |
| 数据源 | **只有 MySQL 8.0**。SQLite / SQLAlchemy 已移除，`DATABASE_URL` 仅为兼容旧配置保留、业务代码不再读取；`code/backend/src/db/` 是旧 ORM 的空目录残留，可直接删除 |
| 入口 | 桌面 `https://www.test.com/majiangapp/`，手机横屏 `https://www.test.com/mjmobile/`（`www.test.com` 为**占位示例域名，不是真实地址**；实际域名以部署为准。两站共用同一 server 的 `/majiangapi/` 与 `/majiangws`） |
| 运行形态 | Uvicorn 单进程（`--workers 1`）+ Nginx HTTPS/WSS + MySQL 8.0 同机；房态在内存，每局结束即落库 |

环境与库：

| 环境 | `APP_ENV` | 数据库 | 说明 |
| --- | --- | --- | --- |
| 本地 | `local` | `mahjong_data` | 本机开发，日志与数据落 `code/backend/log`、`code/backend/data` |
| 测试 | `test_server` | `mahjong_test` | 内网测试端，建表与冒烟演练 |
| 生产 | `server_01` | `mahjong_data` | 代码在 `/data/majiang/src`，站点在 `/data/webserver/{majiangapp,mjmobile}` |

## 功能现状

| 模块 | 已具备 |
| --- | --- |
| 账号 | 登录、注册（可关，短信验证码）、找回密码（验证码重置）、登出、改密、当前用户；口令校验全部转发 contentHub 账号服务，本地只存 `USER_BASIC` 档案镜像，自签 JWT 供 REST/WS 使用 |
| 家庭 | 家庭列表/创建/切换、成员增删改与角色（OWNER/ADMIN/MEMBER）、默认规则族与皮肤；房间、模板、自定义皮肤、审计均按 `familyID` 隔离，跨家庭一律 403 |
| 规则 | 4 个全局规则族（通用/广东/四川/柏氏）+ 家庭模板 CRUD、复制、校验、开桌快照；柏氏番表 **35 项**（含一只幺、258 赢、断幺、连6 四种组合、13 不靠宽松口径） |
| 牌桌 | 创建/关闭房间、邀请码入房、准备、开局、吃碰杠胡判定、结算、聊天、断线重连、观战；一场 = N 圈（开桌可选 1/2/4/8 圈，默认 4），一圈 4 个庄次，庄家胡牌连庄；打满圈数或房主/家庭管理员结束即关房 |
| 观战 | 满座后凭邀请码进房围观；一人一目标（每名在座玩家最多 10 名围观者，全房 40 个名额），断线保留 60 秒；围观人数在桌面/手机两端可见；观战关系只在内存、不落库 |
| 战绩 | 我的场次（含跨家庭客队场次）、场次详情、个人统计；每局结算写 `mj_game_round`（含终局四家手牌留痕）并累加 `mj_game_player.totalScore` |
| 皮肤 | 清单、35 个资源键（34 张牌 + 牌背）上传、发布、设默认、启停、软删；前端图片优先、缺图回退 CSS |
| 音效 | 15 个 SFX 键 + 40 个女声音频（34 张牌面报牌 + 6 种叫牌人声），由 WS 增量事件触发；旧合成叫牌音保留但不再触发，支持静音降级 |
| 审计 | 家庭成员、规则模板、皮肤变更留痕 |

v1.1.x 期间的关键行为修正（均已上线）：连6 补齐 345678 组合、13 不靠不再计门清/独赢、结算页与战绩页标记胡张、庄徽标跟随庄家轮转、叫牌改播人声、围观人数实时刷新、家庭管理员可结束牌局（收桌权限统一 `familyService.isFamilyAdmin`）、吃牌不可用时服务端下发 `chow_hint`、暗杠的牌名不再广播、桌面「轮到你出牌」提示移到本人上方。

## 技术栈

| 层 | 选型 |
| --- | --- |
| 前端 | Vue 3 + TypeScript + Vite 5 + Pinia + Vue Router + Tailwind CSS |
| 后端 | FastAPI + Uvicorn（原生 WebSocket）+ Pydantic 2 |
| 数据库 | MySQL 8.0（utf8mb4 / utf8mb4_0900_ai_ci），pymysql + DBUtils 连接池 |
| 数据访问 | `common/mysqlCommon` 单一入口；表定义 `database/*.txt` + `mysqlCodeGenerator.py` 生成 `auto_generated/`（禁手改） |
| 账号 | contentHub 账号服务（acis：A0A0/A3A0/A6A0/A9A0/AIA0/A5A0）+ `USER_BASIC` 档案表 + 本地 JWT |
| 静态资源 | 皮肤图片 URL 前缀 `/majiangapp`（本地后端挂载，生产 Nginx 从 `/data/webserver/majiangapp` 出） |
| 时间 | 统一 Asia/Shanghai，库内 `VARCHAR(16)` 存 `YYYYMMDDHHMMSS`，不用时间戳、不做时区换算（JWT `exp/iat` 除外） |

## 目录结构

```
majiang/
├── README.md
├── plan/                     # 规划与发布记录（唯一协议/表/规则来源）
│   ├── 家庭麻将总体规划文档.md
│   ├── 01-系统架构设计.md … 08-音效设计.md
│   ├── 07-柏氏规则细则.md
│   ├── 改进和错误修复文档.md
│   └── v1.1.0 … v1.1.5 发布记录 / 各批验收证据
├── docs/                     # 运行视角说明（总览、开发、部署、运维、使用手册）
├── code/
│   ├── backend/
│   │   ├── src/              # 只放代码，运行期产物一律不落这里
│   │   │   ├── main/         # FastAPI 装配：app.py、deps.py、ws.py、api/（REST 路由）
│   │   │   ├── processor/    # 领域服务与事务（account/family/room/rule/skin/history）
│   │   │   ├── common/       # mysqlCommon、mysqlHandle、securityCommon、loggingCommon、miscCommon
│   │   │   ├── config/       # basicSettings（常量/默认值）、localSettings（环境与派生路径）、mysqlSettings
│   │   │   ├── game/         # 引擎、牌型、番种、算分、families/*（通用/广东/四川/柏氏）
│   │   │   ├── realtime/     # 房态演员、按座位快照、落库
│   │   │   ├── schemas/      # Pydantic 契约
│   │   │   ├── database/     # 表定义 txt、生成器、auto_generated（禁手改）
│   │   │   ├── tools/        # initTables、seedPresets、bootstrapFamily、mergeMysqlCommon
│   │   │   ├── schedule/     # dataClean、dataBackup、logslice + restore_*.sh
│   │   │   ├── monitor/      # monitor.py + monitorConfig.py
│   │   │   ├── scripts/      # 一次性运维脚本
│   │   │   ├── tests/        # pytest（数据层用例连 mahjong_test）
│   │   │   ├── db/           # 旧 ORM 空目录残留，可删
│   │   │   ├── .env.example
│   │   │   ├── requirements.txt
│   │   │   └── pytest.ini
│   │   ├── log/              # 所有日志：应用日志 + cron 脚本日志（log/schedule/）
│   │   └── data/             # 附属数据：backup/、test/、webserver/majiangapp/tiles/
│   ├── frontend/             # Vue 3 源码；dist、dist-mobile 为构建产物（不提交）
│   └── deploy/               # 发版、巡检、冒烟脚本与 nginx/systemd 参考配置
```

纪律：

- `src/` 只放代码；日志只写 `backend/log`，其他附属数据只写 `backend/data`。
- 表结构只能改 `database/*.txt` 后跑生成器，`auto_generated/` 由生成器覆盖。
- 前端直访图片放 `data/webserver/majiangapp/tiles/`，URL 前缀统一 `/majiangapp`。

## 本地启动

前置：Python 3.11+、Node 20+、MySQL 8.0、可达的 contentHub 账号服务（默认 `http://127.0.0.1:8160/acis`）。

```powershell
# 1. 数据库
mysql -u root -p -e "CREATE DATABASE mahjong_data DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"
mysql -u root -p -e "CREATE DATABASE mahjong_test DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"

# 2. 后端（运行目录是 src，日志与数据落在上一层的 log/ 与 data/）
cd code/backend/src
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env          # 填 MYSQL_*_PASSWD、SECRET_KEY、ACCOUNT_SERVICE_URL
.\.venv\Scripts\python.exe tools\initTables.py --env local --seed
.\.venv\Scripts\python.exe -m uvicorn main.app:app --host 127.0.0.1 --port 8000 --workers 1

# 3. 前端（dev 用 base=/，代理 /api、/ws、/majiangapp 到 8000）
cd code/frontend
npm install
npm run dev          # 桌面 http://127.0.0.1:5173
npm run dev:mobile   # 手机版 http://127.0.0.1:5173/mobile.html

# 4. 生产构建（base 分别为 /majiangapp/ 与 /mjmobile/，产物在本机生成后上传）
npm run build          # → dist，入口 index.html
npm run build:mobile   # → dist-mobile，入口 mobile.html（降到 chrome78，兼容老安卓）
```

数据库不可用时后端仍能启动（请求层统一返回 503 `DB_UNAVAILABLE`），登录依赖账号服务可达性。

## 验证

```powershell
cd code/backend/src
.\.venv\Scripts\python.exe tools\initTables.py --env test_server --seed
.\.venv\Scripts\python.exe -m pytest -q      # 用例连 mahjong_test，不碰开发/生产库
cd ..\..\frontend
npm run typecheck
```

覆盖：牌编码与造墙、牌型正反例、番种互斥与封顶、两种折算、三组开关取值纪律、自摸/点炮/荒庄分账、四族差异、家庭隔离与管理员矩阵、邀请码入房、观战名额与跟随、皮肤上传与回退、WS 多人流程（含询问窗口、吃碰杠胡、聊天、重连、收桌）。

## 部署

拓扑：浏览器 → Nginx（443 HTTPS/WSS）→ Uvicorn `127.0.0.1:8000` → MySQL；静态站点由 Nginx 直出。

| 本仓库 | 服务器 | 说明 |
| --- | --- | --- |
| `code/backend/src/` | `/data/majiang/src/` | 唯一需要发布的代码树（`rsync --delete`，排除 `.env`） |
| `code/backend/log/`、`data/` | `/data/majiang/log/`、`/data/majiang/data/` | 运行期生成，不随发布覆盖 |
| `code/frontend/dist/` | `/data/webserver/majiangapp/` | 桌面站点（`tiles/`、`audio/` 等运行期资源不覆盖） |
| `code/frontend/dist-mobile/` | `/data/webserver/mjmobile/` | 手机站点（`assets` 只增不删，避免老页面 404） |
| — | `/data/webserver/majiangapp/tiles/` | 皮肤图片；生产 `.env` 用 `UPLOAD_DIR` 指到这里 |

`code/deploy/` 下的运维脚本（在目标服务器本机执行）：

| 脚本 | 用途 |
| --- | --- |
| `deploy.sh` | 全量发版：备份库+代码+前端 → 同步后端/桌面端 → 重启 → 健康检查 |
| `deploy-mobile.sh` | 只发手机版，不碰后端、不重启服务 |
| `41_backend_only.sh` | 只发后端（会重启服务，发版前先确认无进行中对局） |
| `rollback.sh` | 按备份时间戳回滚 |
| `check_state.sh` | 巡检：`/api/health`、OPEN 房、PLAYING 场次 |
| `14_close_stale_rooms.sh` | 关闭历史遗留的 OPEN 幽灵房 |
| `15_cleanup_smoke_rooms.sh` | 清理机器人冒烟房及其场次/局/参与者/聊天 |
| `smoke_bots.py`、`rule_check.py`、`ui_smoke.py` | 机器人真实牌局、规则用例核对、Playwright 界面冒烟 |

## 文档导航

| 想知道 | 看 |
| --- | --- |
| 规划文档索引、术语表、变更记录 | [plan/README.md](plan/README.md) |
| 目标、范围、决策、里程碑 | [plan/家庭麻将总体规划文档.md](plan/家庭麻将总体规划文档.md) |
| 分层、账号链路、连接池、部署拓扑 | [plan/01-系统架构设计.md](plan/01-系统架构设计.md) |
| 表与字段、生成流程 | [plan/02-数据库设计.md](plan/02-数据库设计.md) |
| 规则族与模板、番种 | [plan/03-规则族设计.md](plan/03-规则族设计.md)、[plan/07-柏氏规则细则.md](plan/07-柏氏规则细则.md) |
| REST/WS 契约、错误码 | [plan/04-协议设计.md](plan/04-协议设计.md) |
| 视觉规范、牌面皮肤与切图 | [plan/05-UI设计.md](plan/05-UI设计.md) |
| 音效触发与资源规格 | [plan/08-音效设计.md](plan/08-音效设计.md) |
| 运行反馈问题台账与修复验收 | [plan/改进和错误修复文档.md](plan/改进和错误修复文档.md) |
| 逐版本上线记录 | [plan/v1.1.5-发布记录.md](plan/v1.1.5-发布记录.md) 等 |
| 本地怎么跑、时间怎么存、表怎么改 | [docs/开发指南.md](docs/开发指南.md) |
| 运行视角总览 | [docs/系统总览.md](docs/系统总览.md) |
| 上线与备份恢复 | [docs/部署.md](docs/部署.md)、[docs/运维与备份.md](docs/运维与备份.md) |
| 家人使用说明 | [docs/manual.html](docs/manual.html) |

## 已知边界

- **单进程**：房态只在内存，重启会中断进行中的对局（启动时把库里的 `PLAYING` 场次标记为 `ABORTED`，已结算的每局积分不受影响）；多实例需先实现共享 `RoomStore`。
- **无 migration 工具**：建表/加列走 `tools/initTables.py` 幂等 DDL（`CREATE TABLE IF NOT EXISTS` + 索引检查），生产改表靠「备份 + 测试库演练 + 保留回滚 DDL」。
- **观战不落库**：名额与跟随关系只在内存，进程重启即清空。
- **账号不自建**：注册默认关闭（`ACCOUNT_ALLOW_REGISTER=false`），账号由管理员在 contentHub 侧创建；账号服务不可用时无法登录，已签发 JWT 在过期前仍可用。
- **未实现**：语音聊天、录像回放、排行榜、观战列表大厅；Android 客户端仅有规划文档。

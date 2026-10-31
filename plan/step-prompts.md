# 家庭麻将 · 分步实施提示语

> 配套：[家庭麻将总体规划文档.md](家庭麻将总体规划文档.md)｜[01-系统架构设计.md](01-系统架构设计.md)｜[02-数据库设计.md](02-数据库设计.md)｜[03-规则族设计.md](03-规则族设计.md)｜[04-协议设计.md](04-协议设计.md)｜[05-UI设计.md](05-UI设计.md)｜[06-实施计划.md](06-实施计划.md)｜[08-音效设计.md](08-音效设计.md)
> v1.1.0 运行反馈修复见 [改进和错误修复文档.md](改进和错误修复文档.md) 与 [improve step-prompts.md](improve%20step-prompts.md)（I0–I8）。
>
> **使用方法**：每一步**单独开一个新对话**，把该步 `text` 围栏内的提示语整段复制过去。
> 前一步验收未通过，不要开始下一步。
> 每步结束统一输出：**改动文件清单 + 验收结果 + 遗留问题**。

## 当前状态（2026-10-30）

| 步骤 | 范围 | 状态 |
| --- | --- | --- |
| S0 | 文档评审与口径冻结 | 已完成（2026-10-27，结论见 plan/README.md） |
| S1 | 目录迁移与后端骨架 | 已完成（2026-10-27） |
| S2 | MySQL 表定义与生成链路 | 已完成（2026-10-27） |
| S3 | 账号服务接入与 JWT | 已完成（2026-10-27） |
| S4 | 家庭实体与数据隔离 | 已完成（2026-10-27） |
| S5 | 数据层改造（移除 ORM） | 已完成（2026-10-27，提交 B1–B5，pytest 126 绿） |
| S5b | 观战跟随与围观上限 | 已完成（2026-10-27，纯内存态，pytest 138 绿） |
| S6 | 规则族：通用族等价迁移 | 已完成（2026-10-29，随「并入 S6–S10」提交上线） |
| S7 | 规则族：广东/四川/柏氏 | 已完成（2026-10-29；柏氏番表 32 项已上线，v1.1.0 升 34 项） |
| S8 | 皮肤系统后端 | 已完成（2026-10-29） |
| S9 | 音效模块（前端 SFX） | 已完成（2026-10-29） |
| S10 | 前端适配、皮肤管理、联调部署 | 已完成（2026-10-29，生产 https://www.iottest.online/majiangapp/） |
| **I0–I8** | **v1.1.0 运行反馈修复 + 场次时长** | 见 [improve step-prompts.md](improve%20step-prompts.md)；I0–I6、I8 已实施，**I7 发版已完成（2026-10-30 21:38 上线生产，10-31 完成幽灵房清理与桌面/手机冒烟）——见 [I7-发布记录.md](I7-发布记录.md)** |

**下一步**：v1.1.0（I7）已上线；**v1.1.1（I9–I12 / P10：一只幺、13不靠 判番、牌面人声报牌、胡张标记）已于 2026-10-31 14:06 上线生产（未做冒烟，见 [v1.1.1-发布记录.md](v1.1.1-发布记录.md)）**；后续补做本批的冒烟与验收。

**2026-10-27 追加**：观战改为「一人一目标、每名在座玩家最多 10 人围观」（G13 / D17），新增 S5b（阶段 P4b）。该约束不新增表：S0–S2 已建的 `USER_BASIC` + 14 张 `mj_*` 保持不变，观战关系只存 `RoomActor` 内存。
**2026-10-30 追加**：运行反馈修复另立 v1.1.0 的 I0–I8 步骤（本文 S 系列不再追加），问题台账见 [改进和错误修复文档.md](改进和错误修复文档.md)。

文档有变更时先改 `plan/`，再按顺序推进；不要跳步。

## 全局约定（每步都适用）

| 项 | 约定 |
| --- | --- |
| 代码根 | `d:/StevenLianData/0301. Private Project/gitData/majiang/code/` |
| 文档根 | `d:/StevenLianData/0301. Private Project/gitData/majiang/plan/` |
| 后端根 | `code/backend/`（等价 contentHub 的 `code/src`） |
| 前端根 | `code/frontend/` |
| Python | 3.11+；venv 建在 `code/backend/.venv` |
| MySQL | 8.0；库 `mahjong_data` / 测试 `mahjong_test`；utf8mb4 |
| 表定义 | `code/backend/database/*.txt` 是唯一数据源，禁止手改 `auto_generated/` |
| 业务层 | **禁止裸 SQL**，一律走 `common/mysqlCommon.py` |
| 账号 | 不自建；只用账号服务 + `USER_BASIC` + 本地 JWT |
| 家庭 | 所有家庭域查询必须带 `familyID`；跨家庭一律 403 |
| 观战 | 一人一目标；每名在座玩家最多 10 人围观（4×10=40）；只存内存、不落库、不做观战名单 |
| 邀请码 | 6 位纯数字 `^[1-9][0-9]{5}$` |
| 时间 | DB 用 `VARCHAR(16)` 本地时间；WS 倒计时用 epoch 秒 |
| 协议 | 字段与 JSON 用 `snake_case`；DB 列名用 `camelCase` |
| 提交 | 每步一个可回退的 commit；不混入无关格式改动 |

## 目录

- S0 · 文档评审与口径冻结
- S1 · 目录迁移与后端骨架
- S2 · MySQL 表定义与生成链路
- S3 · 账号服务接入与 JWT
- S4 · 家庭实体与数据隔离
- S5 · 数据层改造（移除 ORM）
- S5b · 观战跟随与围观上限
- S6 · 规则族：通用族等价迁移
- S7 · 规则族：广东/四川/柏氏
- S8 · 皮肤系统后端
- S9 · 音效模块（前端 SFX）
- S10 · 前端适配、皮肤管理、联调部署

---

## S0 · 文档评审与口径冻结

> **什么时候做**：现在。后续所有步骤以本步结论为准。

````text
【家庭麻将 · S0 · 文档评审与口径冻结】

## 目标
把 plan/ 下的规划文档评审到"可照着做"的粒度，冻结术语、字段、接口与阶段边界，不改任何代码。

## 前置
无。当前仓库只有 backend/、frontend/、docs/、README.md，还没有 code/。

## 必须先读
- plan/家庭麻将总体规划文档.md
- plan/01-系统架构设计.md
- plan/02-数据库设计.md
- plan/03-规则族设计.md
- plan/04-协议设计.md
- plan/05-UI设计.md
- plan/06-实施计划.md
- docs/规则设计.md、docs/协议.md（现状基线）

## 任务
1. 交叉核对四张清单，列出不一致项并修正文档：
   - 表名/字段名（02 与 04 的 login_id、family_code、rule_family_code、room_code）
   - 规则配置字段（03 与 04，必须 snake_case）
   - 牌面资源键（04/05，必须 1m/1p/1s/east…white/back）
   - 错误码（03 与 04）
2. 核对既有实现事实（7 表/22 端点/5 视图/76 用例）是否与 00 文档一致；不一致以代码为准改文档。
3. 柏氏细则已冻结于 `plan/07-柏氏规则细则.md`；核对 03 §7 摘要与 07 的数值/判定是否一致，冲突以 07 为准。
4. 在 plan/README.md 更新各文档状态为"已评审"。
5. 输出"评审结论"：通过 / 需修改项 / 未决问题（不超过 5 条）。

## 验收清单
- [ ] plan/ 内所有相对链接可打开，无死链。
- [ ] 02 的表清单 = 1 张 USER_BASIC + 14 张 mj_*；字段名无同义异名。
- [ ] 04 的每个端点都能在 02 找到对应表；每个错误码都有触发场景。
- [ ] 05 的 35 个 tile_key 与 04 的示例一致。
- [ ] 03 的四族 `capability` 字段名统一 snake_case。
- [ ] 未决问题清单已记录，且不阻塞 S1。

## 硬约束
- 只改 plan/ 与 docs/ 下的 .md；不改代码、不建 code/、不执行安装命令。
- 不臆造柏氏规则细则；数值与判定一律以 07 为准，07 未覆盖的先问再写。
- 不删除现有 docs 内容，改为"跳转说明"时保留原文链接。

## 完成后必须输出
1. 改动文件清单（路径 + 改了什么）。
2. 验收结果（逐条勾选，附关键 grep/链接检查结果）。
3. 遗留问题（未决项、需要用户拍板的地方）。
````

---

## S1 · 目录迁移与后端骨架

> **什么时候做**：S0 通过后。此步保持服务可运行，不引入 MySQL。

> **现状（2026-10-27）**：目录迁移已完成——`backend/`、`frontend/` 已迁入 `code/`，后端代码在 `code/backend/src/`，运行时日志在 `code/backend/log`，附属数据在 `code/backend/data`。本步剩余工作是把 `src/app/` 拆为 `main/`、`processor/`、`common/`、`config/` 等骨架；下文提到的旧路径一律相对于 `code/backend/src/`，启动/测试命令在同目录执行。

````text
【家庭麻将 · S1 · 目录迁移与后端骨架】

## 目标
把 backend/、frontend/ 迁入 code/，后端按 contentHub 的 code/src 骨架重排，修正所有硬编码路径，服务仍能用 SQLite 过渡运行。

## 前置
S0 验收通过；工作区干净（git status 无未提交改动）。

## 必须先读
- plan/01-系统架构设计.md §3（旧→新映射）、§13（迁移检查清单）
- plan/06-实施计划.md §2
- 现有代码：backend/app/main.py、backend/app/api/*.py、backend/tests/conftest.py、backend/pytest.ini、frontend/vite.config.ts、README.md

## 任务
1. git mv backend code/backend、frontend code/frontend；不要复制后删原目录（保留 git 历史）。
2. 后端重排：
   - main/app.py（装配）、main/api/*.py（路由）、main/deps.py、main/ws.py
   - processor/（空壳，仅目录与 __init__.py）
   - common/{miscCommon,securityCommon}.py
   - config/{basicSettings,localSettings}.py
   - schemas/、game/、realtime/、tools/、tests/
3. 修正硬编码：
   - main/app.py 的 dist_dir 指向 code/frontend/dist（按新 __file__ 层级重算 parents）
   - tests/conftest.py 的 sys.path 与测试库路径
   - pytest.ini testpaths
   - .env.example 的工作目录说明
4. 更新 README.md 与 docs/*.md 的所有路径命令（cd backend → cd code/backend）。
5. 保持 SQLAlchemy 与 SQLite 可运行；本步不删任何业务逻辑。
6. 建立 `code/backend/src/tools/` 与 `code/backend/data/webserver/majiangapp/tiles/`（`.gitkeep`）。

## 验收清单
- [ ] 目录结构符合 01 §3.1；旧 backend/ frontend/ 不存在。
- [ ] `cd code/backend/src && python -m uvicorn main.app:app --port 8000` 启动成功。
- [ ] GET /api/health 返回 {"ok":true,...}。
- [ ] cd code/frontend && npm ci && npm run build 产出 code/frontend/dist。
- [ ] 后端能托管 / 与 /assets；未知 /api/* 返回 JSON 404。
- [ ] `cd code/backend/src && pytest -q` → 76 passed。
- [ ] grep -rn "cd backend\|cd frontend\|backend/app\|frontend/dist" README.md docs/ plan/ 无过期路径。
- [ ] git log --follow 能看到迁移前历史（至少抽 1 个文件验证）。

## 硬约束
- 不改业务行为、不改接口、不改表结构。
- 不删除 SQLite 相关代码（S5 才删）。
- 不提交 .venv、node_modules、dist、data/webserver 下的二进制。
- 每步一个 commit，message 形如 "chore(S1): move code into code/ and reshape backend skeleton"。

## 完成后必须输出
1. 改动文件清单（含重命名）。
2. 验收结果（命令 + 实际输出摘要）。
3. 遗留问题（路径 greps 未清理项、导入告警等）。
````

---

## S2 · MySQL 表定义与生成链路

> **什么时候做**：S1 通过后。数据库先行，后续所有数据层改造依赖本步。

````text
【家庭麻将 · S2 · MySQL 表定义与生成链路】

## 目标
落地 database/userBasic.txt 与 14 张 mj_*.txt，跑通 mysqlCodeGenerator → mergeMysqlCommon → initTables 全链路，空库可建表并灌入种子。

## 前置
S1 通过；本机 MySQL 8.0 可用；已建空库 mahjong_data 与账号 mjapp（utf8mb4）。

## 必须先读
- plan/02-数据库设计.md 全文（尤其 §2 生成器约束、§3 表定义、§6 流程）
- plan/01-系统架构设计.md §7（数据访问红线）、§8（连接池）
- contentHub 参考实现：code/src/database/mysqlCodeGenerator.py、tools/genTableCode.ps1、tools/mergeMysqlCommon.py、tools/initTables.py、common/mysqlCommon.py 头部注释

## 任务
1. 复制 mysqlCodeGenerator.py 到 code/backend/database/（保留版本头，不修改生成逻辑）。
2. 按 02 §3 逐字落盘 15 个 txt（userBasic.txt + 14 个 mj_*.txt）；检查：单空格、无 Tab、COMMENT 无 % 与 #、首列 recID INT。
3. 新增 config/mysqlSettings.py：
   - 环境映射（local/test_server/server_01）
   - 写句柄 dbW、读句柄 dbR，口令只取环境变量
   - MYSQL_SKIP_CONNECT=1 时 mysqlDB=None
4. 新增 common/mysqlHandle.py：DBUtils.PooledDB（maxconnections 可配，blocking=True，ping=1）、begin/commit/rollback、ping 失败重连一次。
5. 新增 common/mysqlCommon.py：
   - 生成区占位标记
   - 手写 USER_BASIC 7 个函数（createUserBasic/dropUserBasic/queryUserBasic/insertUserBasic/updateUserBasic/deleteUserBasic/statUserBasic，可选 getUserInfoMysql；与 contentHub 同名同签名）
   - transaction()、normalizeJsonValue4DB、MYSQL_JSON_COLUMN_NAME_LIST、表名常量
   - query_mj_* 列表/详情（先只实现 02 §8 列出的函数签名，返回空实现可后续补）
6. 新增 tools/genTableCode.ps1（cd database、只处理 mj_*.txt、-t 去 mj_ 与下划线、失败 exit 1）。
7. 新增 tools/mergeMysqlCommon.py（抽 #mysqlCommon code begin/end，校验 7 函数，丢弃生成 query_*）。
8. 新增 tools/initTables.py（CREATE IF NOT EXISTS + indexes.txt + mj_schema_version；禁 DROP）与 tools/seedPresets.py、tools/bootstrapFamily.py。
9. 执行生成 → 合并 → 建表 → 种子；记录第一条 mj_schema_version。

## 验收清单
- [ ] database/auto_generated/ 有 14 个 auto_gen_code_mj_*.py；每个产物含 create/drop/delete/insert/update/tablename_convertor。
- [ ] mergeMysqlCommon.py 退出码 0，7 个函数/表齐全；重跑两次手写区无 diff。
- [ ] SHOW TABLES 含 USER_BASIC + 14 张 mj_*。
- [ ] SHOW CREATE TABLE mj_room：roomCode char(6) + UNIQUE；recID int auto_increment。
- [ ] SHOW CREATE TABLE USER_BASIC：44 列，主键 loginID（与 contentHub `userBasic.txt` 列数一致）。
- [ ] SELECT COUNT(*) FROM mj_rule_family = 4；mj_rule_template 预置 = 4；mj_tile_skin = 1。
- [ ] initTables.py 重复执行不报错、不丢数据。
- [ ] MYSQL_SKIP_CONNECT=1 python -c "import common.mysqlCommon" 不阻塞、不建连。
- [ ] 插入 ruleSnapshot='' 不报 3140（normalizeJsonValue4DB 生效）。

## 硬约束
- 只走 readFromFile() 路径（-i mj_xxx.txt），禁止 handleSQL()/原生 DDL。
- 必须在 database/ 目录执行并传裸文件名。
- 禁止 DROP；禁止手改 auto_generated/。
- 口令不写进代码/文档/日志。
- 时间列统一 VARCHAR(16)，不要用 DATETIME。

## 完成后必须输出
1. 新增/修改文件清单。
2. 生成与建表的命令 + 输出摘要（表数量、种子数量、版本记录）。
3. 遗留问题（未实现的手写查询、生成器告警）。
````

---

## S3 · 账号服务接入与 JWT

> **什么时候做**：S2 通过后。先打通"能登录"，再谈家庭与业务。

````text
【家庭麻将 · S3 · 账号服务接入与 JWT】

## 目标
移除自建账号与 scrypt 口令，登录/注册/改密/登出全部转发 contentHub 账号服务；登录成功后同步 USER_BASIC 并签发本地 JWT。

## 前置
S2 通过；账号服务可达（ACCOUNT_SERVICE_URL，默认 http://127.0.0.1:8160/acis）；测试账号已存在。

## 必须先读
- plan/01-系统架构设计.md §5（账号链路）
- plan/04-协议设计.md §2（认证、注册与找回口令，含 §2.1–2.5）
- plan/02-数据库设计.md §3.1（USER_BASIC）
- contentHub：common/accountClient.py、main/subfunc/accountSvcClient.py、processor/transferCHMysql.py 的 writeUser2UserBasic

## 任务
1. 移植 common/accountClient.py：CMD 常量、30s 超时、异常收敛、B0 成功、CI 不可用。
2. 新增 processor/accountService.py：
   - login(login_id, passwd)：A0A0 → 失败映射 ACCOUNT_AUTH_FAILED；成功 A3A0 取资料
   - syncUserBasic：queryUserBasic 存在则 update 差异字段，否则 insert（写 regID/regYMDHMS）
   - register / logout(A5A0) / changePassword(A9A0)
   - 角色映射：contentHub `USER_ADMIN_ROLE_LIST`（`administrator`/`manager`）→ admin，否则 member；缺省 ACCOUNT_DEFAULT_ROLE；回写 acis 用 `ROLE_ACCOUNT_ROLE`
3. 新增 common/securityCommon.py：JWT 签发/校验（HS256，sub=loginID，role，iat/exp）。
4. 重写 main/api/auth.py：login/register/logout/me/password/server-time；错误码按 04 §10。
5. main/deps.py：current_user（JWT → USER_BASIC 摘要）、require_admin。
6. 删除 scrypt 口令校验与 users 表读写（users 模型可留到 S5 删）。
7. .env.example 增加 ACCOUNT_* 与 SECRET_KEY；启动时检查账号服务可达性并打印结果（不阻塞启动）。
8. 注册链：`POST /api/auth/verify-code`（A6A0）+ `POST /api/auth/register`（A0A0 + verifyCode）；`ACCOUNT_ALLOW_REGISTER` 关闭时 403 且不触达账号服务；注册成功只同步 USER_BASIC，不签 JWT。
9. 找回口令链：`POST /api/auth/verify-code`（scene=reset_password）+ `POST /api/auth/password/reset`（A9A0 + verifyCode）；`ACCOUNT_ALLOW_PASSWORD_RESET` 开关；账号不存在时对外仍返回 ok，仅审计留痕。
10. `GET /api/auth/options` 返回两个开关与冷却秒数；本地限流「60 秒冷却 + 5 次失败」（进程内计数）。
11. 前端 RegisterView / ForgotPasswordView + 公开路由；登录页入口按 options 渲染（见 05 §4.1.1–4.1.2）。

## 验收清单
- [ ] 正确账号口令登录返回 token + user + families（families 暂为空数组）。
- [ ] 错误口令返回 ACCOUNT_AUTH_FAILED，不泄露账号是否存在。
- [ ] 账号服务停机时返回 503 ACCOUNT_SERVICE_UNAVAILABLE，且 USER_BASIC 无新增记录。
- [ ] 首次登录插入 USER_BASIC，columns 与 02 §3.1 一致；二次登录无变化字段不 update。
- [ ] JWT 篡改/过期返回 401 UNAUTHORIZED。
- [ ] 日志中 grep 不到 passwd/口令明文。
- [ ] POST /api/auth/logout 返回 ok，账号服务不可达也不影响本地返回。
- [ ] 注册：未发码返回 VERIFY_CODE_REQUIRED；错码返回 VERIFY_CODE_INVALID；重复账号返回 ACCOUNT_LOGIN_ID_EXISTS；开关关闭时 403 且账号服务零调用。
- [ ] 找回口令：未注册手机号发码返回 ok；重置成功后旧口令失败、新口令成功；同一验证码二次提交失败。
- [ ] 验证码 60 秒冷却、5 次失败锁定生效；options 与实际开关一致。

## 硬约束
- 本地绝不校验口令；passwd 不进日志、不回显。
- 不在 JWT 放家庭信息。
- 账号服务异常不得产生半登录状态（不写 pref、不签 token）。
- 不新增账号表；USER_BASIC 44 列不改（找回口令只更新 passwd/passwdYMDHMS 镜像）。
- 验证码只在账号服务侧生成与校验，本地不建表、不落 Redis、不缓存明文；md5(passwd+loginID) 只在后端计算，前端不哈希。

## 完成后必须输出
1. 文件清单。
2. 验收结果（含一次真实登录的请求/响应摘要，脱敏）。
3. 遗留问题（账号服务角色命名差异、注册开关等）。
````

---

## S4 · 家庭实体与数据隔离

> **什么时候做**：S3 通过后。先把隔离跑通，再改业务端点。

````text
【家庭麻将 · S4 · 家庭实体与数据隔离】

## 目标
实现 mj_family / mj_family_member / mj_user_pref 的读写与权限校验，提供家庭与成员接口，并把"家庭上下文"固化为 deps。

## 前置
S3 通过（JWT 可用）。

## 必须先读
- plan/01-系统架构设计.md §6（家庭上下文）、§7（数据访问）
- plan/04-协议设计.md §3、§4
- plan/02-数据库设计.md §3.2–3.4、§8

## 任务
1. processor/familyService.py：
   - createFamily（创建者 OWNER + lastFamilyID，事务）
   - listMyFamilies（join member，ACTIVE）
   - getFamily / updateFamily（owner/admin）
   - listMembers / addMember（AIA0 校验 + USER_BASIC 同步）/ updateMember / removeMember
   - transferOwner（同一事务，owner 唯一）
   - assertMember(loginID, familyCode) / assertFamilyAdmin
2. main/api/families.py：8 个端点（04 §3）。
3. main/api/user.py：GET/PUT /api/user/pref（04 §4）。
4. main/deps.py：current_family（从 query/body/资源解析 + 校验成员）、require_family_admin、require_system_admin。
5. 审计：成员/家庭变更写 mj_audit_log（actionCode：FAMILY_CREATE/FAMILY_UPDATE/MEMBER_ADD/MEMBER_UPDATE/MEMBER_REMOVE/OWNER_TRANSFER）。
6. tools/bootstrapFamily.py：按 --owner/--name/--code 建首个家庭（幂等）。

## 验收清单
- [ ] 创建家庭返回 family，成员表有 OWNER 记录，pref.lastFamilyID 已写。
- [ ] 同一 family_code 重复创建返回 409 或幂等返回既有家庭（二选一并保持一致）。
- [ ] 添加成员：账号不存在 → ACCOUNT_USER_NOT_FOUND；已在家庭 → 400。
- [ ] 非成员 GET /api/families/{code} → 403 NOT_FAMILY_MEMBER。
- [ ] 非 admin 添加/停用成员 → 403 NOT_FAMILY_ADMIN。
- [ ] owner 不能移除自己；转让后新旧 owner 角色正确、owner 唯一。
- [ ] 家庭停用后房间/模板/皮肤接口返回 FAMILY_DISABLED。
- [ ] 审计表有对应记录，detailJson 可解析。

## 硬约束
- 家庭域查询必须 SQL 带 familyID，不得内存过滤。
- 禁止数据库外键；关系由应用层事务保证。
- 跨家庭错误不泄露资源是否存在（统一文案）。
- 成员角色只允许 OWNER/ADMIN/MEMBER。

## 完成后必须输出
1. 文件清单。
2. 验收结果（隔离用例的命令与结果）。
3. 遗留问题（成员邀请方式、owner 转让 UI 等）。
````

---

## S5 · 数据层改造（移除 ORM）

> **什么时候做**：S4 通过后。这是最大的一步，按端点分批，每批可独立验收。

````text
【家庭麻将 · S5 · 数据层改造（移除 ORM）】

## 目标
删除 SQLAlchemy/Alembic，现有 22 个 REST 端点与实时落库全部改走 mysqlCommon，补齐事务、分页与查询函数（全量端点见 04，共 44 个；新增端点由 S3/S4/S8 直接建在 mysqlCommon 上）。

## 前置
S4 通过；S2 的 mysqlCommon 已可用；准备测试库 mahjong_test。

## 必须先读
- plan/01-系统架构设计.md §7、§8、§9
- plan/02-数据库设计.md §8（常用查询）
- plan/04-协议设计.md §5–§7
- 现有代码：app/api/*.py、app/realtime/persist.py、app/realtime/room.py、app/main.py

## 任务（按批次提交）
B1 模板与房间：rules.py、rooms.py → processor/ruleService、roomService；补齐 query_mj_rule_template_*、query_mj_room_*。
B2 战绩：history.py → historyService + 聚合查询，消除 N+1，分页改 limit+before_id。
B3 实时落库：persist.py 四个函数改 mysqlCommon；save_round 用 UPDATE totalScore=totalScore+?；协程内用 run_in_threadpool。
B4 启动逻辑：main/app.py 的 bootstrap/close_stale_games 改 mysqlCommon；删除 init_db 与 SessionLocal。
B5 清理：删除 app/db/*、app/core/deps.py 的 Session、requirements 中 sqlalchemy/alembic；pytest conftest 改测试库。

## 验收清单
- [ ] grep -rn "sqlalchemy|SessionLocal|declarative_base|create_all" code/backend 为 0（测试文件也不残留）。
- [ ] 现有 22 个端点全部实跑，响应字段与 04 一致；新增端点随 S3/S4/S8 验收（全量 44 个）。
- [ ] 开桌失败（如模板不存在）时 mj_room 无半条记录。
- [ ] 结算失败时 game_round 与 totalScore 不半更新（事务回滚验证）。
- [ ] 历史列表 SQL 次数为常数（开 general_log 或 SQL 计数断言）。
- [ ] 聊天查询带 LIMIT；历史接口默认 30、最大 100。
- [ ] 进程重启后 mj_game 的 PLAYING 全变 ABORTED。
- [ ] 76 个引擎用例全绿（若字段改名，断言同步改）。

## 硬约束
- 业务层禁止裸 SQL；所有条件参数化。
- 一个业务动作一个事务；跨表写入必须原子。
- 异步路径不得直接触库（run_in_threadpool）。
- 不改协议形状（除 04 已定义的字段变更）。
- 分批提交，每批可单独回滚。

## 完成后必须输出
1. 分批改动清单（端点 → processor → query 函数）。
2. 验收结果（含 SQL 次数与事务回滚证据）。
3. 遗留问题（仍用内存态的部分、慢查询）。
````

---

## S5b · 观战跟随与围观上限

> **什么时候做**：S5 通过后。纯实时层与前端改动，不新增表、不改 02。

````text
【家庭麻将 · S5b · 观战跟随与围观上限】

## 目标
四座满后进入观战：每个观战者同一时刻只跟随 1 名在座玩家，每名在座玩家最多被 10 名观战者跟随；观战快照只给目标手牌明文，观战者不能操作；观战关系只存 RoomActor 内存，不落库。

## 前置
S5 通过（实时写库已走 mysqlCommon）；本步无数据库变更。

## 必须先读
- plan/家庭麻将总体规划文档.md §3、§4.3 G13、§9 D17、§12
- plan/01-系统架构设计.md §4.2、§9、§11
- plan/04-协议设计.md §6、§9.1、§9.3–§9.5、§10、§12
- plan/05-UI设计.md §4.3、§4.5
- 现有代码：realtime/room.py、main/ws.py、realtime/snapshot.py、stores/game.ts、RoomView.vue、SeatBox.vue、ActionBar.vue

## 任务
1. 房态：RoomActor 增 spectators: dict[loginID, SpectateBinding]（targetLoginID/targetSeat/reserveUntil）与按当前座位派生的围观计数；绑定以 targetLoginID 为准，抽座后重算 targetSeat，不跟错人。
2. 消息：main/ws.py 处理 spectate.target（{seat} / {seat:null}）——在 asyncio.Lock 内校验：在座玩家不可观战（SPECTATE_NOT_ALLOWED）、目标座位无人（SPECTATE_TARGET_INVALID）、目标已满 10 人（SPECTATE_TARGET_FULL，保持原绑定）；成功时先释放旧目标名额再占用新目标；同目标重复提交幂等。
3. 快照：state.snapshot 增 spectate 与 seats[].spectator_count；hand/drawn/tenpai 只对 self_seat 或 spectate.target_seat 填充，其余只给 hand_count；观战者 self_seat=null、legal.actions=[]，drawn 为目标的摸牌。
4. 事件：event.spectate_changed{target_login_id,target_seat,viewer_count,seat_viewer_counts} 广播全房，不含观战者身份；观战者本人切换后补发 state.snapshot，不增量回放历史。
5. 握手：4 座满且观战位 4×10 满 → error{ROOM_SPECTATE_FULL} + close(4005)；满座但仍有名额仍返回 ROOM_FULL（非致命）。
6. 生命周期：观战连接全断后绑定保留 60 秒（SPECTATE_RESERVE_SECONDS），超时释放并广播；目标离座/座位回收/房间关闭立即清空该目标的观战者并广播 target_seat=null；同一 loginID 多标签页只占 1 个名额。
7. 配置：config/basicSettings.py 读 SPECTATE_LIMIT_PER_SEAT=10 / SPECTATE_ROOM_MAX=40 / SPECTATE_RESERVE_SECONDS=60，非法值回退默认；同步写进 .env.example。
8. 前端：stores/game.ts 增 spectate 与 spectateSeat(seat|null)；新建 SpectatePanel.vue（4 张座位卡、围观 x/10、满员置灰、未选提示）；RoomView 增顶部横幅与切换入口；SeatBox 显示围观人数；观战者不渲染 HandTiles/ActionBar，改为「切换观战对象 / 取消跟随」；移动端横幅不遮挡牌河。
9. 大厅：room_join_check.spectate 用于满座提示与 available=false 时禁用进入。
10. 不做：观战名单、观战历史、观战落库、观战者禁言或额外聊天权限。

## 验收清单
- [ ] 四座满后第 5 人进入观战：未选目标 hand=[]、spectate=null；选择座位 2 后只有座位 2 的 hand 明文。
- [ ] 同一观战者连续切换 3 次，旧目标 spectator_count -1、新目标 +1，全房总数守恒。
- [ ] 目标已有 10 人时第 11 人返回 SPECTATE_TARGET_FULL，且其原绑定不变。
- [ ] 4×10 满后第 45 个连接握手返回 ROOM_SPECTATE_FULL(4005)。
- [ ] 同一账号 3 个标签页只占 1 个名额；断线 60 秒内重连恢复原目标且不重复占位。
- [ ] 目标离座 / 房间关闭：观战者收到 event.spectate_changed{target_seat:null}，回到未选择态，计数归零。
- [ ] 抽座换座后观战者仍跟随同一 loginID。
- [ ] 观战者发 seat.ready/game.start/game.action 返回 NO_SEAT；观战快照 legal.actions=[]。
- [ ] 375px 可完成选目标与切换；横幅不遮挡牌河与聊天按钮。
- [ ] grep -rn "mj_spectator" code/backend 无命中；02 表数仍为 14 张 mj_*；pytest 全绿（新增观战用例）。

## 硬约束
- 观战关系不落库、不新增表、不改 02；进程重启房态清空即可。
- 上限按 loginID 计数，不按连接数；切换与名额释放必须在同一把锁内完成。
- 观战快照不得出现目标以外任何人的手牌，不得下发牌墙。
- 不改对局规则、结算与既有 WS 事件形状，只做增量字段。
- 观战者不能准备/开局/出牌/吃碰杠胡/暂停；聊天保持可用。

## 完成后必须输出
1. 文件清单（后端 room/ws/snapshot/config、前端 store 与组件）。
2. 验收结果（并发选目标、第 11 人、4×10 满、切换计数、抽座跟随的证据）。
3. 遗留问题（观战者音效策略、被围观人数展示位置等）。
````

---

## S6 · 规则族：通用族等价迁移

> **什么时候做**：S5b 通过后。先保证 generic 与现状逐字节等价，再谈新族。

````text
【家庭麻将 · S6 · 规则族：通用族等价迁移】

## 目标
把现有单一 RuleConfig 拆成"通用骨架 + families/generic 插件"，行为与现状一致；4 套预置模板与 76 个用例全部平移。

## 前置
S5b 通过；现状 76 用例在 SQLite 下全绿（作为对照基线）。

## 必须先读
- plan/03-规则族设计.md §1–§4（含 §3.4 座位/庄家/局风、§3.5 发牌、§3.6 荒庄）、§9–§11
- 现有代码：app/schemas/rule.py、app/game/engine.py、app/game/patterns/*、app/game/fan.py、app/game/scoring.py、app/seeds/presets.py

## 任务
1. 新建 game/families/registry.py：ruleFamilyCode → EngineFactory；导入期自检 capability（patterns 已注册、tile_set 可建墙）。
2. 新建 game/families/generic/{engine.py,config.py,presets.py}：
   - config.py 保留 20 番种、四牌型、三组开关、结算字段（JSON 键 snake_case）
   - patterns 迁入 generic/patterns/
   - presets.py 复刻 4 套预置模板配置
3. processor/ruleService.py：按族能力校验（字段级 + 跨字段 + 白名单），未知字段 400；生成规则快照。
4. 模板接口改 family_code/rule_family_code；预置模板只读；复制到家庭。
5. 开桌时把 template → snapshot 写入 mj_room；开局再写 mj_game；两者不可变。
6. 迁移测试：76 用例改为从 registry 取 generic 引擎，断言与基线一致。
7. 通用骨架补对局流程（03 §3.4–3.6）：
   - 抽座：每场首局掷 2 骰定东位/庄家并广播 event.seats_drawn；整场不重抽（v1.1.0 换圈亦不重抽）
   - 轮庄与局风：第 n 局庄家 = 座位 n-1，局风随之 东南西北
   - 发牌：每人 4 张 × 3 轮 = 12 张，庄家跳牌取第 1、第 5 张（14 张），闲家 13 张，首轮庄家直接出牌
   - 荒庄：牌墙取尽无胡时，有杠 → 记荒庄、迁庄、计局；无杠 → 重发本局、不计数
8. 移除模板中的 dealer_continue_on_win/draw（加载时忽略并记 warning）。

## 验收清单
- [ ] 76 用例全绿，且没有放宽断言。
- [ ] 4 套预置模板与现状配置逐字段一致（写脚本对比旧 config 与新 config）。
- [ ] 番表互斥组取最高、封顶、线性/指数折算结果与基线一致。
- [ ] 关闭 kongScore 后仍可杠且分差 0；关闭 tingHint 后快照无 tenpai。
- [ ] 模板保存后开桌，修改模板不影响该房间快照。
- [ ] capability 缺字段/未知字段被 400 拒绝。
- [ ] 发牌：庄家 14、闲家各 13；跳牌取第 1、5 张；首轮庄家直接出牌。
- [ ] 抽座与轮庄：每圈抽一次；第 n 局庄家 = 座位 n-1，局风 东南西北；北位（座位 3）庄家下庄即圈结束（最少 4 局）。
- [ ] 荒庄二分：有杠落库并迁庄计局；无杠重发不落库、局号与局风不变。

## 硬约束
- generic 行为不得改变（番值、优先级、结算公式）。
- 规则 JSON 键 snake_case；DB 列名不变。
- 引擎不触库、不读环境变量。
- 快照只增字段不删字段。

## 完成后必须输出
1. 文件清单与迁移对照表（旧函数 → 新位置）。
2. 验收结果（用例数、对比脚本输出）。
3. 遗留问题（尚未族化的共享逻辑）。
````

---

## S7 · 规则族：广东/四川/柏氏

> **什么时候做**：S6 通过后。柏氏细则已冻结于 07，本步按 07 实现到"可开桌、可结算"。

````text
【家庭麻将 · S7 · 规则族：广东/四川/柏氏】

## 目标
新增 guangdong、sichuan、baishi 三族：广东复用通用引擎 + 广东番表；四川实现 108 张、禁吃、缺一门、多赢家；柏氏按 07 实现番表（v1.9 为 34 项）、倍数结算、包牌与暂停，验收通过前不可开桌。

## 前置
S6 通过；07 细则已冻结（无待确认项），本步照 07 落 presets 与 engine。

## 必须先读
- plan/03-规则族设计.md §5–§8
- plan/02-数据库设计.md 的 mj_rule_family / mj_rule_template
- plan/05-UI设计.md §4.4（规则页按 capability 渲染）

## 任务
1. guangdong：config.py（番表 12 项、封顶 4/6/8/10/不封顶）、presets.py（默认模板）；capability 去掉 thirteen_unrelated。
2. sichuan：
   - tiles：108 张牌墙（0–26），拒绝 27–33
   - config：lack_suit_required、multi_winner、kong_score、min_fan_to_win
   - engine：缺一门校验、胡牌后退出、继续到 3 人胡或牌墙尽、多赢家 settlement
   - scoring：刮风/下雨杠分、查叫/花猪开关（默认关）
3. baishi（按 07 实现）：
   - 注册族 + capability（`fan_combine=sum_all`、`fan_cap_allowed=false`、`min_fan_to_win=1`、`self_draw_multiplier=2`、`dealer_multiplier{win:2,pay:2}`、`bao_pai` 对象、`switches` 含 `pause`）
   - 番表：07 §5 全部番种（互斥组 `structure`/`anke`/`long`/`flush`/`quan`/`first`，缺门抑制；风刻、箭刻、将牌、258赢、断幺不占组）
   - engine：累计求番、倍数结算、包牌 `payerAllocation`（点炮 + ≥3 明牌 + 四种牌型 + 牌型花色集）、杠分（1/2/1 三家付）、抢杠（仅明杠开窗口，补杠/暗杠不开）、牌尾补牌与海底判定
   - 暂停：房态 `paused`，`room.pause`/`room.resume`
   - ready 由自检结果决定：未通过 07 §13 用例前 `ready=false`
4. seedPresets.py 增加三族预置（柏氏 1 条：07 §5 番表 + 包牌/倍数/杠分配置，`presetFlag='1'`）。
5. 前端规则页按族 capability 渲染；柏氏 `ready=false` 时显示"引擎未就绪"并禁用开桌。

## 验收清单
- [ ] 4 族全部可列出，capability 可解析，patterns 均已注册。
- [ ] 广东建墙 136 张；模板可保存、可开桌。
- [ ] 四川建墙 108 张；出牌含字牌被拒；不能吃；未缺一门不能胡。
- [ ] 四川一局 2 个赢家：winners 长度 2，sum(score_delta)==0。
- [ ] 柏氏引擎验收前开桌返回 RULE_FAMILY_NOT_READY；验收后按 07 §13 全部用例（30 条 + 16b/16c）全绿。
- [ ] 规则页不显示族不支持的开关。
- [ ] 三族各至少 3 个用例（发牌、牌型/限制、结算守恒）。
- [ ] 抢杠：明杠被抢一次（杠作废、10 番、三家各付、无包牌）；补杠与暗杠无抢杠窗口。

## 硬约束
- 不臆造柏氏番种/包牌算法；番值、倍数、包牌条件一律以 07 为准。
- 不得用通用番表冒充柏氏。
- 四川多赢家不得破坏单赢家族的事件协议。
- 族差异只通过 capability 与 engine 插件表达，不在路由里 if/else 族名。

## 完成后必须输出
1. 文件清单（每族 engine/config/presets）。
2. 验收结果（用例列表与结果）。
3. 遗留问题（广东地方玩法、四川查叫/花猪）。
````

---

## S8 · 皮肤系统后端

> **什么时候做**：S7 通过后（也可与 S7 并行，但需 S5 完成）。

````text
【家庭麻将 · S8 · 皮肤系统后端】

## 目标
实现皮肤主档/资源表、上传与发布接口、本地存储与静态托管，提供带 ETag 的家庭皮肤清单。

## 前置
S5 通过；mj_tile_skin / mj_tile_skin_asset 已建表；`code/backend/data/webserver/majiangapp/tiles/` 可写。

## 必须先读
- plan/04-协议设计.md §8
- plan/05-UI设计.md §6（35 个 tile_key、尺寸、格式、状态）
- plan/01-系统架构设计.md §10（文件存储与静态托管）

## 任务
1. processor/skinService.py：
   - createSkin / listSkins(familyID, ETag) / getSkin
   - uploadAsset（magic number + 扩展名 + ≤512KB + 尺寸校验；哈希命名；写 mj_tile_skin_asset）
   - deleteAsset / publish（校验 34+back 齐全）/ setDefault（同家庭唯一，事务）/ disable / softDelete
   - 清单组装：assets map、preview_url、fallback=css-classic
2. main/api/skins.py：6 个端点（04 §8），multipart 上传，管理员校验。
3. main/app.py：把 `data/webserver` 挂到 `/majiangapp`（StaticFiles）+ 长缓存头；目录不存在时自动创建。
4. 校验：只允许 png/webp；拒绝 svg；tile_key 必须在白名单。
5. 审计：SKIN_CREATE/SKIN_UPLOAD/SKIN_PUBLISH/SKIN_DEFAULT/SKIN_DELETE。
6. 种子：css-classic（无资源，ENABLED，default）。

## 验收清单
- [ ] 上传 35 张 → publish 成功；缺 1 张 → SKIN_ASSET_INCOMPLETE 并列出键。
- [ ] 非 png/webp → UPLOAD_BAD_TYPE；>512KB → UPLOAD_TOO_LARGE。
- [ ] 非管理员上传 → 403 NOT_FAMILY_ADMIN。
- [ ] 家庭 A 的清单不含家庭 B 自定义皮肤；全局皮肤两者都可见。
- [ ] 设置默认后同家庭仅一个 default。
- [ ] `/majiangapp/tiles/...` 返回 Cache-Control immutable；/api/skins 带 ETag，304 生效。
- [ ] 软删后清单不再返回，但文件仍在（延迟清理）。
- [ ] 审计表有记录。

## 硬约束
- 文件名完全由服务端生成，不接受用户路径/文件名。
- 拒绝 SVG（脚本注入风险）。
- 上传目录固定在 `code/backend/data/webserver/majiangapp/tiles/`（生产 `/data/webserver/majiangapp/tiles/`）；只经 `/majiangapp/tiles/` 暴露。
- 单皮肤总容量 ≤ 8 MB。

## 完成后必须输出
1. 文件清单。
2. 验收结果（上传/发布/清单/304 的实测输出）。
3. 遗留问题（缩略图生成、物理清理脚本）。
````

---

## S9 · 音效模块（前端 SFX）

> **什么时候做**：S8 通过后、S10 之前。纯前端，可与皮肤前端并行。

````text
【家庭麻将 · S9 · 音效模块（前端 SFX）】

## 目标
按 plan/08-音效设计.md 落地「只有 SFX、没有 BGM」的音效模块：事件映射、优先级混音、限流去重、静音降级、用户开关与音量持久化。

## 前置
S4 通过（/api/user/pref 可用）；S8 通过；WS 事件契约稳定（04 §9.4）。

## 必须先读
- plan/08-音效设计.md 全文（权威）
- plan/04-协议设计.md §4、§9.4
- plan/05-UI设计.md §4.5、§5
- 现有前端：src/stores/game.ts、src/components/table/ScoreBoard.vue、src/api/http.ts

## 任务
A. 资源
1. public/audio/sfx/ 落 15 个 mp3：hu、exhausted、kong_exposed、kong_hidden、kong_added、claim、pong、chow、turn、discard、draw、timeout、dice、deal、chat；规格按 08 §6（单声道 44.1kHz、单文件 ≤40KB、峰值 ≤-1dBFS）。允许先用占位合成音，但文件名不得改。
2. public/audio/sfx/LICENSE.md 记录每个文件来源与许可（自制/CC0），禁止版权素材。

B. 播放内核
3. src/audio/soundKeys.ts：键 → 文件、基础音量、优先级（P0–P4）、是否受 chatSoundFlag 控制。
4. src/audio/audioManager.ts：AudioContext 单例；首次用户手势解锁；进桌预加载（Promise.allSettled）；GainNode 主增益；同键 150ms 去重；最多 4 并发，超出丢最低优先级；P0 播放后 200ms 丢 P3/P4；重连/恢复可见 800ms 静音期；visibilitychange suspend/resume；HTMLAudio 回退；失败键标记 unavailable 并 console.debug。
5. 不引入第三方音频库（howler 等），只用浏览器原生 API。

C. 事件接线
6. src/audio/useGameSounds.ts：在 stores/game.ts 的 handleEvent/handleMessage 中按 08 §2 映射播放；state.snapshot、room.welcome、pong、error、ready_changed、paused、game_finished 不发声。
7. 自己操作不预播放，统一等服务器事件；event.settled 一局只播一次（多赢家不叠加）；is_draw=true 播 exhausted 不播 hu。
8. event.drawn 自己 100%、他人 40% 增益；event.claim_open 仅当 seats 含 self_seat 才播。

D. 设置
9. ScoreBoard 增加「音效」按钮 + popover：总开关、音量 0–100（步进 5）、试听（discard）、聊天提示子开关；未解锁时按钮显示「♪」角标；无 BGM 开关。
10. 偏好：GET/PUT /api/user/pref 消费 sound_enabled、sound_volume、chat_sound；localStorage 先读后覆盖；写请求 500ms 防抖，失败回滚并 toast。
11. 默认开启、音量 70；关闭后不创建音源、不再请求音频。

## 验收清单
- [ ] 四人同房：A 出牌四人各响一次，A 不重复；关闭 A 的音效不影响他人。
- [ ] 自己摸牌正常音量，他人摸牌约 40%；吃/碰/明杠/暗杠/补杠/胡/荒庄/发牌/骰子/超时/询问/轮到/聊天均命中。
- [ ] 胡牌后 200ms 内 P3/P4 被抑制；同键 150ms 去重；一局多赢家只播一次 hu。
- [ ] 荒庄只播 exhausted；无杠重发播 deal，不播 hu。
- [ ] 断线重连不补播，无爆音；切后台暂停、回前台不补播、不重叠。
- [ ] 关闭音效后全场静音，刷新/重登/换标签页后仍关闭；音量三档可辨并持久化。
- [ ] 删除任一 mp3：仅该音效静音，其余正常，控制台无 error，对局可打完。
- [ ] 375px 可操作音效弹层，不遮挡操作栏。
- [ ] Network 面板无 BGM/音频流请求；仅进桌时 15 个 SFX 且可缓存。
- [ ] `npm run build` 无 TS 错误。

## 硬约束
- 只有 SFX，不做 BGM、语音播报、自定义音效包、服务端混音。
- 不改 WS 协议形状；除 pref 两字段外不改后端。
- 音频加载/解码/解锁失败必须静音降级，不得抛未捕获错误或阻塞对局。
- 关键信息不得只靠声音表达。

## 完成后必须输出
1. 改动文件清单（按 A/B/C/D 分组）。
2. 验收结果（逐条证据：事件、音量、Console、Network）。
3. 资源来源与授权清单；遗留问题（如 iOS 硬件静音键限制）。
````

## S10 · 前端适配、皮肤管理、联调部署

> **什么时候做**：S9 通过后。最后一步，覆盖前端、测试、部署与回滚演练。

````text
【家庭麻将 · S10 · 前端适配、皮肤管理、联调部署】

## 目标
前端适配账号/家庭/规则族/皮肤与登录字段变更；新增家庭页与皮肤管理页；完成联调、测试矩阵、部署与回滚演练。

## 前置
S9 通过；后端所有接口在测试库可用；前端能连本地后端。

## 必须先读
- plan/04-协议设计.md 全文
- plan/05-UI设计.md §3–§7
- plan/08-音效设计.md §8（音效验收）
- plan/06-实施计划.md §8
- 现有前端：src/api/*、src/stores/*、src/views/*、src/components/table/Tile.vue、tailwind.config.js

## 任务
A. 基础适配
1. api/http.ts：BASE 不变；401 逻辑保留；错误取 detail/code。
2. stores/auth.ts：login(login_id, passwd)、families、currentFamily、switchFamily、pref。
3. stores/families.ts、stores/skins.ts 新增。
4. 路由：/families、/admin/skins、/admin/skins/:skinCode；守卫 requiresFamily/requiresAdmin。
5. 全部视图字段改 login_id/family_code/rule_family_code 等。

B. 页面
6. FamilyView：列表/创建/切换；空状态。
7. LobbyView：6 位数字输入（inputmode=numeric、自动跳格、粘贴处理）、家庭筛选、创建桌按族选模板。
8. RulesView/RuleForm：按 capability 渲染；柏氏 `ready=false` 时显示"引擎未就绪"。
9. RoomView：ScoreBoard 增加家庭徽标与皮肤切换；其余交互不变。
10. SkinsView/SkinEditView：35 格上传、进度、发布、设默认、预览。
11. AppHeader：家庭切换器 + 移动端菜单。

C. 牌面
12. utils/tile.ts 增加 tileKey(tile)（1m/1p/1s/east…white）。
13. Tile.vue：图片优先，onerror 回退 CSS；faceDown 用 back；保留 selected/highlight/dim；首屏 eager，其余 lazy。
14. 皮肤切换即时生效，不刷新牌桌。

D. 测试与部署
15. 手工清单：1440/1024/768/375 各完成登录→选家庭→开桌→出牌→碰→胡→聊天→音效开关/调音量；满座时完成一次「选择观战对象→切换→取消」。
16. 后端 pytest 全量（引擎/接口/隔离/皮肤/邀请码）；前端构建无 TS 错误。
17. 部署：MySQL 建库、initTables --seed、bootstrapFamily、npm build、systemd、Nginx `/majiangapp/tiles/`、WSS。
18. 回滚演练：代码回退 + 备份恢复 + 皮肤功能开关。

## 验收清单
- [ ] 登录字段改为 login_id 后全流程可用；旧 username 别名仍可登录。
- [ ] 家庭切换后，大厅/规则/战绩/皮肤数据随之切换，无缓存串数据。
- [ ] 邀请码只能输入数字，粘贴非法字符被过滤，满 6 位自动查询。
- [ ] 规则页不显示族不支持的开关；柏氏 `ready=false` 时模板不可保存。
- [ ] 切换皮肤后 34 张牌 + 牌背全部命中；删一张后该张回退 CSS，无控制台异常。
- [ ] 音效与皮肤互不影响：切皮肤不改音效设置，关音效不改牌面；全程无 BGM 请求。
- [ ] 375px 宽度可完成一次出牌与一次碰牌，操作栏不被遮挡。
- [ ] 跨家庭接口全部 403，前端有明确提示。
- [ ] pytest 全绿；npm run build 成功。
- [ ] HTTPS 下 WSS 连接正常；`/majiangapp/tiles/` 长缓存；备份恢复演练成功。
- [ ] 回滚演练：旧版本代码 + 现有库可启动（无破坏性 DDL）。

## 硬约束
- 不改协议形状；只按 04 的字段消费。
- 图片缺失必须回退，不允许空白牌或整桌报错。
- 不在前端硬编码家庭/皮肤列表。
- 移动端手牌不缩小到 <32px，只滚动。
- 部署前必须做一次备份与恢复演练。

## 完成后必须输出
1. 改动文件清单（按 A/B/C/D 分组）。
2. 验收结果（手工矩阵 + 自动化结果 + 部署与回滚证据）。
3. 遗留问题与后续建议（性能、可访问性、未实现玩法）。
````

## 附录 A · 步骤与阶段对照

| 步骤 | 阶段 | 交付 |
| --- | --- | --- |
| S0 | P0 | 文档冻结 |
| S1 | P1 | code/ 骨架 |
| S2 | P2 | 表定义与生成链路 |
| S3 | P3a | 账号与 JWT |
| S4 | P3b | 家庭与隔离 |
| S5 | P4 | 数据层无 ORM |
| S5b | P4b | 观战跟随与围观上限 |
| S6 | P5a | 通用族等价 |
| S7 | P5b | 广东/四川/柏氏 |
| S8 | P6a | 皮肤后端 |
| S9 | P6b | 音效前端 |
| S10 | P7 | 前端、联调、部署 |
| I0–I8 | P8 | v1.1.0 运行反馈修复（见 [improve step-prompts.md](improve%20step-prompts.md)） |

> 附录 A 的 S0–S10 均已完成并上线（2026-10-29）；v1.1.0 的修复步骤不在本文，统一见 [improve step-prompts.md](improve%20step-prompts.md)。

## 附录 B · 每步固定输出格式

```text
## 改动文件
- path: 说明

## 验收结果
- [x] 条目 —— 命令/证据
- [ ] 未通过条目 —— 原因

## 遗留问题
- 问题 / 影响 / 建议下一步
```

## 附录 C · 待办与已知遗留

| 项 | 状态 |
| --- | --- |
| 柏氏规则细则 | 已冻结于 plan/07（v1.9，34 项番表、倍数、包牌、风刻、荒庄二分） |
| 广东地方玩法（马/鬼/杠爆） | 未纳入首期 |
| 四川查叫/花猪细则 | 仅开关与钩子，默认关 |
| 缩略图生成 | 可选，首期直接使用原图 |
| 皮肤物理清理脚本 | 待补 |
| 前端单元测试 | 本轮不引入，靠手工矩阵 |
| 观战名单 / 观战历史 | 不做：观战关系只存内存，仅展示每座围观人数，不展示谁在看谁 |

---
name: mobile-compat-chrome87-viewport-lock
overview: 手机版兼容基线从 Chrome 78 收敛到 Chrome 87，清理随之失效的老内核兜底；入口 HTML 改 no-cache 消除旧入口引用已删资源导致的白屏；视口高度改为一次性锁定（--mj-vh），消除地址栏与 HTTP 提示条收放引起的整页重排。鸿蒙「整页反复重载」判定为 HTTP 触发的浏览器 HTTPS 优先/回退循环，不改代码，只做验证与记录。
todos:
  - id: bump-target
    content: 手机版 build.target 收敛到 chrome87，删除 mobile.css 的 inset/gap 兜底并保留 100vh 回退
    status: completed
  - id: viewport-lock
    content: 新增 useViewportHeight 在 main.ts 挂载前写入 --mj-vh，CSS 接三级高度链
    status: completed
    dependencies:
      - bump-target
  - id: entry-no-cache
    content: 为两个入口 HTML 增加 no-cache 精确 location，并同步部署文档与自检命令
    status: completed
  - id: harmony-http-record
    content: 整理鸿蒙 http 整页重载的 https 复测步骤与已知限制，写入改进台账
    status: completed
  - id: verify-release
    content: 用 [skill:playwright-cli] 跑两入口与双视口冒烟、核验产物语法，统一版本号并写发布记录
    status: completed
    dependencies:
      - bump-target
      - viewport-lock
      - entry-no-cache
      - harmony-http-record
---

## 用户需求

移动端 `/mjmobile/` 目前为兼容 Chrome 78（2019）做了一整套降级与兜底，用户判断这批超老内核可以不再兼容；同时鸿蒙系统自带浏览器上出现显示异常，希望明确根因方向并给出处置建议。

## 产品概述

两件事，一件需改代码、一件只需结论与记录：

- 兼容基线收敛：手机版最低内核由 Chrome 78 提升到 Chrome 87，同步清掉已失效的样式兜底，减轻构建与维护负担。
- 鸿蒙问题定性：现象为「整页反复重载，整页白一下像刷新了一遍」，且发生在 http 地址、鸿蒙自带浏览器下。结论是浏览器侧的 HTTPS 优先/回退循环，代码内无对应逻辑、nginx 也无 80→443 跳转，因此不作为代码缺陷修复，改为 https 复测确认 + 文档记录为已知限制。

## 核心功能

1. 手机版构建目标由 `chrome78 + safari13 + firefox70 + edge79` 收敛到 `chrome87`，PC 构建目标保持不变。
2. 删除随基线提升而失效的两块老内核样式兜底（`inset` 简写、flex `gap`），保留必须保留的 `100vh` 高度回退与 `text-size-adjust`。
3. 新增视口高度锁定：一次性把可视高度写入 `--mj-vh`，仅在横竖屏切换与超过阈值的高度变化时重算，避免地址栏、HTTP 提示条收放引起整页重排跳动。
4. 入口 HTML 改为不缓存、静态资源继续长缓存，避免旧入口引用已清理的哈希资源导致整页白屏。
5. 鸿蒙「整页重载」给出可执行的复测步骤（同机用 https 域名访问对比）与发布记录说明，不改动横屏闸门、诊断面板、反色防护、UA 嗅探等假设性修复。

## 边界与不在范围内

- 不做 UA 判断，不新增诊断面板，不改 `LandscapeGate`/`useOrientation`，不加反色/强制深色相关样式。
- 不引入 `@vitejs/plugin-legacy` 或任何 polyfill 依赖。
- 桌面版 `index.html`、PC 产物与后端代码逻辑保持不变（仅版本号同步）。

## 一、结论先行（回答"UA 问题还是什么"）

- `src/**` 全链路无 `navigator.userAgent` 分支；`useOrientation.ts:31-35`、`LandscapeGate.vue:19` 均基于 `matchMedia`/`innerWidth`，与 UA 无关。
- 代码内唯一整页跳转是 `src/stores/game.ts:367-370`（token 失效 1.2s 后跳登录），与"反复重载"无关；`src/api/ws.ts:26-29` 按 `location.protocol` 选 `ws:`/`wss:`，http 下合法。
- `code/deploy/nginx-majiang.conf` 只有 API/WS/静态与 SPA 回退，**没有** 80→443 的 301/302。因此"整页白一下再重画"来自鸿蒙自带浏览器的 HTTPS 优先升级失败回退循环。
- 处置：同机改用 https（生产 `www.iottest.online` 有正式证书）复测；测试端 `192.168.100.100` 为 http，记为已知限制，回归时不再当代码 bug 排查。

## 二、技术栈（沿用现有，不新增依赖）

- 构建：Vite 5.4 + esbuild，只改 `build.target`；不引入 `@vitejs/plugin-legacy`（会带 core-js，家庭设备可控，不值得）。
- 样式：Tailwind 3.4 + `mobile.css` 增量覆盖；autoprefixer 默认 browserslist 已够。
- 运行时：新增一个纯 TS composable 写 CSS 变量，无第三方依赖。
- 部署：nginx 静态托管（`/data/webserver/majiangapp`、`/data/webserver/mjmobile`），沿用 `code/deploy/nginx-majiang.conf` 片段与 `~/mj_deploy2/18_front_only.sh`。

### 能删 / 必须留的精确清单（已核实）

| 项 | 位置 | 依据 | 处置 |
| --- | --- | --- | --- |
| `?.`/`??` 语法降级 | `vite.config.ts:41-46` | Chrome 80+ 原生支持 | 删除（target→87） |
| `@supports not (inset: 0)` | `mobile.css:26-34` | `inset` 简写 Chrome 87+ | 删除（87 正好支持） |
| `@supports not (gap: 1px)` | `mobile.css:35-51` | flex gap Chrome 84+ | 删除；`MobileHand.vue:78` 用 `gap-[3px]`，`.mj-meld-row/.mj-btn-row` 仅在此块出现（死规则） |
| `.mj-app/.mj-dvh` 的 `100vh` 回退 | `mobile.css:80-87` | `dvh` 是 Chrome 108+ | **必须保留** |
| `-webkit-text-size-adjust:100%` | `mobile.css:55-59` | 防字体自动放大，与内核无关 | **必须保留** |


## 三、实施策略

### 1. 构建目标收敛

`vite.config.ts` 改 `target: mobile ? ['chrome87'] : undefined`，注释改写为"手机版按 Chrome 87 基线；PC 仍走 Vite 默认"，删除 chrome78/Android 12 预装 Chrome 的说明。PC 分支保持 `undefined`，确保桌面产物零变化。

### 2. 视口高度锁定（核心新增）

新增 `src/mobile/composables/useViewportHeight.ts`，导出 `installViewportHeight(): () => void`，在 `main.ts` 的 `createApp(...).mount('#app')` **之前**调用（首帧即生效，避免先按 100vh 排版后再跳一次）：

- 取值优先级：`window.visualViewport?.height` → `window.innerHeight`；写 `document.documentElement.style.setProperty('--mj-vh', h + 'px')`。
- 重算时机：`orientationchange` 与 `screen.orientation.change` 立即重算；`visualViewport` 的 `resize`/`window.resize` 走 250ms 防抖，且**高度差值 < 120px 时忽略**（过滤地址栏、http 提示条收放）。
- 键盘保护：当 `document.activeElement` 是 `input/textarea/select` 时跳过重算，避免输入时整页被压到键盘高度。
- 全部 try/catch 静默降级；无 `visualViewport` 时退回 `innerHeight`；SSR/不支持场景直接返回空清理函数。
- 返回清理函数（移除监听、保留变量），便于将来切页复用。

`mobile.css` 接上变量，变量兜底必须是 `100vh`（不能写 `100dvh`，否则 chrome87 上第三条声明整体失效）：

```css
.mj-app  { min-height: 100vh; min-height: 100dvh; min-height: var(--mj-vh, 100vh); }
.mj-dvh  { height: 100vh; height: 100dvh; height: var(--mj-vh, 100vh); }
```

权衡（写入注释与文档）：锁定高度后，iOS 地址栏收起时底部可能留白数px，换来的是整页不再随地址栏/提示条抖动；`src/styles/index.css:15-19` 已有 `html, body, #app { height:100% }`，高度链无需再加。

### 3. 入口 no-cache

`code/deploy/nginx-majiang.conf` 新增两个精确匹配（精确匹配优先于前缀 location，`try_files` 内部重定向同样命中）：

```
location = /mjmobile/mobile.html  { root /data/webserver; add_header Cache-Control "no-cache, must-revalidate"; }
location = /majiangapp/index.html { root /data/webserver; add_header Cache-Control "no-cache, must-revalidate"; }
```

`assets/`、`tileart/`、`audio/` 的长缓存段不动；改前备份 `majiang.conf_YYYYMMDD_HHMMSS.bak`，reload 失败即回滚。注意 `add_header` 在 location 级别会覆盖父级同名头，此处仅需该一个头，无影响。

### 4. 鸿蒙 http 的落点（不做代码修复）

- 交付内容是**复测步骤**：同机访问 `https://www.iottest.online/mjmobile/`，若不重载即确认；再访问 `http://192.168.100.100/mjmobile/` 对照。
- 文档记录为已知限制：http 下鸿蒙自带浏览器可能反复升级/回退导致整页重载；如需消除，只能给该地址配域名 + 有效证书（自签证书会触发安全警告页，不建议）。
- 发布记录中显式标注"非代码缺陷"，避免下次回归重复排查。

### 5. 验收

- `npm run typecheck`、`npm run build`、`npm run build:mobile` 全绿。
- 产物核验：`dist-mobile/assets/mobile-*.js` 中 `?.`/`??` 保持原样（未降级为三元）；`dist/` 与改动前相比仅 hash 变化、体积基本持平。
- 冒烟：复用 `plan/tools/smoke_v114.py`（本地静态 + 假 REST/WS，接 `dist`/`dist-mobile`）跑两入口；再用 `[skill:playwright-cli]` 以 375×667、667×375 两个视口验证 `--mj-vh` 已写入 `documentElement.style`、`.mj-dvh` 计算高度等于视口高度、桌面版截图无差异。
- 版本与文档：`package.json`、`LoginView.vue:17`、`MobileLoginView.vue:17`、`code/backend/src/config/basicSettings.py:21` 四处同步 1.1.6；新建发布记录；`plan/android家庭麻将客户端规划.md:195/204` 的 WebView 下限 78→87。

## 四、实施要点

- **爆炸半径**：只动手机版入口链路（`vite.config.ts` 手机分支、`mobile.css`、`mobile/main.ts`）；`src/styles/index.css`、`index.html`、桌面组件、后端逻辑均不改。
- **不可回退的错误**：删 `100vh` 那行会让 chrome87 内核（不支持 dvh）整页高度为 0；`var(--mj-vh, 100vh)` 的兜底写 `100dvh` 同理会失效。
- **性能**：高度重算为 O(1) 且带阈值 + 防抖，正常对局无额外重排；不新增网络请求、不新增 DOM。
- **风险与回滚**：仅前端；nginx 片段回滚后 `nginx -s reload`；前端用 `majiangapp_*.tgz` / `mjmobile_*.tgz` 回滚。发版前查 `OPEN/PLAYING`，本次不重启后端。
- **iOS 回归重点**：地址栏收起后底部留白是否可接受（可接受即按方案；若不可接受，改为仅在 `CSS.supports('height','100dvh')` 为假时才写 `--mj-vh`）。

## 五、目录结构

```
majiang/
├── code/frontend/
│   ├── vite.config.ts                        # [MODIFY] 手机 build.target → ['chrome87']；重写注释；PC 分支保持 undefined
│   ├── package.json                          # [MODIFY] version → 1.1.6
│   └── src/mobile/
│       ├── main.ts                           # [MODIFY] mount 前调用 installViewportHeight()；保留现有序（音效、手势、样式导入）
│       ├── composables/useViewportHeight.ts  # [NEW] 视口高度锁定：visualViewport→innerHeight，写 --mj-vh；orientationchange 立即重算；resize 250ms 防抖 + 120px 阈值；输入聚焦时跳过；try/catch 静默；返回清理函数
│       └── styles/mobile.css                 # [MODIFY] 删除 26-51 行两块 @supports not 兜底；78-90 行改为 vh/dvh/var 三级链（兜底 100vh）；注释说明 dvh 仍需回退与锁定权衡
├── code/deploy/
│   └── nginx-majiang.conf                    # [MODIFY] 新增 /mjmobile/mobile.html 与 /majiangapp/index.html 两个精确 location，Cache-Control: no-cache, must-revalidate
├── code/backend/src/config/basicSettings.py  # [MODIFY] VERSION → 1.1.6（仅版本号，无逻辑变更）
├── code/frontend/src/views/LoginView.vue     # [MODIFY] version 初值 → 1.1.6
├── code/frontend/src/mobile/views/MobileLoginView.vue  # [MODIFY] version 初值 → 1.1.6
├── docs/部署.md                              # [MODIFY] §12 nginx 片段补两行 no-cache；"上线验证"补 curl 检查 Cache-Control
└── plan/
    ├── android家庭麻将客户端规划.md           # [MODIFY] WebView 可运行下限 78→87，风险表 UA 检测表述改为能力检测
    ├── 改进和错误修复文档.md                  # [MODIFY] 新增批次：兼容基线收敛 / 视口高度锁定 / 入口 no-cache / 鸿蒙 http 重载结论
    └── v1.1.6-发布记录.md                     # [NEW] 改动摘要、产物语法核验、冒烟证据、https 复测结论、回滚命令
```

## Agent Extensions

### Skill

- **playwright-cli**
- Purpose: 在本地静态服务（复用 `plan/tools/smoke_v114.py` 的孪生后端）上打开 `/majiangapp/` 与 `/mjmobile/`，用 375×667 与 667×375 视口核对 `--mj-vh` 是否写入、`.mj-dvh` 计算高度是否等于视口高度，并截图对比桌面版无视觉回归。
- Expected outcome: 产出手机竖/横屏与桌面截图、`--mj-vh` 取值快照，作为发版证据。
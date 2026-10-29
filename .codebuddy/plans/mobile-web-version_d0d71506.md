---
name: mobile-web-version
overview: 在现有 code/frontend 工程内新增移动端多入口，用第二套构建产出 base=/mjmobile/ 的产物，实现手机端的登录/注册/大厅/横屏牌桌/战绩核心闭环，与 PC 版 /majiangapp/ 并存部署到 www.iottest.online。
design:
  architecture:
    framework: vue
  styleKeywords:
    - 墨绿绒面
    - 哑金点缀
    - 玻璃拟态
    - 拇指优先
    - 沉浸横屏牌桌
    - 微动效触感
  fontSystem:
    fontFamily: Noto Sans SC
    heading:
      size: 22px
      weight: 600
    subheading:
      size: 14px
      weight: 500
    body:
      size: 13px
      weight: 400
  colorSystem:
    primary:
      - "#C9A063"
      - "#96682C"
      - "#2E7D5B"
    background:
      - "#071A12"
      - "#0A2419"
      - "#0F3D2E"
      - "#F7F3E8"
    text:
      - "#F7F3E8"
      - "#A8BFB4"
      - "#141C18"
    functional:
      - "#C0392B"
      - "#3B9E72"
      - "#E8A33D"
      - "#6C8EBF"
todos:
  - id: mobile-build-entry
    content: 改造 vite 双入口与双 base、新增 mobile.html 与 .env.mjmobile、抽出 router/guards.ts，搭好 src/mobile 入口外壳
    status: completed
  - id: mobile-ui-kit
    content: 编写 mobile.css 与通用组件：NavBar、TabBar、MobileSheet、DesktopOnlySheet、useOrientation、LandscapeGate
    status: completed
    dependencies:
      - mobile-build-entry
  - id: mobile-auth-family
    content: 实现移动端登录、注册、找回密码与家庭页（切换/新建家庭/成员入口转 PC 提示）
    status: completed
    dependencies:
      - mobile-ui-kit
  - id: mobile-lobby
    content: 实现移动大厅：统计头、家庭切换、进行中牌桌卡片、6 位邀请码入座、MobileCreateRoomSheet 建桌
    status: completed
    dependencies:
      - mobile-ui-kit
  - id: mobile-room
    content: 实现横屏牌桌：MobileRoomView 与 ScoreBoard/SeatChip/River/Hand，复用动作条/结算/观战/聊天，补 Tile 尺寸档与 game.ts 跳转修正
    status: completed
    dependencies:
      - mobile-ui-kit
  - id: mobile-history
    content: 实现移动战绩页：统计卡与走势、时间筛选、场次列表、详情抽屉含番种与终局手牌
    status: completed
    dependencies:
      - mobile-ui-kit
  - id: mobile-deploy
    content: 加 nginx /mjmobile 片段与 deploy-mobile.sh，跑通 typecheck 与两套构建，并用 [skill:playwright-cli] 以竖屏/横屏视口截图验收
    status: completed
    dependencies:
      - mobile-room
      - mobile-history
---

## 产品概述

在现有「家庭麻将」Web 端之外，新增一套**面向手机浏览器**的独立入口（同一后端、同一账号、同一份实时牌局），与 PC 版并存。PC 版继续用 `/majiangapp/`，手机版发布到 `/mjmobile/`。手机版不是 PC 页面的等比缩放：大厅/战绩/家庭是竖屏单列、拇指优先的流式布局，牌桌是把手机横过来、四方位沉浸式的真实牌桌。

## 核心功能

- **登录 / 注册 / 找回密码**：手机号 + 密码，竖屏单列表单，大输入框与大按钮，键盘弹出不遮挡提交按钮，顶部显示服务连通状态。
- **大厅**：当前家庭问候与累计积分/场次/胡牌数；家庭横向切换；本家庭进行中牌桌卡片列表（点开即进桌）；6 位数字邀请码输入（支持整串粘贴、输满自动进桌）；「创建牌桌」主操作（选规则族与模板、填桌名）；「规则模板」入口点击后提示改用电脑操作。
- **牌桌（核心，横屏）**：进入房间时提示横屏并尝试全屏 + 方向锁定，竖屏时显示「请横屏」遮罩。横屏下顶栏显示房间名、邀请码（可复制）、局风/局数、牌墙剩余、连接状态与「更多」（规则详情、切皮肤、音效设置、结束牌局、离桌）；对家在上、上家/下家分列左右，各自显示头像、昵称、分数、副露与手牌张数；中央牌河四方位排布并显示牌墙剩余，事件横幅（出牌/碰/杠/胡/超时）在牌河上方滑入；自己副露单独一行，手牌整排贴底可横向滑动、摸到的牌单独隔开、可听牌的张有金框；点牌只选中（抬起），按「打出」才出牌，避免误触；吃碰杠胡/过动作条贴底拇指区。等人阶段显示准备、房主限时选择与「开始牌局」；支持观战与被观战对象选择、非本家庭成员进桌申请与房主审批、牌桌聊天（底部抽屉）、单局结算（番种、分数构成、赢家手牌、终局四家手牌）、下一局、结束牌局与整场结算、断线重连提示。
- **战绩**：竖屏统计卡（累计积分、参与场次、最高单场、胡牌局数）与迷你积分走势；按全部/近 30 天/近 7 天筛选；场次列表显示房名、时间、四位家人分数与我的得分；点击从底部抽屉查看每局番种、分数变化与终局手牌；客队场次带「客队」标记。
- **家庭**：家庭卡列表（当前家庭高亮）、一键切换、创建家庭（名称、编码、默认规则族）；「成员管理」点击后提示改用电脑操作。

## 视觉与交互

沿用 PC 的墨绿绒面 + 哑金 + 米白牌面质感，但移动端「信息上收、操作下沉」：顶栏极简、底部固定操作区、触控目标不小于 44px，去掉悬停态依赖，全部改为按压反馈；页面切换轻位移淡入，抽屉从底部上滑，牌桌事件横幅顶部滑入。竖屏页面为单列流式（内容居中、最大宽度约 560px），牌桌为唯一横屏全屏场景。

## 技术栈

完全沿用 `code/frontend` 现有栈，不引入任何新依赖：Vue 3.5 + TypeScript + Vite 5.4 + Tailwind 3.4.17 + Pinia 2 + vue-router 4 + lucide-vue-next。移动端通过 **同一工程、第二入口 + 第二 mode** 产出 `dist-mobile`（base `/mjmobile/`），PC 构建行为保持不变。

## 实现方案

### 1. 双入口构建（不改 PC 产物）

- `vite.config.ts` 由 `({ command, mode })` 分支：
- `mobile = mode === 'mjmobile'`
- `base`：build 时 `mobile ? '/mjmobile/' : '/majiangapp/'`，dev 时 `'/'`
- `build.outDir`：`mobile ? 'dist-mobile' : 'dist'`
- `build.rollupOptions.input`：显式指定 `mobile.html` 或 `index.html`（避免两个 HTML 互相污染）
- 新增 `mobile.html`（`viewport` + `viewport-fit=cover` + `user-scalable=no`、`theme-color`、`apple-mobile-web-app-*`、入口 `/src/mobile/main.ts`）与 `.env.mjmobile`（`VITE_API_BASE=/majiangapi`、`VITE_WS_PATH=/majiangws`）。
- 新增脚本：`build:mobile`（`vue-tsc --noEmit && vite build --mode mjmobile`）、`dev:mobile`（`vite --open /mobile.html`，dev 下 base 为 `/`，走既有 `/api`、`/ws` 代理，无需额外 mode）。
- `tailwind.config.js` 的 `content` 追加 `./mobile.html`（`./src/**` 已覆盖 `src/mobile`）。

```ts
// vite.config.ts 关键分支（保持 PC 默认行为不变）
export default defineConfig(({ command, mode }) => {
  const mobile = mode === 'mjmobile'
  return {
    base: command === 'build' ? (mobile ? '/mjmobile/' : '/majiangapp/') : '/',
    build: {
      outDir: mobile ? 'dist-mobile' : 'dist',
      rollupOptions: { input: resolve(__dirname, mobile ? 'mobile.html' : 'index.html') }
    }
  }
})
```

### 2. 复用边界（单一真源）

- **直接复用、零改动**：`api/http.ts`、`api/ws.ts`、`stores/auth|families|game|skins`、`composables/useToast`、`audio/*`、`types.ts`、`utils/tile.ts`、`ToastHost.vue`、`table/Tile.vue`、`table/ActionBar.vue`、`table/SpectatePanel.vue`、`table/ResultModal.vue`、`table/TurnTimer.vue`、`ChatPanel.vue`、`Sparkline.vue`。数据流（WS 快照全量替换 + 增量事件播音效）完全不变；同域共享 `localStorage` 的 `mj_token`，PC 登录后手机自动登录。
- **向后兼容的加法式改动**（3 处小改）：

1. `Tile.vue` 的 `SIZES` 增加 `hand`（38×52）与 `micro`（20×27）两档，仅移动端引用，PC 不受影响；
2. `stores/game.ts` 中 401 兜底 `window.location.href = '/login'` 改为 `` `${import.meta.env.BASE_URL}login` ``（PC 下也是修正，移动端必需）；
3. 把 `router/index.ts` 的 `beforeEach/afterEach` 守卫抽到新文件 `router/guards.ts`（`installGuards(router)`），PC 路由与移动路由共用，避免白名单/`requiresFamily` 规则漂移。

- **新建**：`src/mobile/**` 全部移动端视图、组件、路由、样式。

### 3. 移动端外壳与技术要点

- `src/mobile/App.vue`：`router-view` + `ToastHost` + 页面过渡；登录态 watch（token → 会话/偏好/皮肤）与 `onUnauthorized` 处理复用 PC 的 `App.vue` 逻辑。
- 全局移动端 CSS（`styles/mobile.css`）：`height: 100dvh`（兼容 iOS 地址栏）、`env(safe-area-inset-*)` 内边距、`-webkit-tap-highlight-color: transparent`、`touch-action: manipulation`、`overscroll-behavior: none`、`input { font-size: 16px }`（防 iOS 聚焦缩放）；牌桌区域 `user-select: none`。
- `useOrientation.ts`：`matchMedia('(orientation: landscape)')` + `documentElement.requestFullscreen()` + `screen.orientation.lock('landscape')`（均 try/catch，iOS 不支持时靠遮罩文案兜底）。
- `MobileSheet.vue`：底部抽屉基座（遮罩点击关闭、`Esc` 关闭、打开时锁 body 滚动、安全区内边距），大厅建桌、战绩详情、牌桌更多/聊天/观战复用。
- 手牌尺寸自适应：`MobileHand` 依据容器宽度在 `md`(32×44)/`hand`(38×52)/`lg`(42×57) 间切档 + `overflow-x-auto` + 摸牌后自动滚到末尾；四家牌河用 `sm`/`micro` 小牌，控制单屏 Tile 数量 ≤ 约 110 个。

### 4. 牌桌布局（横屏）

`h-[100dvh]` 纵向三段：顶栏 `MobileScoreBoard`（≈40px）→ 主体 `grid-cols-[72px_1fr_72px]`（左右座位竖条 + 中央牌河，牌河内顶部叠对家条）→ 底部固定槽位（自己副露行 + `MobileHand` + 动作条）。动作条占独立槽位而不覆盖手牌，牌河 `flex-1` 自适应压缩；`ResultModal`/`SpectatePanel`/`ChatPanel`/`TurnTimer`/`ActionBar` 直接复用，统一挂 `z-index` 与安全区。观战者沿用 `relative` 四方位推导（`self/right/across/left`），与 PC 语义一致。

### 5. 部署（后端零改动）

- `code/deploy/nginx-majiang.conf` 追加：`/mjmobile/tileart/`（30 天缓存）、`/mjmobile/audio/sfx/`（30 天缓存）、`/mjmobile/`（`root /data/webserver; try_files $uri $uri/ /mjmobile/index.html;`）。复用既有 `/majiangapi/` 与 `/majiangws`，不动 `/majiangapp/`。
- 新增 `code/deploy/deploy-mobile.sh`：备份 `/data/webserver/mjmobile` 为 tar → `rsync -a --delete dist-mobile → /data/webserver/mjmobile` → `chmod -R a+rX` → 不重启后端；首次上线前需 `nginx -t && nginx -s reload`。
- 发布链：本机 `npm run build:mobile` → 打包 `dist-mobile` → scp 到 `~/mj_deploy2/` → `sudo bash deploy-mobile.sh` → `curl -fsS https://www.iottest.online/mjmobile/` 校验。

### 6. 性能与可靠性

- 路由级 `() => import()` 分包，页面级懒加载；`Tile` 图片保持 `loading="lazy"`，仅手牌 `eager`。
- 移动端剔除大面积 `backdrop-blur`（中低端 Android 掉帧），只在抽屉/顶栏 2–3 处保留。
- 首屏无新增依赖，包体增量仅为移动端视图 chunk；`/mjmobile/tileart/*.svg`、`/mjmobile/audio/sfx/*` 走独立缓存头。
- WS 重连、心跳、音效手势解锁、断线静音期等现有机制原样生效，不重复实现。

### 7. 执行注意

- `npm run build`（PC）与 `npm run typecheck` 必须仍通过，`dist` 路径与内容不变；提交前两个 build 都跑一遍。
- 不使用 hover-only 交互；所有可点区域 ≥ 44px；表单用 `inputmode`/`autocomplete` 提升手机输入体验。
- 牌桌相关浮层统一在一个 `z-index` 阶梯里（顶栏 40 / 动作条 50 / 抽屉 60 / 结算 70 / 竖屏遮罩 90）。
- 新文件注释与文案使用简体中文，风格与现有代码一致。

## 目录结构

```
code/frontend/
├── mobile.html                                   # [NEW] 移动端 HTML 入口：viewport-fit=cover、禁缩放、theme-color、apple-mobile-web-app 元信息，挂 /src/mobile/main.ts
├── .env.mjmobile                                 # [NEW] mobile 构建环境：VITE_API_BASE=/majiangapi、VITE_WS_PATH=/majiangws
├── vite.config.ts                                # [MODIFY] 按 mode 分支 base/outDir/rollupOptions.input，PC 行为不变
├── package.json                                  # [MODIFY] 新增 build:mobile、dev:mobile 脚本
├── tailwind.config.js                            # [MODIFY] content 增加 ./mobile.html
└── src/
    ├── router/
    │   ├── index.ts                              # [MODIFY] 守卫改为 installGuards(router)，路由表不变
    │   └── guards.ts                             # [NEW] 抽出登录/公开页/requiresFamily/requiresAdmin 守卫与标题设置，PC 与移动共用
    ├── stores/
    │   └── game.ts                               # [MODIFY] 401 跳转改用 import.meta.env.BASE_URL
    ├── components/table/
    │   └── Tile.vue                              # [MODIFY] SIZES 增加 hand(38×52)、micro(20×27) 两档（加法，PC 不用）
    └── mobile/
        ├── main.ts                               # [NEW] 移动端入口：initSoundPrefs、bindAudioGestures、pinia、mobile router、移动端样式
        ├── App.vue                               # [NEW] 移动端外壳：router-view + ToastHost + 过渡；复刻 PC 的 token/家庭 watch
        ├── router.ts                             # [NEW] 移动路由：login/register/forgot-password/families/lobby(/)/room/:code/history/兜底重定向，调用 installGuards
        ├── styles/mobile.css                     # [NEW] dvh、安全区、禁点击高亮/双击缩放、overscroll、16px 输入框、牌桌防选中
        ├── composables/useOrientation.ts         # [NEW] 横竖屏检测 + requestFullscreen/orientation.lock 尝试与降级
        ├── components/LandscapeGate.vue          # [NEW] 牌桌竖屏遮罩：提示横屏、按钮尝试全屏、iOS 文案兜底
        ├── components/MobileNavBar.vue           # [NEW] 移动顶部栏：标题/副标题、返回、家庭 chip（可切换）
        ├── components/MobileTabBar.vue           # [NEW] 底部 Tab：大厅/战绩/家庭，安全区适配，路由高亮
        ├── components/MobileSheet.vue            # [NEW] 底部抽屉基座：遮罩、滚动锁定、安全区、上滑动画
        ├── components/DesktopOnlySheet.vue       # [NEW] 「请用电脑打开 /majiangapp/ 操作」提示（规则模板/皮肤/成员入口）
        ├── components/JoinCodeInput.vue          # [NEW] 6 位邀请码：数字键盘、整串粘贴、输满回调、错误态
        ├── components/MobileCreateRoomSheet.vue  # [NEW] 建桌抽屉：规则族/模板选择、桌名、未就绪族禁用（复用 /rules、/rule-families、POST /rooms）
        ├── components/table/MobileScoreBoard.vue # [NEW] 牌桌顶栏：房间名、邀请码复制、局风/局数、牌墙、连接状态；「更多」抽屉含规则详情/皮肤/音效/结束牌局/离桌
        ├── components/table/MobileSeatChip.vue   # [NEW] 对家/上家/下家：头像、昵称、庄/房主/围观、分数、副露(micro)、手牌张数、回合高亮
        ├── components/table/MobileRiver.vue      # [NEW] 中央牌河：自己 6 列网格 + 三家紧凑条 + 牌墙剩余 + 最后一张高亮
        ├── components/table/MobileHand.vue       # [NEW] 自己手牌：宽度自适应档位、横滑、摸牌分隔、听牌高亮、选中抬起、点选回调
        ├── views/MobileLoginView.vue             # [NEW] 竖屏登录：账号/密码大输入、错误条、忘记密码、注册入口（按 options 开关）、服务状态
        ├── views/MobileRegisterView.vue          # [NEW] 竖屏注册：手机号/昵称/密码/验证码流程，成功后回填登录页
        ├── views/MobileForgotPasswordView.vue    # [NEW] 竖屏找回密码：验证码 + 重置，成功后回登录
        ├── views/MobileLobbyView.vue             # [NEW] 大厅：问候与统计、家庭切换、进行中牌桌卡片、邀请码入座、创建牌桌、PC-only 入口提示
        ├── views/MobileFamiliesView.vue          # [NEW] 家庭：卡片列表与切换、创建家庭抽屉、成员管理入口转 PC 提示
        ├── views/MobileRoomView.vue              # [NEW] 横屏牌桌：三段布局、四方位座位、观战目标选择、聊天抽屉、结算/结束/整场结束/进桌申请等浮层，复用 ActionBar/ResultModal/SpectatePanel/TurnTimer
        └── views/MobileHistoryView.vue           # [NEW] 战绩：统计卡 + Sparkline、时间筛选、场次列表、底部抽屉详情（番种/分数变化/终局手牌）

code/deploy/
├── nginx-majiang.conf                            # [MODIFY] 追加 /mjmobile/tileart/、/mjmobile/audio/sfx/、/mjmobile/ SPA 回退
└── deploy-mobile.sh                              # [NEW] 服务器端手机版发版：备份 mjmobile → rsync dist-mobile → 权限 → 校验（不重启后端）

docs/部署.md                                       # [MODIFY] 增加手机版构建与 /mjmobile 发布、nginx 片段、回滚说明
```

## 设计定位

「把牌桌搬到手里」——沿用 PC 的墨绿绒面 + 哑金 + 米白牌面质感，但形态彻底移动化：信息上收、操作下沉、一屏一任务。竖屏页面为单列流式（内容居中、最大宽 560px），牌桌是唯一的横屏沉浸场景，进入即提示横屏并可一键全屏。

## 视觉语言

- **材质**：深墨绿绒面背景（径向渐变 + 细噪点感），面板用半透明玻璃 + 1px 金线描边；牌面米白、投影短而实，模拟实体牌。
- **层次**：顶栏压暗（`bg-felt-950/85` + 轻模糊），内容区通透，底部操作区用高对比金色实体按钮，形成「暗底—亮操作」的视觉锚点。
- **动效**：页面切换 200ms 位移淡入；抽屉 240ms 上滑带阻尼；牌被选中抬起 8px 并描金边；事件横幅从牌河顶部滑入 2.6s 后消失；按钮 `active` 缩放 0.98 给出触感。全部尊重 `prefers-reduced-motion`。
- **触控**：所有可点区域 ≥ 44×44px；卡片与列表项整块可点；不使用 hover-only 反馈。

## 页面规划

### 1. 牌桌（横屏，主场景）

- **顶栏**：房间名 + 邀请码胶囊（点击复制）、局风与第 N/M 局、牌墙余量、连接呼吸点、「更多」图标。
- **对家条**：居中窄条，头像 + 昵称 + 分数 + 副露小牌 + 剩余张数，回合时金色呼吸描边。
- **左右座位**：各占 72px 竖列，头像在上、昵称与分数竖排，副露竖叠，信息极简。
- **中央牌河**：四方位小牌网格，中央牌墙计数（大号数字 + 「剩余」），最后一张描金；横幅叠在牌河上方。
- **自己区**：副露单行（小牌 + 被吃标记点），下方手牌整排，摸到的牌用金色竖线隔开，听牌张金框，选中抬起。
- **底部操作**：打出确认条（已选牌名 + 打出/取消）或 吃/碰/杠/胡/过 动作条，高度固定不遮手牌，含安全区留白。
- **辅层**：竖屏遮罩（大图标 + 「把手机横过来」+ 全屏按钮）；结算面板、聊天抽屉、观战选择、进桌申请、离桌确认均为底部或居中浮层。

### 2. 大厅

- **顶部**：问候语 + 一句战绩摘要（累计积分 / 场次 / 胡牌），右侧家庭 chip 横滑切换。
- **进行中牌桌**：卡片流（桌名、邀请码、规则族徽标、人数与围观数），整卡可点直达牌桌；房主卡片右上角可关闭。
- **邀请码入座**：6 格数字框，输满自动校验，错误红字就近提示。
- **主操作**：底部固定「创建牌桌」金色大按钮，上方是规则模板（点击提示用电脑）与战绩快捷入口。
- **底部 Tab**：大厅 / 战绩 / 家庭，安全区内边距。

### 3. 登录 / 注册 / 找回

- 背景漂浮半透明大牌 + 中心金色光晕，卡片居中，顶部品牌小字。
- 输入框 48px 高、圆角 12px、聚焦金色描边；主按钮满宽、48px 高；错误提示为红边条置于按钮上方。
- 底部一行服务状态圆点 + 版本号；键盘弹起用 `dvh` + 滚动到可见保证按钮可达。

### 4. 战绩

- 顶部 2×2 统计卡（累计积分、参与场次、最高单场、胡牌局数），下方迷你积分走势线。
- 时间筛选为胶囊 chips（全部 / 近 30 天 / 近 7 天）。
- 场次列表：房名 + 时间 + 四人小色点与分数 + 右侧我的得分（正绿负红）；客队场次带金色小标签。
- 点击从底部抽屉展开详情：四人分数卡、本场规则摘要、逐局番种标签与分数变化、终局四家手牌（小牌 + 副露分组）。

### 5. 家庭

- 家庭卡列表：首字母圆形徽标 + 名称 + 编码 + 角色徽章 + 成员数/默认规则，当前家庭金色描边并显示「当前」。
- 卡片底部两个按钮：「进入（切换）」与「成员（提示用电脑）」。
- 右下角「新建家庭」浮动按钮打开抽屉：家庭名称、编码（可留空自动生成）、默认规则族下拉。

## Agent Extensions

### Skill

- **playwright-cli**
- Purpose: 在移动端页面完成后，用手机视口（如 390×844 竖屏与 844×390 横屏）打开本地 `vite` 服务或线上 `/mjmobile/`，跑通「登录 → 大厅 → 邀请码/建桌 → 横屏牌桌」关键路径并截图。
- Expected outcome: 产出竖屏与横屏两套截图，确认无横向溢出、牌桌四方位与手牌区不重叠、动作条不遮挡手牌、安全区与横屏遮罩生效；据此列出需要修的样式问题并修完复验。
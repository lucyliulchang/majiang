<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, Eye, Flag, Hand, Loader2, MessageSquare, Play, Timer, WifiOff } from 'lucide-vue-next'

import ChatPanel from '../components/ChatPanel.vue'
import ActionBar from '../components/table/ActionBar.vue'
import DiscardRiver from '../components/table/DiscardRiver.vue'
import HandTiles from '../components/table/HandTiles.vue'
import PlayerSeat from '../components/table/PlayerSeat.vue'
import ResultModal from '../components/table/ResultModal.vue'
import ScoreBoard from '../components/table/ScoreBoard.vue'
import SpectatePanel from '../components/table/SpectatePanel.vue'
import Tile from '../components/table/Tile.vue'
import TurnTimer from '../components/table/TurnTimer.vue'
import { useHandCursor } from '../composables/useHandCursor'
import { useToast } from '../composables/useToast'
import { useAuthStore } from '../stores/auth'
import { CHOW_PICK_LIMIT, useGameStore } from '../stores/game'
import { useSkinsStore } from '../stores/skins'
import type { LegalAction } from '../types'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const auth = useAuthStore()
const game = useGameStore()
const skins = useSkinsStore()

const code = String(route.params.code || '').toUpperCase()
const dismissedRound = ref<number | null>(null)
const chatOpen = ref(false)
const spectateOpen = ref(false)

onMounted(() => {
  game.enterRoom(code)
  // 皮肤清单进桌即就绪：切换时只换 assetMap，不刷新牌桌
  void skins.ensureLoaded()
})

onBeforeUnmount(() => {
  game.leaveRoom()
})

const phase = computed(() => game.phase)
const inGame = computed(() => phase.value !== 'waiting')
const selfSeat = computed(() => game.selfSeat)
const isSpectator = computed(() => selfSeat.value === null)
const mySeatView = computed(() => game.mySeatView)
const turn = computed(() => game.turn)
const seats = computed(() => game.seats)

const relative = computed(() => {
  // 观战时把「被关注的人」摆到底部：手牌、副露、牌河才能像本家视角一样对齐
  const self = selfSeat.value ?? game.spectateSeat ?? 0
  return {
    self,
    right: (self + 1) % 4,
    across: (self + 2) % 4,
    left: (self + 3) % 4
  }
})

function seatAt(seat: number) {
  return game.snapshot?.seats?.[seat] ?? null
}

const showResult = computed(() => {
  const result = game.result
  if (!result || phase.value !== 'settled') return false
  return dismissedRound.value !== result.round_no
})

/** 结算面板被「看看牌桌」收起后，牌桌上要留一个随时能回去的入口 */
const resultDismissed = computed(() => {
  const result = game.result
  if (!result || phase.value !== 'settled') return false
  return dismissedRound.value === result.round_no
})

function reopenResult(): void {
  dismissedRound.value = null
}

/** 收起结算：提醒一句怎么回到结算 / 进入下一局，避免以为卡在牌桌上 */
function dismissResult(): void {
  dismissedRound.value = game.result?.round_no ?? null
  toast.info('结算已收起，牌桌下方可随时点「看结算」或「下一局」')
}

const myTurnTimerVisible = computed(
  () => Boolean(game.snapshot?.deadline) && game.ruleBrief?.turn_timeout.enabled
)

const canDiscard = computed(() => game.isMyTurn && game.hasAction('discard'))

// 手牌游标：鼠标点选与键盘共用一套选中状态（←/→ 选牌，空格/↑ 出牌，↓/Esc 取消）
// 吃牌选两张走同一套组件的**多选**分支（U-2）：出牌仍是单选，两者互不污染
const {
  selectedIndex,
  selectedName,
  multiSelected,
  select: selectTile,
  clear: clearSelection,
  setMulti,
  clearMulti,
  discardSelected
} = useHandCursor({
  hand: computed(() => game.hand),
  drawn: computed(() => game.drawn),
  active: computed(() => canDiscard.value || game.chowSelecting),
  discard: (tile) => game.discard(tile),
  multiActive: computed(() => game.chowSelecting),
  multiLimit: CHOW_PICK_LIMIT,
  onMultiChange: (tiles) => game.setChowPicks(tiles),
  onNothingToDiscard: () => toast.info('先点一张牌，再按空格出牌')
})

// ---- 吃牌选两张（v1.1.0 U-2）：点「吃」只进选牌态，确认后才提交 ----
/** 进入选牌态并默认套用服务端推荐组合 */
function openChow(): void {
  game.beginChow()
  setMulti(game.chowPicks)
}

/** 点候选组合一键套用 */
function applyChow(tiles: number[]): void {
  game.setChowPicks(tiles)
  setMulti(tiles)
}

function cancelChow(): void {
  game.cancelChow()
  clearMulti()
}

function confirmChow(): void {
  game.confirmChow()
  clearMulti()
}

// 窗口关闭（收口 / 超时 / 换牌）时 store 会清空选牌态，手牌高亮跟着退
watch(
  () => game.chowSelecting,
  (open) => {
    if (!open) clearMulti()
  }
)
// 换局时手牌会重发，游标必须回到未选中
watch(
  () => game.result?.round_no,
  () => clearSelection()
)

// 自己回合的「过」只是「不杠/不自摸，直接出牌」：本地收起动作条即可，
// 不能发给服务端——出牌阶段服务端只认 discard/hu/kong，pass 会回 BAD_ACTION 卡住牌局
const passDismissed = ref(false)
watch(
  () => `${game.turn}|${game.legal.map((item) => `${item.action}:${item.kong_kind ?? ''}:${(item.tiles || []).join('-')}`).join(',')}`,
  () => {
    passDismissed.value = false
  }
)
const showActionBar = computed(() => {
  if (isSpectator.value || passDismissed.value) return false
  const actions = game.legal
  return actions.some((item) => item.action !== 'discard')
})

// ---- 开局设置：出牌/响应限时（默认 0 秒 = 不限时；房主开局前可改）----
const TIMEOUT_OPTIONS = [10, 15, 20, 30, 45, 60, 90, 120]
const timeoutChoice = ref(0)
/** 下拉选项：0 = 不限时；模板里若是个非常规值（如 18 秒）也一并列出来，避免选择框空白 */
const timeoutOptions = computed(() => {
  const list = [...TIMEOUT_OPTIONS]
  const current = Number(timeoutChoice.value) || 0
  if (current > 0 && !list.includes(current)) list.push(current)
  return list.sort((a, b) => a - b)
})
watch(
  () => [phase.value, game.ruleBrief?.turn_timeout.enabled, game.ruleBrief?.turn_timeout.seconds] as const,
  ([currentPhase, enabled, seconds]) => {
    // 只在等人阶段跟随规则快照，开局后不再回写（避免盖掉房主刚选的秒数）
    if (currentPhase !== 'waiting') return
    timeoutChoice.value = enabled ? Number(seconds ?? 0) || 15 : 0
  },
  { immediate: true }
)

function startGame(): void {
  const seconds = timeoutChoice.value > 0 ? timeoutChoice.value : 0
  game.startGame({ enabled: seconds > 0, seconds })
}

// ---- 观战（S5b）：一人一目标，未选目标只收公共牌面 ----
const spectate = computed(() => game.spectate)
const spectateTarget = computed(() => game.spectateSeatView)
const spectateLimit = computed(() => spectate.value?.limit_per_seat ?? 10)
const spectateViewerCount = computed(() => spectate.value?.viewer_count ?? 0)
const needSpectateChoice = computed(() => isSpectator.value && !spectateTarget.value)

function openSpectate(): void {
  spectateOpen.value = true
}

function follow(seat: number): void {
  game.followSeat(seat)
  spectateOpen.value = false
}

function cancelSpectate(): void {
  game.followSeat(null)
  spectateOpen.value = false
}

function onAct(action: LegalAction): void {
  // 吃不再"点一下就提交"：进选牌态，由玩家指定用哪两张手牌（U-2）
  if (action.action === 'chow') {
    openChow()
    return
  }
  game.act(action)
}

function onPass(): void {
  // 自己的回合：过 = 不杠、不自摸，收起动作条去出牌（服务端出牌阶段不认 pass）
  if (game.isMyTurn && game.hasAction('discard')) {
    passDismissed.value = true
    return
  }
  game.pass()
}

function copyCode(): void {
  const text = game.snapshot?.room?.room_code || code
  navigator.clipboard?.writeText(text).then(
    () => toast.success(`邀请码 ${text} 已复制`),
    () => toast.warn(`邀请码是 ${text}`)
  )
}

function exitRoom(): void {
  game.leaveRoom()
  router.push({ name: 'lobby' })
}

function nextRound(): void {
  dismissedRound.value = game.result?.round_no ?? null
  game.nextRound()
}

// ---- 结束牌局（仅开桌的人）：二次确认后提前收场，已打完的局保留 ----
const endConfirmOpen = ref(false)
/** 房态口径与后端一致（`RoomActor.status`）：只要不是 waiting 就能收场，finished 是"关闭牌桌" */
const roomStatus = computed(() => game.snapshot?.status ?? 'waiting')
const canEndGame = computed(() => game.isHost && roomStatus.value !== 'waiting')
const endGameLabel = computed(() => (roomStatus.value === 'finished' ? '关闭牌桌' : '结束牌局'))

function confirmEndGame(): void {
  endConfirmOpen.value = false
  game.endGame()
}

/** 回大厅：房间还没关掉时房主先幂等关房（REST），关不上也不拦人，大厅可以再关 */
async function backToLobby(): Promise<void> {
  await game.exitToLobby()
  router.push({ name: 'lobby' })
}

/**
 * 底部手牌区对应的人：在座玩家看自己，观战者看被关注的人。
 * 手牌、副露（吃碰杠）与分数必须同一视角，否则观战时会「看得到手牌却看不到吃碰」。
 */
const bottomView = computed(() => (isSpectator.value ? spectateTarget.value : mySeatView.value))
const myMelds = computed(() => bottomView.value?.melds || [])
const hintEnabled = computed(() => Boolean(game.ruleBrief?.ting_hint))
/** 吃牌时标出「被吃的那一张」；碰/杠整组同牌，不标 */
function claimIndex(meld: { kind: string; tiles: number[]; claim_tile?: number | null }): number {
  if (meld.kind !== 'chow') return -1
  const claim = meld.claim_tile
  if (claim === null || claim === undefined) return -1
  return meld.tiles.indexOf(claim)
}
/** 庄家昵称：ScoreBoard 显示「南风局 · 第 2/4 局 · 庄家 X」 */
const dealerName = computed(() => {
  const seat = game.snapshot?.dealer_seat
  if (seat === null || seat === undefined) return null
  return game.snapshot?.seats?.[seat]?.display_name || null
})
</script>

<template>
  <div class="flex h-screen min-h-[640px] flex-col overflow-hidden">
    <!-- 顶部信息条 -->
    <!-- relative z-50：header 因 backdrop-blur 自成层叠上下文，需压在牌桌与聊天栏之上，
         否则 ScoreBoard 里 z-40 的皮肤/音效弹层会被后面的牌桌区域遮住、点不到 -->
    <header class="relative z-50 flex min-h-14 shrink-0 items-center border-b border-gold-400/15 bg-felt-950/85 px-3 py-1.5 backdrop-blur sm:px-4">
      <div v-if="game.snapshot" class="w-full">
        <ScoreBoard
          :room-name="game.snapshot.room.room_name"
          :code="game.snapshot.room.room_code"
          :rule-name="game.snapshot.room.rule_name"
          :rule-brief="game.ruleBrief"
          :wall-count="game.snapshot.wall_count"
          :round-no="game.snapshot.round_no"
          :total-rounds="game.snapshot.rounds_per_circle ?? 4"
          :round-in-circle="game.snapshot.round_in_circle ?? null"
          :circle-no="game.snapshot.circle_no ?? 1"
          :total-circles="game.snapshot.total_circles ?? 1"
          :dealer-continue="Boolean(game.snapshot.dealer_continue)"
          :family-name="game.snapshot.room.family_name"
          :family-code="game.snapshot.room.family_code"
          :round-wind="game.snapshot.round_wind ?? (game.snapshot.round_no ? (game.snapshot.round_no - 1) % 4 : null)"
          :dealer-name="dealerName"
          :connected="game.connected"
          :can-end-game="canEndGame"
          :end-game-label="endGameLabel"
          @copy="copyCode"
          @exit="exitRoom"
          @end-game="endConfirmOpen = true"
        />
      </div>
      <div v-else class="flex items-center gap-2 text-sm text-ink-300/70">
        <Loader2 class="h-4 w-4 animate-spin" />
        正在进入牌桌 {{ code }}…
      </div>
    </header>

    <!-- 观战横幅：常驻但不遮挡牌河（独立一行，不叠在牌桌上） -->
    <div
      v-if="isSpectator && spectateTarget"
      class="flex h-9 shrink-0 items-center justify-center gap-2 border-b border-gold-400/15 bg-gold-400/[0.06] px-3 text-xs"
    >
      <Eye class="h-3.5 w-3.5 shrink-0 text-gold-300" />
      <span class="truncate text-cream-100">正在观战：{{ spectateTarget.display_name }}</span>
      <span class="shrink-0 text-ink-300/70">{{ spectateViewerCount }}/{{ spectateLimit }}</span>
      <button type="button" class="btn-ghost shrink-0 rounded px-2 py-0.5 text-[11px]" @click="openSpectate">
        切换
      </button>
      <button type="button" class="shrink-0 rounded px-2 py-0.5 text-[11px] text-ink-300/70" @click="cancelSpectate">
        取消跟随
      </button>
    </div>

    <div class="flex min-h-0 flex-1">
      <!-- 牌桌：不要抬高层级，header 的 skin/sound 弹层要压在牌桌之上 -->
      <section class="relative flex min-w-0 flex-1 items-center justify-center p-3">
        <div class="felt-panel relative flex h-full w-full max-w-[1120px] flex-col gap-2 rounded-[28px] p-3 shadow-table">
          <!-- 顶部：对家（compact：只留昵称/分数/张数，把空间让给自己的手牌） -->
          <div class="flex justify-center">
            <div class="w-[min(100%,440px)]">
              <PlayerSeat
                v-if="seatAt(relative.across)"
                :seat="seatAt(relative.across)!"
                :is-turn="turn === relative.across"
                :is-dealer="game.snapshot?.dealer_seat === relative.across"
                :show-ready="!inGame"
                compact
              />
              <div v-else class="rounded-xl border border-dashed border-cream-100/15 py-3 text-center text-xs text-ink-300/50">
                空座，等待家人入座
              </div>
            </div>
          </div>

          <!-- 中部：左右座位 + 牌河 -->
          <div class="grid min-h-0 flex-1 grid-cols-[minmax(96px,140px)_1fr_minmax(96px,140px)] gap-2">
            <div class="flex flex-col items-stretch justify-center gap-2">
              <div class="w-full">
                <PlayerSeat
                  v-if="seatAt(relative.left)"
                  :seat="seatAt(relative.left)!"
                  :is-turn="turn === relative.left"
                  :show-ready="!inGame"
                  compact
                />
                <div v-else class="rounded-xl border border-dashed border-cream-100/15 py-3 text-center text-[11px] text-ink-300/50">
                  空座
                </div>
              </div>

              <!-- 左侧出牌提示：只在自己该出牌时亮；点牌先选中，再点一次取消 -->
              <transition name="fade">
                <div
                  v-if="canDiscard"
                  class="flex items-center justify-center gap-1.5 rounded-xl border border-gold-400/60 bg-gold-400/15 px-2 py-2 text-[11px] font-medium leading-tight text-gold-100 shadow-gold animate-breathe"
                >
                  <Hand class="h-3.5 w-3.5 shrink-0 text-gold-300" />
                  <span>{{ selectedIndex === null ? '轮到你出牌（←→ 选牌，空格/↑ 出牌）' : '点牌可改选，按「打出」出牌' }}</span>
                </div>
              </transition>
            </div>

            <div class="relative min-h-0 rounded-2xl border border-cream-100/[0.06] bg-felt-950/25">
              <DiscardRiver
                :discards="game.snapshot?.discards || [[], [], [], []]"
                :self-seat="relative.self"
                :last-discard="game.snapshot?.last_discard || null"
                :wall-count="game.snapshot?.wall_count || 0"
                :turn="turn"
              />

              <!-- 提示横幅 -->
              <transition name="fade">
                <div
                  v-if="game.banner"
                  class="pointer-events-none absolute left-1/2 top-3 -translate-x-1/2 whitespace-nowrap rounded-full border px-4 py-2 text-sm backdrop-blur"
                  :class="
                    game.banner.kind === 'win'
                      ? 'border-vermilion-500/50 bg-vermilion-500/20 text-cream-50'
                      : 'border-gold-400/40 bg-felt-950/85 text-gold-100'
                  "
                >
                  {{ game.banner.text }}
                </div>
              </transition>

              <!-- 等待开局遮罩 -->
              <div
                v-if="!inGame"
                class="absolute inset-0 flex flex-col items-center justify-center gap-3 overflow-y-auto rounded-2xl bg-felt-950/70 py-2 backdrop-blur-[2px]"
              >
                <p class="text-sm text-cream-100">等人齐了就开始</p>
                <div class="flex gap-1.5">
                  <Tile v-for="index in 4" :key="index" :tile="0" size="sm" face-down :dim="index > seats.length" />
                </div>
                <p class="text-xs text-ink-300/70">{{ seats.length }} / 4 位家人已入座</p>
                <div class="flex flex-col items-center gap-2">
                  <button
                    v-if="!isSpectator"
                    type="button"
                    class="rounded-lg px-5 py-2 text-sm font-semibold transition"
                    :class="
                      mySeatView?.ready
                        ? 'btn-ghost'
                        : 'btn-gold'
                    "
                    @click="game.toggleReady()"
                  >
                    {{ mySeatView?.ready ? '取消准备' : '我准备好了' }}
                  </button>
                  <!-- 开局设置：出牌限时（默认不限时） -->
                  <div
                    v-if="game.isHost"
                    class="flex items-center gap-1.5 rounded-lg border border-cream-100/12 bg-felt-950/60 px-2.5 py-1.5 text-[11px] text-ink-300/85"
                  >
                    <Timer class="h-3.5 w-3.5 shrink-0 text-gold-300" />
                    <span class="whitespace-nowrap" title="选 0 秒即不限时：出牌与吃碰杠胡的响应都不计时、也不会自动「过」">
                      限时
                    </span>
                    <select
                      v-model.number="timeoutChoice"
                      aria-label="出牌与响应限时"
                      title="选 0 秒即不限时：出牌与吃碰杠胡的响应都不计时、也不会自动「过」"
                      class="rounded-md border border-cream-100/15 bg-felt-900 px-1.5 py-1 text-[11px] text-cream-100"
                    >
                      <option :value="0">0 秒（不限时）</option>
                      <option v-for="sec in timeoutOptions" :key="sec" :value="sec">{{ sec }} 秒</option>
                    </select>
                  </div>
                  <button
                    v-if="game.isHost"
                    type="button"
                    class="btn-gold flex items-center gap-2 rounded-lg px-5 py-2 text-sm font-semibold"
                    :disabled="!game.everyoneReady"
                    @click="startGame"
                  >
                    <Play class="h-4 w-4" />
                    {{ game.everyoneReady ? '开始牌局' : '等所有人准备' }}
                  </button>
                  <p v-if="isSpectator" class="flex items-center gap-1 text-xs text-ink-300/60">
                    <Eye class="h-3.5 w-3.5" />
                    座位已满，你在观战
                  </p>
                </div>
              </div>
            </div>

            <div class="flex items-center justify-end">
              <div class="w-full">
                <PlayerSeat
                  v-if="seatAt(relative.right)"
                  :seat="seatAt(relative.right)!"
                  :is-turn="turn === relative.right"
                  :show-ready="!inGame"
                  compact
                />
                <div v-else class="rounded-xl border border-dashed border-cream-100/15 py-3 text-center text-[11px] text-ink-300/50">
                  空座
                </div>
              </div>
            </div>
          </div>

          <!-- 底部：自己 -->
          <div class="shrink-0">
            <div class="mb-2 flex items-end justify-between gap-3">
              <div class="flex items-center gap-2">
                <span
                  class="flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold text-felt-950"
                  :style="{ backgroundColor: bottomView?.color || auth.avatarColor }"
                >
                  {{ (bottomView?.display_name || auth.displayName).slice(0, 1) }}
                </span>
                <div class="leading-tight">
                  <p class="text-xs text-cream-100">
                    {{ bottomView?.display_name || (isSpectator ? '观战中' : auth.displayName) }}
                  </p>
                  <p class="text-[10px]" :class="(bottomView?.total_score || 0) >= 0 ? 'text-jade-400' : 'text-vermilion-400'">
                    累计 {{ bottomView?.total_score ?? 0 }}
                    <span v-if="bottomView?.round_score" class="text-ink-300/60">
                      · 本局 {{ bottomView.round_score > 0 ? '+' : '' }}{{ bottomView.round_score }}
                    </span>
                  </p>
                </div>
                <div v-if="myTurnTimerVisible && game.isMyTurn" class="ml-2">
                  <TurnTimer
                    :deadline="game.snapshot?.deadline ?? null"
                    :total="game.ruleBrief?.turn_timeout.seconds || 15"
                  />
                </div>
                <span
                  v-else-if="!game.connected"
                  class="ml-2 flex items-center gap-1 text-[11px] text-vermilion-400"
                >
                  <WifiOff class="h-3.5 w-3.5" />
                  {{ game.connectionDetail || '重连中' }}
                </span>
              </div>

              <div class="flex flex-wrap items-center justify-end gap-1">
                <div
                  v-for="(meld, index) in myMelds"
                  :key="index"
                  class="flex items-center gap-[1px] rounded border border-gold-400/25 bg-felt-900/60 px-1 py-0.5"
                >
                  <Tile
                    v-for="(tile, tileIndex) in meld.tiles"
                    :key="tileIndex"
                    :tile="tile"
                    size="sm"
                    :mark="tileIndex === claimIndex(meld)"
                  />
                </div>
              </div>
            </div>

            <div class="flex min-h-[92px] items-end justify-center overflow-x-auto pb-1">
              <!-- 在座玩家看自己的牌；观战者看目标（只读）；未选目标没有任何手牌 -->
              <HandTiles
                v-if="!isSpectator || spectateTarget"
                :tiles="game.hand"
                :drawn="game.drawn"
                :selected-index="selectedIndex"
                :selected-indices="multiSelected"
                :tenpai="game.tenpai"
                :interactive="canDiscard || game.chowSelecting"
                :show-hint="hintEnabled && canDiscard"
                @select="selectTile"
              />
              <div v-else class="flex items-center gap-2 pb-4">
                <p class="text-xs text-ink-300/60">你在观战，还没选观战对象</p>
                <button type="button" class="btn-gold rounded-lg px-3 py-1 text-[11px]" @click="openSpectate">
                  选一位家人
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- 出牌确认条：点牌只选中，再点一次取消选中，按「打出」才真正出牌 -->
        <div
          v-if="canDiscard && selectedIndex !== null && !showActionBar"
          class="pointer-events-none absolute inset-x-0 bottom-24 flex justify-center px-4"
        >
          <div
            class="pointer-events-auto flex items-center gap-2 rounded-2xl border border-gold-400/30 bg-felt-950/85 px-3 py-2 shadow-table backdrop-blur-md animate-riseIn"
          >
            <span class="pl-1 text-[11px] text-ink-300/80">已选</span>
            <span class="text-xs font-semibold text-cream-100">{{ selectedName }}</span>
            <button type="button" class="btn-gold rounded-xl px-4 py-1.5 text-sm font-semibold" @click="discardSelected">
              打出
            </button>
            <button type="button" class="btn-ghost rounded-xl px-3 py-1.5 text-xs" @click="clearSelection">取消</button>
          </div>
        </div>

        <!-- 动作条 -->
        <div v-if="showActionBar" class="pointer-events-none absolute inset-x-0 bottom-24 flex justify-center px-4">
          <ActionBar
            :actions="game.legal"
            :claim-tile="game.snapshot?.legal?.claim_tile ?? null"
            :reason="game.snapshot?.legal?.reason"
            :chow-open="game.chowSelecting"
            :chow-picks="game.chowPicks"
            :chow-candidates="game.chowCandidates"
            :chow-valid="game.chowValid"
            :chow-hint="game.chowHint"
            @act="onAct"
            @pass="onPass"
            @open-chow="openChow"
            @apply-chow="applyChow"
            @confirm-chow="confirmChow"
            @cancel-chow="cancelChow"
          />
        </div>

        <!-- 结算收起后的回看入口：「看看牌桌」不是死路，随时能回到结算并点下一局 -->
        <div
          v-if="resultDismissed"
          class="pointer-events-none absolute inset-x-0 bottom-24 z-20 flex justify-center px-4"
        >
          <div
            class="pointer-events-auto flex items-center gap-2 rounded-full border border-gold-400/35 bg-felt-900/90 px-2.5 py-1.5 text-xs shadow-table backdrop-blur animate-riseIn"
          >
            <span class="whitespace-nowrap pl-1 text-ink-300/75">第 {{ game.result?.round_no }} 局已结算</span>
            <button type="button" class="btn-ghost rounded-full px-2.5 py-1 text-[11px]" @click="reopenResult">
              看结算
            </button>
            <button
              type="button"
              class="btn-gold flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold"
              @click="nextRound"
            >
              {{ game.result?.is_last_round ? '查看总账' : '下一局' }}
              <ArrowRight class="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </section>

      <!-- 聊天：窄屏收成抽屉，把宽度让给手牌；≥1280px 才常驻 -->
      <aside class="hidden w-[300px] shrink-0 p-3 pl-0 xl:block">
        <ChatPanel
          :messages="game.chat"
          :self-login-id="auth.loginId"
          :connected="game.connected"
          @send="game.sendChat"
        />
      </aside>
    </div>

    <!-- 聊天抽屉 -->
    <button
      type="button"
      class="fixed bottom-6 right-4 z-30 flex h-12 w-12 items-center justify-center rounded-full border border-gold-400/40 bg-felt-800 text-gold-300 shadow-gold xl:hidden"
      aria-label="打开聊天"
      @click="chatOpen = true"
    >
      <MessageSquare class="h-5 w-5" />
    </button>

    <div
      v-if="chatOpen"
      class="fixed inset-0 z-50 flex justify-end bg-felt-950/70 backdrop-blur-sm xl:hidden"
      @click.self="chatOpen = false"
    >
      <div class="h-full w-[86%] max-w-[360px] p-3">
        <ChatPanel
          :messages="game.chat"
          :self-login-id="auth.loginId"
          :connected="game.connected"
          @send="game.sendChat"
        />
      </div>
    </div>

    <!-- 观战选择层：未选目标时常驻；点「切换」时作为弹层 -->
    <div
      v-if="needSpectateChoice || spectateOpen"
      class="fixed inset-0 z-[60] flex items-end justify-center bg-felt-950/85 px-3 pb-4 backdrop-blur-sm sm:items-center"
      @click.self="spectateTarget && (spectateOpen = false)"
    >
      <div class="glass w-full max-w-lg rounded-2xl p-4 shadow-table">
        <div class="mb-2 flex items-center justify-between">
          <h2 class="text-sm font-medium text-cream-100">选择观战对象</h2>
          <button
            v-if="spectateTarget"
            type="button"
            class="rounded px-2 py-0.5 text-[11px] text-ink-300/70"
            @click="spectateOpen = false"
          >
            关闭
          </button>
        </div>
        <SpectatePanel
          :seats="game.snapshot?.seats || [null, null, null, null]"
          :target-login-id="spectate?.target_login_id ?? null"
          :limit="spectateLimit"
          @select="follow"
          @cancel="cancelSpectate"
        />
        <p v-if="!spectateTarget" class="mt-3 text-[11px] leading-relaxed text-ink-300/60">
          不选也能留在牌桌旁看公共牌面（牌河、分数、倒计时），但看不到任何人的手牌。
        </p>
      </div>
    </div>

    <!-- S10：非本家庭成员凭码进桌 —— 等房主在牌桌上确认 -->
    <div
      v-if="game.joinPending"
      class="fixed inset-0 z-[75] flex items-center justify-center bg-felt-950/90 px-4 backdrop-blur-sm"
    >
      <div class="w-full max-w-sm animate-riseIn rounded-2xl border border-gold-400/30 bg-felt-900/95 p-5 text-center shadow-table">
        <Loader2 class="mx-auto h-6 w-6 animate-spin text-gold-300" />
        <h2 class="mt-3 text-base font-semibold text-cream-100">等房主确认进桌</h2>
        <p class="mt-2 text-xs leading-relaxed text-ink-300/80">
          这是「{{ game.joinPendingInfo?.family_name || '别人家' }}」的牌桌<span
            v-if="game.joinPendingInfo?.room_name"
          >「{{ game.joinPendingInfo.room_name }}」</span>。
          进桌申请已经发给房主，同意后会自动进来；房主不在牌桌上时可能等不到，可以先回大厅稍后再试。
        </p>
        <button type="button" class="btn-ghost mt-4 rounded-lg px-4 py-2 text-sm" @click="exitRoom">
          先回大厅
        </button>
      </div>
    </div>

    <!-- 房主没同意 / 房间已关 -->
    <div
      v-if="game.joinDenied"
      class="fixed inset-0 z-[75] flex items-center justify-center bg-felt-950/90 px-4 backdrop-blur-sm"
    >
      <div class="w-full max-w-sm animate-riseIn rounded-2xl border border-vermilion-500/35 bg-felt-900/95 p-5 text-center shadow-table">
        <h2 class="text-base font-semibold text-cream-100">进不了这桌</h2>
        <p class="mt-2 text-xs leading-relaxed text-ink-300/80">{{ game.joinDenied }}</p>
        <button type="button" class="btn-gold mt-4 rounded-lg px-4 py-2 text-sm font-semibold" @click="exitRoom">
          回大厅
        </button>
      </div>
    </div>

    <!-- 房主：非本家庭访客的进桌申请（只有房主收得到） -->
    <div
      v-if="game.joinRequests.length"
      class="fixed inset-0 z-[72] flex items-center justify-center bg-felt-950/85 px-4 backdrop-blur-sm"
    >
      <div class="w-full max-w-sm animate-riseIn rounded-2xl border border-gold-400/35 bg-felt-900/95 p-5 shadow-table">
        <h2 class="text-base font-semibold text-cream-100">有人想进这桌</h2>
        <p class="mt-1 text-[11px] leading-relaxed text-ink-300/65">
          这几位不是本家庭成员，凭邀请码过来，得你点头才能进桌。
        </p>
        <div class="mt-3 space-y-2">
          <div
            v-for="req in game.joinRequests"
            :key="req.login_id"
            class="flex items-center gap-2 rounded-xl border border-cream-100/12 bg-cream-100/[0.03] px-3 py-2"
          >
            <span class="min-w-0 flex-1 truncate text-sm text-cream-100">{{ req.display_name }}</span>
            <button
              type="button"
              class="btn-ghost rounded-lg px-2.5 py-1 text-[11px]"
              @click="game.approveJoin(req.login_id, false)"
            >
              拒绝
            </button>
            <button
              type="button"
              class="btn-gold rounded-lg px-2.5 py-1 text-[11px] font-semibold"
              @click="game.approveJoin(req.login_id, true)"
            >
              同意进桌
            </button>
          </div>
        </div>
      </div>
    </div>

    <ResultModal
      v-if="showResult && game.result"
      :result="game.result"
      :seats="seats"
      :self-seat="selfSeat"
      :base-score="game.ruleBrief?.base_score ?? 1"
      :dealer-seat="game.snapshot?.dealer_seat ?? null"
      @close="dismissResult"
      @next="nextRound"
    />

    <!-- 结束牌局确认：只有开桌的人能触发 -->
    <div
      v-if="endConfirmOpen"
      class="fixed inset-0 z-[70] flex items-center justify-center bg-felt-950/85 px-4 backdrop-blur-sm"
      @click.self="endConfirmOpen = false"
    >
      <div class="w-full max-w-sm animate-riseIn rounded-2xl border border-vermilion-500/35 bg-felt-900/95 p-5 text-center shadow-table">
        <p class="text-[11px] tracking-[0.3em] text-vermilion-400/80">END GAME</p>
        <h2 class="mt-1.5 text-lg font-semibold text-cream-100">{{ endGameLabel }}？</h2>
        <p v-if="roomStatus === 'finished'" class="mt-2 text-left text-xs leading-relaxed text-ink-300/80">
          本场已经打完，每一局的积分都已入库。关闭后这桌会立刻从大厅消失。
        </p>
        <p v-else class="mt-2 text-left text-xs leading-relaxed text-ink-300/80">
          已经打完的局和积分都会保留；正在进行的这一局直接作废，不计分。
          全桌会立刻看到本场结算，这桌随即关闭、不再留在大厅里。
        </p>
        <div class="mt-5 flex justify-center gap-2">
          <button type="button" class="btn-ghost rounded-lg px-4 py-2 text-sm" @click="endConfirmOpen = false">
            再打一会
          </button>
          <button
            type="button"
            class="flex items-center gap-1.5 rounded-lg bg-vermilion-500 px-4 py-2 text-sm font-semibold text-cream-50 transition hover:bg-vermilion-400"
            @click="confirmEndGame"
          >
            <Flag class="h-4 w-4" />
            {{ endGameLabel }}
          </button>
        </div>
      </div>
    </div>

    <!-- 整场结束 -->
    <div
      v-if="game.finished"
      class="fixed inset-0 z-[65] flex items-center justify-center bg-felt-950/88 px-4 backdrop-blur"
    >
      <div class="w-full max-w-md animate-riseIn rounded-2xl border border-gold-400/30 bg-felt-900/95 p-6 text-center">
        <p class="text-[11px] tracking-[0.3em] text-gold-400/70">GAME OVER</p>
        <h2 class="mt-2 text-xl font-semibold text-cream-100">
          {{ game.finished.aborted ? '本场提前结束' : '这场打完了' }}
        </h2>
        <p v-if="game.finished.aborted" class="mt-1 text-xs text-ink-300/70">
          {{ game.finished.ended_by_name ? `${game.finished.ended_by_name} 结束了牌局` : '已结束' }} · 未打完的一局不计分
        </p>
        <p v-if="game.roomClosed" class="mt-1 text-[11px] text-ink-300/55">
          这桌已经关闭，回大厅可以再开一桌
        </p>
        <div class="mt-4 space-y-1.5">
          <div
            v-for="entry in game.finished.scores"
            :key="entry.seat"
            class="flex items-center justify-between rounded-lg border border-cream-100/10 bg-cream-100/[0.03] px-3 py-2 text-sm"
          >
            <span class="text-cream-100">{{ entry.name }}</span>
            <span class="font-num font-bold" :class="entry.total >= 0 ? 'text-jade-400' : 'text-vermilion-400'">
              {{ entry.total > 0 ? '+' : '' }}{{ entry.total }}
            </span>
          </div>
        </div>
        <button type="button" class="btn-gold mt-5 w-full rounded-lg py-2.5 text-sm font-semibold" @click="backToLobby">
          回到大厅
        </button>
      </div>
    </div>

    <!-- 房间已被房主关闭，但本人没赶上结算广播：只留一条回大厅的路 -->
    <div
      v-if="game.roomClosed && !game.finished"
      class="fixed inset-0 z-[66] flex items-center justify-center bg-felt-950/88 px-4 backdrop-blur"
    >
      <div class="w-full max-w-sm animate-riseIn rounded-2xl border border-gold-400/25 bg-felt-900/95 p-6 text-center">
        <p class="text-[11px] tracking-[0.3em] text-gold-400/70">ROOM CLOSED</p>
        <h2 class="mt-2 text-lg font-semibold text-cream-100">这桌已经结束了</h2>
        <p class="mt-2 text-xs leading-relaxed text-ink-300/70">房主结束了本场牌局，回大厅可以再开一桌。</p>
        <button type="button" class="btn-gold mt-5 w-full rounded-lg py-2.5 text-sm font-semibold" @click="backToLobby">
          回到大厅
        </button>
      </div>
    </div>

  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

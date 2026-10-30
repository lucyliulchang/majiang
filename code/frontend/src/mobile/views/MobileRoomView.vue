<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, Eye, Hand, Loader2, Play, Timer, WifiOff } from 'lucide-vue-next'

import ChatPanel from '../../components/ChatPanel.vue'
import ActionBar from '../../components/table/ActionBar.vue'
import ResultModal from '../../components/table/ResultModal.vue'
import SpectatePanel from '../../components/table/SpectatePanel.vue'
import Tile from '../../components/table/Tile.vue'
import TurnTimer from '../../components/table/TurnTimer.vue'
import LandscapeGate from '../components/LandscapeGate.vue'
import MobileSheet from '../components/MobileSheet.vue'
import MobileHand from '../components/table/MobileHand.vue'
import MobileMoreSheet from '../components/table/MobileMoreSheet.vue'
import MobileRiver from '../components/table/MobileRiver.vue'
import MobileRoomOverlays from '../components/table/MobileRoomOverlays.vue'
import MobileScoreBoard from '../components/table/MobileScoreBoard.vue'
import MobileSeatChip from '../components/table/MobileSeatChip.vue'
import { useOrientation } from '../composables/useOrientation'
import { useHandCursor } from '../../composables/useHandCursor'
import { useToast } from '../../composables/useToast'
import { useAuthStore } from '../../stores/auth'
import { CHOW_PICK_LIMIT, useGameStore } from '../../stores/game'
import { useSkinsStore } from '../../stores/skins'
import type { LegalAction } from '../../types'

/**
 * 手机版牌桌（横屏）。
 *
 * 纵向三段：顶栏信息带 → 牌桌（左右座位竖条 + 对家横条 + 中央牌河）→ 自己（副露 + 手牌）
 * 再加一条独立的底部操作槽。动作条占槽位而不覆盖手牌，避免「点牌点到碰」。
 *
 * 状态与交互与 PC 的 RoomView 完全一致（同一个 game store、同一套 WS 协议），
 * 只有排布方式不同：先点牌选中，再按「打出」确认。
 */
const route = useRoute()
const router = useRouter()
const toast = useToast()
const auth = useAuthStore()
const game = useGameStore()
const skins = useSkinsStore()
const { exitFullscreen } = useOrientation()

const code = String(route.params.code || '').toUpperCase()
const dismissedRound = ref<number | null>(null)
const chatOpen = ref(false)
const spectateOpen = ref(false)
const moreOpen = ref(false)
const endConfirmOpen = ref(false)

onMounted(() => {
  game.enterRoom(code)
  // 皮肤清单进桌即就绪：切换时只换 assetMap，不刷新牌桌
  void skins.ensureLoaded()
})

onBeforeUnmount(() => {
  game.leaveRoom()
  exitFullscreen()
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
  return { self, right: (self + 1) % 4, across: (self + 2) % 4, left: (self + 3) % 4 }
})

function seatAt(seat: number) {
  return game.snapshot?.seats?.[seat] ?? null
}

const showResult = computed(() => {
  const result = game.result
  if (!result || phase.value !== 'settled') return false
  return dismissedRound.value !== result.round_no
})

const resultDismissed = computed(() => {
  const result = game.result
  if (!result || phase.value !== 'settled') return false
  return dismissedRound.value === result.round_no
})

function reopenResult(): void {
  dismissedRound.value = null
}

function dismissResult(): void {
  dismissedRound.value = game.result?.round_no ?? null
  toast.info('结算已收起，底部可随时点「看结算」或「下一局」')
}

const canDiscard = computed(() => game.isMyTurn && game.hasAction('discard'))

// 手牌游标：触屏点选与键盘（←/→ 选牌，空格/↑ 出牌，↓/Esc 取消）共用一套选中状态
// 吃牌选两张走同一套组件的**多选**分支（U-2），出牌仍是单选
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

// ---- 吃牌选两张（v1.1.0 U-2）：与桌面同一套交互，只是动作槽在底部 ----
function openChow(): void {
  game.beginChow()
  setMulti(game.chowPicks)
}

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

// 自己回合的「过」只是「不杠/不自摸，直接出牌」：本地收起动作条即可
const passDismissed = ref(false)
watch(
  () =>
    `${game.turn}|${game.legal
      .map((item) => `${item.action}:${item.kong_kind ?? ''}:${(item.tiles || []).join('-')}`)
      .join(',')}`,
  () => {
    passDismissed.value = false
  }
)

const showActionBar = computed(() => {
  if (isSpectator.value || passDismissed.value) return false
  return game.legal.some((item) => item.action !== 'discard')
})

// ---- 开局设置：出牌/响应限时（默认 0 秒 = 不限时）----
const TIMEOUT_OPTIONS = [10, 15, 20, 30, 45, 60, 90, 120]
const timeoutChoice = ref(0)
const timeoutOptions = computed(() => {
  const list = [...TIMEOUT_OPTIONS]
  const current = Number(timeoutChoice.value) || 0
  if (current > 0 && !list.includes(current)) list.push(current)
  return list.sort((a, b) => a - b)
})
watch(
  () => [phase.value, game.ruleBrief?.turn_timeout.enabled, game.ruleBrief?.turn_timeout.seconds] as const,
  ([currentPhase, enabled, seconds]) => {
    if (currentPhase !== 'waiting') return
    timeoutChoice.value = enabled ? Number(seconds ?? 0) || 15 : 0
  },
  { immediate: true }
)

function startGame(): void {
  const seconds = timeoutChoice.value > 0 ? timeoutChoice.value : 0
  game.startGame({ enabled: seconds > 0, seconds })
}

// ---- 观战（S5b）----
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
  moreOpen.value = false
  game.leaveRoom()
  void router.push({ name: 'lobby' })
}

/** 回大厅：房间还没关掉时房主先幂等关房（REST），关不上也不拦人，大厅可以再关 */
async function backToLobby(): Promise<void> {
  await game.exitToLobby()
  void router.push({ name: 'lobby' })
}

function nextRound(): void {
  dismissedRound.value = game.result?.round_no ?? null
  game.nextRound()
}

function confirmEndGame(): void {
  endConfirmOpen.value = false
  moreOpen.value = false
  game.endGame()
}

const myTurnTimerVisible = computed(
  () => Boolean(game.snapshot?.deadline) && Boolean(game.ruleBrief?.turn_timeout.enabled)
)

/** 房态口径与后端一致（`RoomActor.status`）：只要不是 waiting 就能收场，finished 是「关闭牌桌」 */
const roomStatus = computed(() => game.snapshot?.status ?? 'waiting')
const canEndGame = computed(() => game.isHost && roomStatus.value !== 'waiting')
const endGameLabel = computed(() => (roomStatus.value === 'finished' ? '关闭牌桌' : '结束牌局'))

const bottomView = computed(() => (isSpectator.value ? spectateTarget.value : mySeatView.value))
const myMelds = computed(() => bottomView.value?.melds || [])
const hintEnabled = computed(() => Boolean(game.ruleBrief?.ting_hint))
/** 听牌张数：规则开启听牌提示时才显示 */
const waitCount = computed(() => Object.keys(game.tenpai || {}).length)

/** 吃牌时标出「被吃的那一张」；碰/杠整组同牌，不标 */
function claimIndex(meld: { kind: string; tiles: number[]; claim_tile?: number | null }): number {
  if (meld.kind !== 'chow') return -1
  const claim = meld.claim_tile
  if (claim === null || claim === undefined) return -1
  return meld.tiles.indexOf(claim)
}

const dealerName = computed(() => {
  const seat = game.snapshot?.dealer_seat
  if (seat === null || seat === undefined) return null
  return game.snapshot?.seats?.[seat]?.display_name || null
})
</script>

<template>
  <div class="mj-dvh mj-table flex flex-col overflow-hidden">
    <header class="mj-bar-top shrink-0 px-2 py-1">
      <MobileScoreBoard
        v-if="game.snapshot"
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
        :round-wind="game.snapshot.round_wind ?? (game.snapshot.round_no ? (game.snapshot.round_no - 1) % 4 : null)"
        :dealer-name="dealerName"
        :connected="game.connected"
        :family-name="game.snapshot.room.family_name"
        @copy="copyCode"
        @more="moreOpen = true"
        @chat="chatOpen = true"
      />
      <div v-else class="flex items-center gap-2 text-[12px] text-ink-300/70">
        <Loader2 class="h-4 w-4 animate-spin" />
        正在进入牌桌 {{ code }}…
      </div>
    </header>

    <!-- 观战横幅：独立一行，不遮挡牌河 -->
    <div
      v-if="isSpectator && spectateTarget"
      class="flex h-7 shrink-0 items-center justify-center gap-2 border-b border-gold-400/15 bg-gold-400/[0.06] px-2 text-[11px]"
    >
      <Eye class="h-3 w-3 shrink-0 text-gold-300" />
      <span class="truncate text-cream-100">观战：{{ spectateTarget.display_name }}</span>
      <span class="shrink-0 text-ink-300/70">{{ spectateViewerCount }}/{{ spectateLimit }}</span>
      <button type="button" class="btn-ghost shrink-0 rounded px-1.5 py-0.5 text-[10px]" @click="openSpectate">切换</button>
      <button type="button" class="shrink-0 rounded px-1.5 py-0.5 text-[10px] text-ink-300/70" @click="cancelSpectate">取消</button>
    </div>

    <!-- 牌桌主体 -->
    <div class="flex min-h-0 flex-1 gap-1 px-1 pt-1">
      <div class="w-[62px] shrink-0">
        <MobileSeatChip
          v-if="seatAt(relative.left)"
          :seat="seatAt(relative.left)!"
          layout="side"
          :is-turn="turn === relative.left"
          :is-dealer="game.snapshot?.dealer_seat === relative.left"
          :show-ready="!inGame"
        />
        <div v-else class="flex h-full items-center justify-center rounded-lg border border-dashed border-cream-100/15">
          <span class="text-[10px] text-ink-300/45">空座</span>
        </div>
      </div>

      <div class="flex min-h-0 flex-1 flex-col gap-1">
        <div v-if="seatAt(relative.across)" class="shrink-0">
          <MobileSeatChip
            :seat="seatAt(relative.across)!"
            layout="bar"
            :is-turn="turn === relative.across"
            :is-dealer="game.snapshot?.dealer_seat === relative.across"
            :show-ready="!inGame"
          />
        </div>
        <div v-else class="shrink-0 rounded-lg border border-dashed border-cream-100/15 py-1 text-center text-[10px] text-ink-300/45">
          空座，等待家人入座
        </div>

        <div class="relative min-h-0 flex-1 overflow-hidden rounded-xl border border-cream-100/[0.06] bg-felt-950/25 px-1 py-1">
          <MobileRiver
            :discards="game.snapshot?.discards || [[], [], [], []]"
            :self-seat="relative.self"
            :last-discard="game.snapshot?.last_discard || null"
            :wall-count="game.snapshot?.wall_count || 0"
          />

          <!-- 事件横幅 -->
          <div
            v-if="game.banner"
            class="mj-banner pointer-events-none absolute left-1/2 top-1 z-10 max-w-[80%] truncate rounded-full border px-3.5 py-1.5 text-[13px]"
            :class="
              game.banner.kind === 'win'
                ? 'border-vermilion-500/50 bg-vermilion-500/25 text-cream-50'
                : 'border-gold-400/40 bg-felt-950/90 text-gold-100'
            "
          >
            {{ game.banner.text }}
          </div>

          <!-- 等人阶段 -->
          <div
            v-if="!inGame"
            class="mj-vscroll absolute inset-0 flex flex-col items-center justify-center gap-1.5 rounded-xl bg-felt-950/80 px-2 py-2 backdrop-blur-[1px]"
          >
            <p class="text-[12px] text-cream-100">等人齐了就开始 · {{ seats.length }} / 4 已入座</p>
            <div class="flex items-center gap-2">
              <button
                v-if="!isSpectator"
                type="button"
                class="mj-press rounded-lg px-4 py-1.5 text-[12px] font-semibold"
                :class="mySeatView?.ready ? 'btn-ghost' : 'btn-gold'"
                @click="game.toggleReady()"
              >
                {{ mySeatView?.ready ? '取消准备' : '我准备好了' }}
              </button>
              <button
                v-if="game.isHost"
                type="button"
                class="mj-press btn-gold flex items-center gap-1.5 rounded-lg px-4 py-1.5 text-[12px] font-semibold"
                :disabled="!game.everyoneReady"
                @click="startGame"
              >
                <Play class="h-3.5 w-3.5" />
                {{ game.everyoneReady ? '开始牌局' : '等所有人准备' }}
              </button>
            </div>
            <label
              v-if="game.isHost"
              class="flex items-center gap-1.5 rounded-lg border border-cream-100/10 bg-felt-950/60 px-2 py-1 text-[10px] text-ink-300/85"
            >
              <Timer class="h-3 w-3 text-gold-300" />
              <span>限时</span>
              <select
                v-model.number="timeoutChoice"
                aria-label="出牌与响应限时"
                class="rounded border border-cream-100/15 bg-felt-900 px-1 py-0.5 text-[10px] text-cream-100"
              >
                <option :value="0">0 秒（不限时）</option>
                <option v-for="sec in timeoutOptions" :key="sec" :value="sec">{{ sec }} 秒</option>
              </select>
            </label>
            <p v-if="isSpectator" class="text-[10px] text-ink-300/60">座位已满，你在观战</p>
          </div>
        </div>
      </div>

      <div class="w-[62px] shrink-0">
        <MobileSeatChip
          v-if="seatAt(relative.right)"
          :seat="seatAt(relative.right)!"
          layout="side"
          :is-turn="turn === relative.right"
          :is-dealer="game.snapshot?.dealer_seat === relative.right"
          :show-ready="!inGame"
        />
        <div v-else class="flex h-full items-center justify-center rounded-lg border border-dashed border-cream-100/15">
          <span class="text-[10px] text-ink-300/45">空座</span>
        </div>
      </div>
    </div>

    <!-- 自己：身份 + 副露 + 手牌 -->
    <div class="shrink-0 px-1">
      <div class="flex items-center gap-2 pb-0.5 pt-1">
        <span
          class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold text-felt-950"
          :style="{ backgroundColor: bottomView?.color || auth.avatarColor }"
        >
          {{ (bottomView?.display_name || auth.displayName).slice(0, 1) }}
        </span>
        <span class="max-w-[96px] shrink-0 truncate text-[11px] text-cream-100">
          {{ bottomView?.display_name || (isSpectator ? '观战中' : auth.displayName) }}
        </span>
        <span class="shrink-0 text-[11px]" :class="(bottomView?.total_score || 0) >= 0 ? 'text-jade-400' : 'text-vermilion-400'">
          {{ bottomView?.total_score ?? 0 }}
          <span v-if="bottomView?.round_score" class="text-ink-300/60">（{{ bottomView.round_score > 0 ? '+' : '' }}{{ bottomView.round_score }}）</span>
        </span>

        <TurnTimer
          v-if="myTurnTimerVisible && game.isMyTurn"
          :deadline="game.snapshot?.deadline ?? null"
          :total="game.ruleBrief?.turn_timeout.seconds || 15"
          :size="30"
        />
        <span v-else-if="!game.connected" class="flex items-center gap-1 text-[10px] text-vermilion-400">
          <WifiOff class="h-3 w-3" />
          {{ game.connectionDetail || '重连中' }}
        </span>

        <div class="ml-auto flex min-w-0 items-center gap-1 overflow-hidden">
          <div
            v-for="(meld, index) in myMelds"
            :key="index"
            class="flex shrink-0 items-center gap-[1px] rounded border border-gold-400/25 bg-felt-900/60 px-0.5"
          >
            <Tile
              v-for="(tile, tileIndex) in meld.tiles"
              :key="tileIndex"
              :tile="tile"
              size="micro"
              :mark="tileIndex === claimIndex(meld)"
            />
          </div>
        </div>
      </div>

      <div class="flex min-h-[54px] w-full items-end justify-center">
        <MobileHand
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
        <button
          v-else
          type="button"
          class="btn-gold mb-2 rounded-lg px-3 py-1.5 text-[11px]"
          @click="openSpectate"
        >
          你在观战，选一位家人
        </button>
      </div>
    </div>

    <!-- 底部操作槽：动作条 / 出牌确认都不覆盖手牌 -->
    <div class="mj-safe-b flex min-h-[54px] shrink-0 items-center justify-center px-1 pb-1">
      <ActionBar
        v-if="showActionBar"
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

      <div
        v-else-if="canDiscard && selectedIndex !== null"
        class="flex items-center gap-2 rounded-xl border border-gold-400/30 bg-felt-950/85 px-2.5 py-1.5"
      >
        <span class="pl-1 text-[10px] text-ink-300/80">已选</span>
        <span class="text-[12px] font-semibold text-cream-100">{{ selectedName }}</span>
        <button type="button" class="mj-press btn-gold rounded-lg px-3.5 py-1.5 text-[13px] font-semibold" @click="discardSelected">
          打出
        </button>
        <button type="button" class="mj-press btn-ghost rounded-lg px-2.5 py-1.5 text-[11px]" @click="clearSelection">取消</button>
      </div>

      <div
        v-else-if="resultDismissed"
        class="flex items-center gap-2 rounded-full border border-gold-400/35 bg-felt-900/90 px-2.5 py-1.5 text-[11px]"
      >
        <span class="whitespace-nowrap pl-1 text-ink-300/75">第 {{ game.result?.round_no }} 局已结算</span>
        <button type="button" class="btn-ghost rounded-full px-2.5 py-1 text-[10px]" @click="reopenResult">看结算</button>
        <button type="button" class="mj-press btn-gold flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-semibold" @click="nextRound">
          {{ game.result?.is_last_round ? '查看总账' : '下一局' }}
          <ArrowRight class="h-3 w-3" />
        </button>
      </div>

      <p v-else-if="canDiscard" class="flex items-center gap-1.5 text-[11px] text-gold-200">
        <Hand class="h-3.5 w-3.5 text-gold-300" />
        轮到你出牌：点一张牌，再按「打出」
        <span v-if="hintEnabled && waitCount > 0" class="rounded-full border border-gold-400/35 bg-gold-400/10 px-1.5 py-0.5 text-[10px] text-gold-300">
          {{ waitCount }} 张可听
        </span>
      </p>

      <p v-else-if="isSpectator && !spectateTarget" class="text-[11px] text-ink-300/60">
        未选观战对象，只能看到公共牌面
      </p>
    </div>

    <MobileSheet :open="chatOpen" title="牌桌闲聊" max-height="88vh" @close="chatOpen = false">
      <div class="h-[62vh]">
        <ChatPanel
          :messages="game.chat"
          :self-login-id="auth.loginId"
          :connected="game.connected"
          @send="game.sendChat"
        />
      </div>
    </MobileSheet>

    <!-- 观战对象选择 -->
    <MobileSheet
      :open="needSpectateChoice || spectateOpen"
      title="选择观战对象"
      subtitle="只能看到被关注那一位的手牌；不选也能看公共牌面"
      @close="spectateTarget && (spectateOpen = false)"
    >
      <SpectatePanel
        :seats="game.snapshot?.seats || [null, null, null, null]"
        :target-login-id="spectate?.target_login_id ?? null"
        :limit="spectateLimit"
        @select="follow"
        @cancel="cancelSpectate"
      />
    </MobileSheet>

    <MobileMoreSheet
      :open="moreOpen"
      :code="game.snapshot?.room.room_code || code"
      :rule-name="game.snapshot?.room.rule_name || '本局规则'"
      :rule-brief="game.ruleBrief"
      :can-end-game="canEndGame"
      :end-game-label="endGameLabel"
      @close="moreOpen = false"
      @copy="copyCode"
      @exit="exitRoom"
      @end-game="endConfirmOpen = true"
    />

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

    <MobileRoomOverlays
      :join-pending="game.joinPending"
      :join-pending-info="game.joinPendingInfo"
      :join-denied="game.joinDenied"
      :join-requests="game.joinRequests"
      :end-confirm-open="endConfirmOpen"
      :finished="game.finished"
      :room-closed="game.roomClosed"
      :end-game-label="endGameLabel"
      :end-game-final="roomStatus === 'finished'"
      @exit="exitRoom"
      @approve="game.approveJoin"
      @cancel-end="endConfirmOpen = false"
      @confirm-end="confirmEndGame"
      @back-to-lobby="backToLobby"
    />

    <LandscapeGate />
  </div>
</template>

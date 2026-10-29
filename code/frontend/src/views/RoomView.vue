<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Eye, Loader2, MessageSquare, Play, Timer, WifiOff } from 'lucide-vue-next'

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
import { useToast } from '../composables/useToast'
import { useAuthStore } from '../stores/auth'
import { useGameStore } from '../stores/game'
import { useSkinsStore } from '../stores/skins'
import type { LegalAction } from '../types'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const auth = useAuthStore()
const game = useGameStore()
const skins = useSkinsStore()

const code = String(route.params.code || '').toUpperCase()
const selected = ref<number | null>(null)
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

watch(
  () => game.result?.round_no,
  () => {
    selected.value = null
  }
)

const phase = computed(() => game.phase)
const inGame = computed(() => phase.value !== 'waiting')
const selfSeat = computed(() => game.selfSeat)
const isSpectator = computed(() => selfSeat.value === null)
const mySeatView = computed(() => game.mySeatView)
const turn = computed(() => game.turn)
const seats = computed(() => game.seats)

const relative = computed(() => {
  const self = selfSeat.value ?? 0
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

const myTurnTimerVisible = computed(
  () => Boolean(game.snapshot?.deadline) && game.ruleBrief?.turn_timeout.enabled
)

const canDiscard = computed(() => game.isMyTurn && game.hasAction('discard'))
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

function onSelect(tile: number): void {
  if (!canDiscard.value) return
  selected.value = selected.value === tile ? null : tile
}

function onDiscard(tile: number): void {
  if (!canDiscard.value) return
  game.discard(tile)
  selected.value = null
}

function onAct(action: LegalAction): void {
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

function backToLobby(): void {
  game.leaveRoom()
  router.push({ name: 'lobby' })
}

const myMelds = computed(() => mySeatView.value?.melds || [])
const hintEnabled = computed(() => Boolean(game.ruleBrief?.ting_hint))
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
          :total-rounds="game.snapshot.game_total_rounds"
          :family-name="game.snapshot.room.family_name"
          :family-code="game.snapshot.room.family_code"
          :round-wind="game.snapshot.round_wind ?? (game.snapshot.round_no ? game.snapshot.round_no - 1 : null)"
          :dealer-name="dealerName"
          :connected="game.connected"
          @copy="copyCode"
          @exit="exitRoom"
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
        <div class="felt-panel relative flex h-full w-full max-w-[1080px] flex-col gap-2 rounded-[28px] p-3 shadow-table">
          <!-- 顶部：对家 -->
          <div class="flex justify-center">
            <div class="w-[min(100%,540px)]">
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
          <div class="grid min-h-0 flex-1 grid-cols-[minmax(120px,180px)_1fr_minmax(120px,180px)] gap-2">
            <div class="flex items-center justify-start">
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
            </div>

            <div class="relative min-h-0 rounded-2xl border border-cream-100/[0.06] bg-felt-950/25">
              <DiscardRiver
                :discards="game.snapshot?.discards || [[], [], [], []]"
                :self-seat="selfSeat"
                :last-discard="game.snapshot?.last_discard || null"
                :wall-count="game.snapshot?.wall_count || 0"
                :turn="turn"
              />

              <!-- 提示横幅 -->
              <transition name="fade">
                <div
                  v-if="game.banner"
                  class="pointer-events-none absolute left-1/2 top-3 -translate-x-1/2 whitespace-nowrap rounded-full border px-3.5 py-1.5 text-xs backdrop-blur"
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
                class="absolute inset-0 flex flex-col items-center justify-center gap-4 rounded-2xl bg-felt-950/70 backdrop-blur-[2px]"
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
                  <button
                    v-if="game.isHost"
                    type="button"
                    class="btn-gold flex items-center gap-2 rounded-lg px-5 py-2 text-sm font-semibold"
                    :disabled="!game.everyoneReady"
                    @click="game.startGame()"
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
                  :style="{ backgroundColor: mySeatView?.color || auth.avatarColor }"
                >
                  {{ (mySeatView?.display_name || auth.displayName).slice(0, 1) }}
                </span>
                <div class="leading-tight">
                  <p class="text-xs text-cream-100">
                    {{ isSpectator ? '观战中' : mySeatView?.display_name || auth.displayName }}
                  </p>
                  <p class="text-[10px]" :class="(mySeatView?.total_score || 0) >= 0 ? 'text-jade-400' : 'text-vermilion-400'">
                    累计 {{ mySeatView?.total_score ?? 0 }}
                    <span v-if="mySeatView?.round_score" class="text-ink-300/60">
                      · 本局 {{ mySeatView.round_score > 0 ? '+' : '' }}{{ mySeatView.round_score }}
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
                  <Tile v-for="(tile, tileIndex) in meld.tiles" :key="tileIndex" :tile="tile" size="xs" />
                </div>
              </div>
            </div>

            <div class="flex min-h-[70px] items-end justify-center overflow-x-auto pb-1">
              <!-- 在座玩家看自己的牌；观战者看目标（只读）；未选目标没有任何手牌 -->
              <HandTiles
                v-if="!isSpectator || spectateTarget"
                :tiles="game.hand"
                :drawn="game.drawn"
                :selected="selected"
                :tenpai="game.tenpai"
                :interactive="canDiscard"
                :show-hint="hintEnabled && canDiscard"
                @select="onSelect"
                @discard="onDiscard"
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

        <!-- 动作条 -->
        <div v-if="showActionBar" class="pointer-events-none absolute inset-x-0 bottom-24 flex justify-center px-4">
          <ActionBar
            :actions="game.legal"
            :claim-tile="game.snapshot?.legal?.claim_tile ?? null"
            :reason="game.snapshot?.legal?.reason"
            @act="onAct"
            @pass="onPass"
          />
        </div>
      </section>

      <!-- 聊天 -->
      <aside class="hidden w-[330px] shrink-0 p-3 pl-0 lg:block">
        <ChatPanel
          :messages="game.chat"
          :self-login-id="auth.loginId"
          :connected="game.connected"
          @send="game.sendChat"
        />
      </aside>
    </div>

    <!-- 移动端聊天抽屉 -->
    <button
      type="button"
      class="fixed bottom-6 right-4 z-30 flex h-12 w-12 items-center justify-center rounded-full border border-gold-400/40 bg-felt-800 text-gold-300 shadow-gold lg:hidden"
      aria-label="打开聊天"
      @click="chatOpen = true"
    >
      <MessageSquare class="h-5 w-5" />
    </button>

    <div
      v-if="chatOpen"
      class="fixed inset-0 z-50 flex justify-end bg-felt-950/70 backdrop-blur-sm lg:hidden"
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

    <ResultModal
      v-if="showResult && game.result"
      :result="game.result"
      :seats="seats"
      :self-seat="selfSeat"
      @close="dismissedRound = game.result?.round_no ?? null"
      @next="nextRound"
    />

    <!-- 整场结束 -->
    <div
      v-if="game.finished"
      class="fixed inset-0 z-[65] flex items-center justify-center bg-felt-950/88 px-4 backdrop-blur"
    >
      <div class="w-full max-w-md animate-riseIn rounded-2xl border border-gold-400/30 bg-felt-900/95 p-6 text-center">
        <p class="text-[11px] tracking-[0.3em] text-gold-400/70">GAME OVER</p>
        <h2 class="mt-2 text-xl font-semibold text-cream-100">这场打完了</h2>
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

    <!-- 提醒：不限时 -->
    <div
      v-if="inGame && game.ruleBrief && !game.ruleBrief.turn_timeout.enabled"
      class="pointer-events-none fixed bottom-2 left-1/2 z-20 flex -translate-x-1/2 items-center gap-1.5 rounded-full border border-cream-100/10 bg-felt-950/80 px-3 py-1 text-[11px] text-ink-300/60"
    >
      <Timer class="h-3 w-3" />
      本局不限时，慢慢打
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

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { CalendarClock, ChartLine, ChevronRight, Loader2, Trophy } from 'lucide-vue-next'

import MobileNavBar from '../components/MobileNavBar.vue'
import MobileSheet from '../components/MobileSheet.vue'
import MobileTabBar from '../components/MobileTabBar.vue'
import Sparkline from '../../components/Sparkline.vue'
import Tile from '../../components/table/Tile.vue'
import { api } from '../../api/http'
import { useToast } from '../../composables/useToast'
import { useAuthStore } from '../../stores/auth'
import type { FinalHand, GameDetail, GameSummary, StatsInfo } from '../../types'
import { winTileRefOf } from '../../utils/finalHand'

/**
 * 手机版战绩：上面是我的总计与走势，下面是场次列表；
 * 点一场从底部抽屉展开逐局番种、分数变化与终局四家手牌（和 PC 明细同源）。
 */
const toast = useToast()
const auth = useAuthStore()

const games = ref<GameSummary[]>([])
const stats = ref<StatsInfo | null>(null)
const loading = ref(true)
const range = ref<'all' | '7' | '30'>('all')
const detail = ref<GameDetail | null>(null)
const detailOpen = ref(false)
const detailLoading = ref(false)

const familyCode = computed(() => auth.currentFamilyCode || '')
const familyQuery = computed(() =>
  familyCode.value ? `family_code=${encodeURIComponent(familyCode.value)}` : ''
)

async function load(): Promise<void> {
  if (!familyCode.value) {
    games.value = []
    stats.value = null
    loading.value = false
    return
  }
  loading.value = true
  try {
    const [list, stat] = await Promise.all([
      api.get<GameSummary[]>(`/history/games?limit=60&${familyQuery.value}`),
      api.get<StatsInfo>(`/history/stats?${familyQuery.value}`)
    ])
    games.value = list
    stats.value = stat
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    loading.value = false
  }
}

onMounted(load)

// 切家庭：战绩与统计整份重拉，明细抽屉一并关掉（避免看到别家的对局）
watch(familyCode, () => {
  detail.value = null
  detailOpen.value = false
  void load()
})

/** 客队场次：这场牌属于别的家庭（自己凭邀请码过去打的） */
function isGuestGame(game: GameSummary | GameDetail): boolean {
  return Boolean(game.family_code) && game.family_code !== familyCode.value
}

function guestFamilyName(game: GameSummary | GameDetail): string {
  return game.family_name || game.family_code || '其他家庭'
}

/**
 * 胡张落点（v1.1.0 · 04 §9.5）：优先用后端 `winning_tile_index`，
 * 旧局缺该字段时回退为「暗牌中最后一张同值牌」——与后端口径一致，不会指错牌。
 */
function winRef(hand: FinalHand) {
  return winTileRefOf(hand)
}

const STATUS_TEXT: Record<string, string> = {
  FINISHED: '已结束',
  ABORTED: '中断',
  PLAYING: '进行中',
  finished: '已结束',
  aborted: '中断',
  playing: '进行中'
}

function statusText(status: string): string {
  return STATUS_TEXT[status] || '进行中'
}

const filtered = computed(() => {
  if (range.value === 'all') return games.value
  const days = Number(range.value)
  const limit = Date.now() - days * 24 * 3600 * 1000
  return games.value.filter((game) => new Date(game.started_at).getTime() >= limit)
})

const trend = computed(() => {
  const ordered = [...filtered.value].reverse()
  let running = 0
  return ordered.map((game) => {
    running += game.my_score
    return running
  })
})

function fmt(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function winTypeText(type: string): string {
  return type === 'self_draw' ? '自摸' : type === 'discard' ? '点炮' : '荒庄'
}

async function openDetail(id: number): Promise<void> {
  detailOpen.value = true
  detailLoading.value = true
  try {
    detail.value = await api.get<GameDetail>(`/history/games/${id}`)
  } catch (error) {
    toast.error((error as Error).message)
    detailOpen.value = false
  } finally {
    detailLoading.value = false
  }
}

function closeDetail(): void {
  detailOpen.value = false
  detail.value = null
}
</script>

<template>
  <div class="mj-app mj-tabbar-hold mj-nav-hold">
    <MobileNavBar title="战绩与对账" :subtitle="`${auth.currentFamilyName} · 含在别人家打的客队场次`" />

    <main class="px-4 pt-4">
      <!-- 我的总计 -->
      <section class="mj-card px-4 py-3.5">
        <div class="mb-3 flex items-center gap-1.5">
          <Trophy class="h-4 w-4 text-gold-300" />
          <p class="text-[13px] font-medium text-gold-300">我的总计</p>
          <span class="ml-auto text-[10px] text-ink-300/50">含客队场次</span>
        </div>
        <div class="grid grid-cols-2 gap-2">
          <div class="mj-card-flat px-3 py-2.5">
            <p class="text-[10px] text-ink-300/65">累计积分</p>
            <p class="mt-1 font-num text-[20px] font-bold" :class="(stats?.total_score ?? 0) >= 0 ? 'text-jade-400' : 'text-vermilion-400'">
              {{ stats?.total_score ?? 0 }}
            </p>
          </div>
          <div class="mj-card-flat px-3 py-2.5">
            <p class="text-[10px] text-ink-300/65">参与场次</p>
            <p class="mt-1 font-num text-[20px] font-bold text-cream-100">{{ stats?.games_played ?? 0 }}</p>
          </div>
          <div class="mj-card-flat px-3 py-2.5">
            <p class="text-[10px] text-ink-300/65">最高单场</p>
            <p class="mt-1 font-num text-[20px] font-bold text-jade-400">{{ stats?.best_game ?? 0 }}</p>
          </div>
          <div class="mj-card-flat px-3 py-2.5">
            <p class="text-[10px] text-ink-300/65">胡牌局数</p>
            <p class="mt-1 font-num text-[20px] font-bold text-gold-300">{{ stats?.rounds_won ?? 0 }}</p>
          </div>
        </div>
      </section>

      <!-- 走势 -->
      <section class="mj-card mt-3 px-4 py-3.5">
        <p class="mb-1 flex items-center gap-1.5 text-[13px] font-medium text-gold-300">
          <ChartLine class="h-4 w-4" /> 积分走势
        </p>
        <p class="mb-2 text-[10px] text-ink-300/60">按时间累积，向右是最近的牌局</p>
        <div class="overflow-hidden">
          <Sparkline :values="trend.length ? trend : [0, 0]" :width="300" :height="64" class="h-auto w-full" />
        </div>
      </section>

      <!-- 场次列表 -->
      <section class="mt-4">
        <div class="mb-2 flex items-center gap-1.5">
          <CalendarClock class="h-4 w-4 text-gold-300" />
          <h2 class="text-[13px] font-medium text-cream-100">历史场次</h2>
          <div class="ml-auto flex gap-1">
            <button
              v-for="option in [
                { key: 'all', label: '全部' },
                { key: '30', label: '近 30 天' },
                { key: '7', label: '近 7 天' }
              ]"
              :key="option.key"
              type="button"
              class="rounded-full px-2.5 py-1 text-[11px]"
              :class="range === option.key ? 'bg-gold-400/15 text-gold-300' : 'text-ink-300/65'"
              @click="range = option.key as 'all' | '7' | '30'"
            >
              {{ option.label }}
            </button>
          </div>
        </div>

        <p v-if="loading" class="flex items-center justify-center gap-2 py-10 text-[13px] text-ink-300/60">
          <Loader2 class="h-4 w-4 animate-spin" /> 加载战绩…
        </p>
        <p v-else-if="!filtered.length" class="mj-card px-4 py-10 text-center text-[13px] text-ink-300/60">
          还没有打完的场次，先去打一局吧
        </p>

        <div v-else class="space-y-2.5">
          <button
            v-for="game in filtered"
            :key="game.id"
            type="button"
            class="mj-press mj-card flex w-full items-center gap-3 px-3.5 py-3 text-left"
            @click="openDetail(game.id)"
          >
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="truncate text-[13px] font-medium text-cream-100">{{ game.room_name }}</span>
                <span v-if="isGuestGame(game)" class="shrink-0 rounded border border-gold-400/25 bg-gold-400/[0.08] px-1 py-[1px] text-[9px] text-gold-300/90">
                  客队
                </span>
              </div>
              <p class="mt-0.5 text-[10px] text-ink-300/55">{{ fmt(game.started_at) }} · {{ statusText(game.status) }}</p>
              <div class="mt-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[10px] text-ink-300/75">
                <span v-for="player in game.players" :key="player.seat" class="flex items-center gap-1">
                  <span class="h-1.5 w-1.5 rounded-full" :style="{ backgroundColor: player.color }" />
                  {{ player.display_name }}
                  <span :class="player.total_score >= 0 ? 'text-jade-400' : 'text-vermilion-400'">
                    {{ player.total_score > 0 ? '+' : '' }}{{ player.total_score }}
                  </span>
                </span>
              </div>
            </div>
            <div class="shrink-0 text-right">
              <p class="font-num text-[17px] font-bold" :class="game.my_score >= 0 ? 'text-jade-400' : 'text-vermilion-400'">
                {{ game.my_score > 0 ? '+' : '' }}{{ game.my_score }}
              </p>
              <p class="text-[9px] text-ink-300/50">我的得分</p>
            </div>
            <ChevronRight class="h-4 w-4 shrink-0 text-ink-300/40" />
          </button>
        </div>
      </section>
    </main>

    <!-- 场次详情 -->
    <MobileSheet :open="detailOpen" :title="detail?.room_name || '场次明细'" max-height="90vh" @close="closeDetail">
      <p v-if="detailLoading" class="py-10 text-center text-[13px] text-ink-300/60">加载中…</p>

      <template v-else-if="detail">
        <p class="-mt-1 mb-3 text-[11px] text-ink-300/65">
          {{ fmt(detail.started_at) }} · {{ detail.rule_name }}
          <span v-if="isGuestGame(detail)" class="ml-1 rounded border border-gold-400/25 bg-gold-400/[0.08] px-1 py-[1px] text-[10px] text-gold-300/90">
            客队 · {{ guestFamilyName(detail) }}
          </span>
        </p>

        <div class="mb-3 grid grid-cols-2 gap-2">
          <div
            v-for="player in detail.players"
            :key="player.seat"
            class="mj-card-flat px-3 py-2"
          >
            <p class="truncate text-[11px]" :style="{ color: player.color }">{{ player.display_name }}</p>
            <p class="mt-0.5 font-num text-[17px] font-bold" :class="player.total_score >= 0 ? 'text-jade-400' : 'text-vermilion-400'">
              {{ player.total_score > 0 ? '+' : '' }}{{ player.total_score }}
            </p>
          </div>
        </div>

        <div
          v-if="detail.rule_snapshot"
          class="mb-3 rounded-xl border border-gold-400/20 bg-gold-400/[0.06] px-3 py-2 text-[10px] leading-relaxed text-gold-100/90"
        >
          本场规则：底分 {{ detail.rule_snapshot.base_score }} ·
          {{ detail.rule_snapshot.fan_mode === 'exponential' ? '2 的 N 次方' : '线性累加' }} ·
          {{ detail.rule_snapshot.turn_timeout.enabled ? `限时 ${detail.rule_snapshot.turn_timeout.seconds} 秒` : '不限时' }} ·
          {{ detail.rule_snapshot.kong_score.enabled ? '杠计分' : '杠不计分' }}
        </div>

        <div class="space-y-2">
          <div
            v-for="round in detail.rounds"
            :key="round.round_no"
            class="mj-card-flat px-3 py-2.5"
          >
            <div class="flex items-center justify-between gap-2">
              <p class="min-w-0 truncate text-[12px] text-cream-100">
                第 {{ round.round_no }} 局 ·
                <span v-if="round.winner_seat !== null">
                  {{ detail.players.find((p) => p.seat === round.winner_seat)?.display_name }}
                  {{ winTypeText(round.win_type) }}
                  <span v-if="round.winning_tile_name" class="text-ink-300/70">（{{ round.winning_tile_name }}）</span>
                </span>
                <span v-else class="text-ink-300/70">荒庄</span>
              </p>
              <p class="shrink-0 font-num text-[12px] text-gold-300">{{ round.fan_total }} 番</p>
            </div>

            <div class="mt-1.5 flex flex-wrap gap-1">
              <span
                v-for="item in round.fan_items"
                :key="item.id"
                class="rounded border border-gold-400/20 bg-gold-400/[0.08] px-1.5 py-0.5 text-[10px] text-gold-100/85"
              >
                {{ item.name }} +{{ item.fan * item.count }}
              </span>
            </div>

            <div v-if="round.final_hands?.length" class="mt-1.5 space-y-1 rounded-lg bg-felt-950/40 px-2 py-1.5">
              <p class="text-[9px] text-ink-300/55">终局手牌（点炮/抢杠的胡张已并入赢家手牌）</p>
              <div v-for="hand in round.final_hands" :key="hand.seat" class="flex flex-wrap items-center gap-0.5">
                <span class="w-[52px] shrink-0 truncate text-[9px]" :class="hand.is_winner ? 'text-gold-300' : 'text-ink-300/70'">
                  {{ hand.display_name }}
                </span>
                <Tile
                  v-for="(tile, tileIndex) in hand.concealed"
                  :key="`c-${tileIndex}`"
                  :tile="tile"
                  size="micro"
                  :win-tile="tileIndex === winRef(hand).concealedIndex"
                />
                <span v-for="(meld, meldIndex) in hand.melds" :key="`m-${meldIndex}`" class="ml-1 flex items-center gap-0.5">
                  <Tile
                    v-for="(tile, meldTileIndex) in meld.tiles"
                    :key="`mt-${meldIndex}-${meldTileIndex}`"
                    :tile="tile"
                    size="micro"
                    :mark="meld.claim_tile === tile"
                    :win-tile="meldIndex === winRef(hand).meldIndex && meldTileIndex === winRef(hand).meldTileIndex"
                  />
                </span>
              </div>
            </div>

            <div class="mt-1.5 flex flex-wrap gap-2 text-[10px]">
              <span
                v-for="(delta, index) in round.score_delta"
                :key="index"
                :class="delta >= 0 ? 'text-jade-400' : 'text-vermilion-400'"
              >
                {{ detail.players.find((p) => p.seat === index)?.display_name }}
                {{ delta > 0 ? '+' : '' }}{{ delta }}
              </span>
            </div>
          </div>
        </div>
      </template>
    </MobileSheet>

    <MobileTabBar />
  </div>
</template>

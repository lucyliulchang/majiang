<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { CalendarClock, ChartLine, Loader2, Trophy, X } from 'lucide-vue-next'

import AppHeader from '../components/AppHeader.vue'
import Sparkline from '../components/Sparkline.vue'
import Tile from '../components/table/Tile.vue'
import { api } from '../api/http'
import { useToast } from '../composables/useToast'
import { useAuthStore } from '../stores/auth'
import type { GameDetail, GameSummary, StatsInfo } from '../types'

const toast = useToast()
const auth = useAuthStore()

const games = ref<GameSummary[]>([])
const stats = ref<StatsInfo | null>(null)
const loading = ref(true)
const range = ref<'all' | '7' | '30'>('all')
const detail = ref<GameDetail | null>(null)
const detailLoading = ref(false)

const familyCode = computed(() => auth.currentFamilyCode || '')
const familyQuery = computed(() => (familyCode.value ? `family_code=${encodeURIComponent(familyCode.value)}` : ''))

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

/** 客队场次：这场牌属于别的家庭（自己凭邀请码过去打的） */
function isGuestGame(game: GameSummary | GameDetail): boolean {
  return Boolean(game.family_code) && game.family_code !== familyCode.value
}

function guestFamilyName(game: GameSummary | GameDetail): string {
  return game.family_name || game.family_code || '其他家庭'
}

// 切家庭：战绩与统计整份重拉，明细抽屉一并关掉（避免看到别家的对局）
watch(familyCode, () => {
  detail.value = null
  void load()
})

// 场次状态自 S5 起统一为大写（04 §7）
const STATUS_TEXT: Record<string, string> = {
  FINISHED: '已结束',
  ABORTED: '中断',
  PLAYING: '进行中',
  // 兼容旧数据
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

const fmt = (iso: string): string => {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const winTypeText = (type: string): string =>
  type === 'self_draw' ? '自摸' : type === 'discard' ? '点炮' : '荒庄'

async function openDetail(id: number): Promise<void> {
  detailLoading.value = true
  try {
    detail.value = await api.get<GameDetail>(`/history/games/${id}`)
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    detailLoading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen pb-16">
    <AppHeader />

    <main class="mx-auto max-w-[1400px] px-5 pt-24">
      <div class="mb-5">
        <p class="text-[11px] tracking-[0.32em] text-gold-400/70">HISTORY</p>
        <h1 class="mt-1 text-2xl font-semibold text-cream-100">战绩与对账</h1>
        <p class="mt-1 text-sm text-ink-300/80">
          {{ auth.currentFamilyName }} · 每局的番种、分数变化都留了底；在别人家打的客队场次也会一并列出。
        </p>
      </div>

      <div class="grid gap-4 lg:grid-cols-[320px_1fr]">
        <div class="space-y-4">
          <div class="glass rounded-2xl p-4">
            <p class="mb-1 flex items-center gap-1.5 text-sm font-medium text-gold-300">
              <Trophy class="h-4 w-4" /> 我的总计
            </p>
            <p class="mb-3 text-[10px] text-ink-300/55">统计口径：我参与的全部场次（含客队场次）</p>
            <div class="grid grid-cols-2 gap-2.5">
              <div class="rounded-xl border border-cream-100/10 bg-cream-100/[0.03] px-3 py-2.5">
                <p class="text-[11px] text-ink-300/70">累计积分</p>
                <p class="mt-1 font-num text-xl font-bold" :class="(stats?.total_score ?? 0) >= 0 ? 'text-jade-400' : 'text-vermilion-400'">
                  {{ stats?.total_score ?? 0 }}
                </p>
              </div>
              <div class="rounded-xl border border-cream-100/10 bg-cream-100/[0.03] px-3 py-2.5">
                <p class="text-[11px] text-ink-300/70">参与场次</p>
                <p class="mt-1 font-num text-xl font-bold text-cream-100">{{ stats?.games_played ?? 0 }}</p>
              </div>
              <div class="rounded-xl border border-cream-100/10 bg-cream-100/[0.03] px-3 py-2.5">
                <p class="text-[11px] text-ink-300/70">最高单场</p>
                <p class="mt-1 font-num text-xl font-bold text-jade-400">{{ stats?.best_game ?? 0 }}</p>
              </div>
              <div class="rounded-xl border border-cream-100/10 bg-cream-100/[0.03] px-3 py-2.5">
                <p class="text-[11px] text-ink-300/70">胡牌局数</p>
                <p class="mt-1 font-num text-xl font-bold text-gold-300">{{ stats?.rounds_won ?? 0 }}</p>
              </div>
            </div>
          </div>

          <div class="glass rounded-2xl p-4">
            <p class="mb-2 flex items-center gap-1.5 text-sm font-medium text-gold-300">
              <ChartLine class="h-4 w-4" /> 积分走势
            </p>
            <p class="mb-2 text-[11px] text-ink-300/60">按时间累积，向右是最近的牌局</p>
            <Sparkline :values="trend.length ? trend : [0, 0]" :width="272" :height="70" />
          </div>
        </div>

        <div class="glass rounded-2xl p-4">
          <div class="mb-3 flex flex-wrap items-center gap-2">
            <p class="flex items-center gap-1.5 text-sm font-medium text-cream-100">
              <CalendarClock class="h-4 w-4 text-gold-300" />
              历史场次
            </p>
            <div class="ml-auto flex gap-1">
              <button
                v-for="option in [
                  { key: 'all', label: '全部' },
                  { key: '30', label: '近 30 天' },
                  { key: '7', label: '近 7 天' }
                ]"
                :key="option.key"
                type="button"
                class="rounded-lg px-2.5 py-1 text-xs transition"
                :class="range === option.key ? 'bg-gold-400/15 text-gold-300' : 'text-ink-300/70 hover:text-cream-100'"
                @click="range = option.key as 'all' | '7' | '30'"
              >
                {{ option.label }}
              </button>
            </div>
          </div>

          <p v-if="loading" class="flex items-center gap-2 py-10 text-sm text-ink-300/60">
            <Loader2 class="h-4 w-4 animate-spin" /> 加载战绩…
          </p>
          <p v-else-if="!filtered.length" class="py-12 text-center text-sm text-ink-300/60">
            还没有打完的场次，先去打一局吧
          </p>

          <div v-else class="space-y-2">
            <button
              v-for="game in filtered"
              :key="game.id"
              type="button"
              class="flex w-full flex-wrap items-center gap-3 rounded-xl border border-cream-100/10 bg-cream-100/[0.02] px-3.5 py-2.5 text-left transition hover:border-gold-400/35 hover:bg-gold-400/[0.05]"
              @click="openDetail(game.id)"
            >
              <div class="min-w-[120px]">
                <p class="text-xs text-cream-100">{{ game.room_name }}</p>
                <p class="text-[11px] text-ink-300/60">{{ fmt(game.started_at) }}</p>
                <span
                  v-if="isGuestGame(game)"
                  class="mt-1 inline-block rounded border border-gold-400/25 bg-gold-400/[0.08] px-1 py-[1px] text-[10px] leading-tight text-gold-300/90"
                >
                  客队 · {{ guestFamilyName(game) }}
                </span>
              </div>
              <div class="flex flex-1 flex-wrap items-center gap-1.5">
                <span
                  v-for="player in game.players"
                  :key="player.seat"
                  class="flex items-center gap-1 rounded-full border border-cream-100/10 px-1.5 py-0.5 text-[11px] text-ink-300/85"
                >
                  <span class="h-2 w-2 rounded-full" :style="{ backgroundColor: player.color }" />
                  {{ player.display_name }}
                  <span :class="player.total_score >= 0 ? 'text-jade-400' : 'text-vermilion-400'">
                    {{ player.total_score > 0 ? '+' : '' }}{{ player.total_score }}
                  </span>
                </span>
              </div>
              <div class="text-right">
                <p class="font-num text-base font-bold" :class="game.my_score >= 0 ? 'text-jade-400' : 'text-vermilion-400'">
                  {{ game.my_score > 0 ? '+' : '' }}{{ game.my_score }}
                </p>
                <p class="text-[10px] text-ink-300/50">{{ statusText(game.status) }}</p>
              </div>
            </button>
          </div>
        </div>
      </div>
    </main>

    <!-- 场次详情 -->
    <div v-if="detail || detailLoading" class="fixed inset-0 z-[60] flex justify-end bg-felt-950/75 backdrop-blur-sm" @click.self="detail = null">
      <div class="h-full w-full max-w-xl overflow-y-auto border-l border-gold-400/20 bg-felt-900/95 p-5">
        <div class="mb-4 flex items-start justify-between">
          <div>
            <p class="text-[11px] tracking-[0.28em] text-gold-400/70">場次明細</p>
            <h2 class="mt-1 text-lg font-semibold text-cream-100">{{ detail?.room_name || '加载中…' }}</h2>
            <p class="text-xs text-ink-300/70">
              {{ detail ? fmt(detail.started_at) : '' }} · {{ detail?.rule_name }}
              <span
                v-if="detail && isGuestGame(detail)"
                class="ml-1 rounded border border-gold-400/25 bg-gold-400/[0.08] px-1 py-[1px] text-[10px] text-gold-300/90"
              >
                客队 · {{ guestFamilyName(detail) }}
              </span>
            </p>
          </div>
          <button type="button" class="btn-ghost rounded-lg p-2" @click="detail = null">
            <X class="h-4 w-4" />
          </button>
        </div>

        <p v-if="detailLoading" class="py-10 text-center text-sm text-ink-300/60">加载中…</p>

        <template v-else-if="detail">
          <div class="mb-4 grid grid-cols-2 gap-2">
            <div
              v-for="player in detail.players"
              :key="player.seat"
              class="rounded-xl border border-cream-100/10 bg-cream-100/[0.03] px-3 py-2"
            >
              <p class="text-xs" :style="{ color: player.color }">{{ player.display_name }}</p>
              <p class="mt-0.5 font-num text-lg font-bold" :class="player.total_score >= 0 ? 'text-jade-400' : 'text-vermilion-400'">
                {{ player.total_score > 0 ? '+' : '' }}{{ player.total_score }}
              </p>
            </div>
          </div>

          <div
            v-if="detail.rule_snapshot"
            class="mb-4 rounded-xl border border-gold-400/20 bg-gold-400/[0.06] px-3 py-2 text-[11px] leading-relaxed text-gold-100/90"
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
              class="rounded-xl border border-cream-100/10 bg-cream-100/[0.02] px-3 py-2.5"
            >
              <div class="flex items-center justify-between">
                <p class="text-xs text-cream-100">
                  第 {{ round.round_no }} 局 ·
                  <span v-if="round.winner_seat !== null">
                    {{ detail.players.find((p) => p.seat === round.winner_seat)?.display_name }}
                    {{ winTypeText(round.win_type) }}
                    <span v-if="round.winning_tile_name" class="text-ink-300/70">（{{ round.winning_tile_name }}）</span>
                  </span>
                  <span v-else class="text-ink-300/70">荒庄</span>
                </p>
                <p class="font-num text-sm text-gold-300">{{ round.fan_total }} 番</p>
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
                <p class="text-[10px] text-ink-300/60">终局手牌（点炮/抢杠的胡张已并入赢家手牌）</p>
                <div
                  v-for="hand in round.final_hands"
                  :key="hand.seat"
                  class="flex flex-wrap items-center gap-0.5"
                >
                  <span
                    class="w-14 shrink-0 truncate text-[10px]"
                    :class="hand.is_winner ? 'text-gold-300' : 'text-ink-300/70'"
                  >
                    {{ hand.display_name }}
                  </span>
                  <Tile v-for="(tile, tileIndex) in hand.concealed" :key="`c-${tileIndex}`" :tile="tile" size="xs" />
                  <span
                    v-for="(meld, meldIndex) in hand.melds"
                    :key="`m-${meldIndex}`"
                    class="ml-1 flex items-center gap-0.5"
                  >
                    <Tile
                      v-for="(tile, meldTileIndex) in meld.tiles"
                      :key="`mt-${meldIndex}-${meldTileIndex}`"
                      :tile="tile"
                      size="xs"
                      :mark="meld.claim_tile === tile"
                    />
                  </span>
                </div>
              </div>
              <div class="mt-1.5 flex flex-wrap gap-2 text-[11px]">
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
      </div>
    </div>
  </div>
</template>

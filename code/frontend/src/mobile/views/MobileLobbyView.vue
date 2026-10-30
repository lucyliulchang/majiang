<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  BookOpen,
  Check,
  ChevronRight,
  History,
  Loader2,
  Plus,
  Sparkles,
  Trophy,
  Users,
  X
} from 'lucide-vue-next'

import DesktopOnlySheet from '../components/DesktopOnlySheet.vue'
import JoinCodeInput from '../components/JoinCodeInput.vue'
import MobileCreateRoomSheet from '../components/MobileCreateRoomSheet.vue'
import MobileNavBar from '../components/MobileNavBar.vue'
import MobileSheet from '../components/MobileSheet.vue'
import MobileTabBar from '../components/MobileTabBar.vue'
import { api } from '../../api/http'
import { useToast } from '../../composables/useToast'
import { useAuthStore } from '../../stores/auth'
import { useFamiliesStore } from '../../stores/families'
import type { RoomInfo, RoomJoinCheck, StatsInfo } from '../../types'

/**
 * 手机版大厅：一屏看全「我现在能干什么」——
 * 上面是我的战绩摘要与家庭切换，中间是本家庭进行中的牌桌，
 * 下面是邀请码入座，主操作「创建牌桌」固定在底部拇指区。
 */
const router = useRouter()
const auth = useAuthStore()
const families = useFamiliesStore()
const toast = useToast()

const rooms = ref<RoomInfo[]>([])
const stats = ref<StatsInfo | null>(null)
const loading = ref(true)
const createOpen = ref(false)
const familyOpen = ref(false)
const pcOpen = ref(false)
const pcFeature = ref('规则模板')
const checking = ref(false)
const codeError = ref('')
const switching = ref(false)
const closingId = ref<number | null>(null)
const closing = ref(false)
const codeInput = ref<InstanceType<typeof JoinCodeInput> | null>(null)

const familyCode = computed(() => auth.currentFamilyCode || '')

function familyQuery(): string {
  return familyCode.value ? `?family_code=${encodeURIComponent(familyCode.value)}` : ''
}

/**
 * 拉大厅数据。`silent=true` 用于自动刷新：不显示骨架、不弹错误，避免每 30s 打扰一次。
 */
async function load(silent = false): Promise<void> {
  // 家庭未就绪时不发请求：避免用「上一个家庭」的空参数拿到别人的数据
  if (!familyCode.value) {
    rooms.value = []
    stats.value = null
    loading.value = false
    return
  }
  if (!silent) loading.value = true
  try {
    const [roomList, stat] = await Promise.all([
      api.get<RoomInfo[]>(`/rooms${familyQuery()}`),
      api.get<StatsInfo>(`/history/stats${familyQuery()}`)
    ])
    rooms.value = roomList
    stats.value = stat
  } catch (error) {
    if (!silent) toast.error((error as Error).message)
  } finally {
    if (!silent) loading.value = false
  }
}

// ---- 大厅自愈（B-1）：切回前台立刻刷新 + 每 30s 轮询，别人关掉的牌桌不会再挂着 ----
const POLL_INTERVAL_MS = 30000
let pollTimer: number | undefined

function onVisibilityChange(): void {
  if (document.visibilityState === 'visible') void load(true)
}

function stopAutoRefresh(): void {
  if (pollTimer !== undefined) {
    window.clearInterval(pollTimer)
    pollTimer = undefined
  }
  document.removeEventListener('visibilitychange', onVisibilityChange)
}

onMounted(() => {
  void load()
  pollTimer = window.setInterval(() => void load(true), POLL_INTERVAL_MS)
  document.addEventListener('visibilitychange', onVisibilityChange)
})

onBeforeUnmount(stopAutoRefresh)

// 切家庭：大厅数据整份重拉，任何旧列表都不保留（无缓存串数据）
watch(familyCode, () => {
  codeError.value = ''
  codeInput.value?.reset()
  void load()
})

async function pickFamily(code: string): Promise<void> {
  familyOpen.value = false
  if (code === familyCode.value) return
  switching.value = true
  try {
    await families.switchTo(code)
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    switching.value = false
  }
}

async function joinByCode(code: string): Promise<void> {
  codeError.value = ''
  if (code.length !== 6 || checking.value) return
  checking.value = true
  try {
    const info = await api.get<RoomJoinCheck>(`/rooms/code/${code}`)
    if (!info.can_join && !info.spectate.available) {
      codeError.value = '牌桌满了，围观位也满了，稍后再试'
      codeInput.value?.reset()
      return
    }
    if (!info.can_join) toast.info(`座位已满，将以观战身份进入（可围观 ${info.spectate.limit_per_seat * 4} 人）`)
    if (info.needs_approval) toast.info('这是别人家的牌桌，进桌要等房主同意')
    await router.push({ name: 'room', params: { code: info.room_code } })
  } catch (error) {
    codeError.value = (error as Error).message
    codeInput.value?.reset()
  } finally {
    checking.value = false
  }
}

function enterRoom(room: RoomInfo): void {
  void router.push({ name: 'room', params: { code: room.room_code } })
}

function onCreated(room: RoomInfo): void {
  createOpen.value = false
  void router.push({ name: 'room', params: { code: room.room_code } })
}

function openPc(feature: string): void {
  pcFeature.value = feature
  pcOpen.value = true
}

async function doClose(room: RoomInfo): Promise<void> {
  if (closing.value) return
  closing.value = true
  try {
    await api.post<RoomInfo>(`/rooms/${room.id}/close`, {})
    rooms.value = rooms.value.filter((item) => item.id !== room.id)
    closingId.value = null
    toast.success(`已关闭「${room.room_name}」`)
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    closing.value = false
  }
}
</script>

<template>
  <div class="mj-app mj-nav-hold mj-cta-hold">
    <MobileNavBar title="大厅" :subtitle="`${auth.currentFamilyName} · ${rooms.length} 桌等你入座`">
      <template #right>
        <button
          type="button"
          class="mj-press flex h-10 max-w-[132px] items-center gap-1.5 rounded-full border border-family/40 bg-family/10 pl-1 pr-2.5"
          @click="familyOpen = true"
        >
          <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-family text-[11px] font-semibold text-felt-950">
            {{ switching ? '…' : (auth.currentFamilyName || '家').slice(0, 1) }}
          </span>
          <span class="truncate text-[12px] text-cream-100/90">{{ auth.currentFamilyName }}</span>
          <ChevronRight class="h-3.5 w-3.5 shrink-0 text-ink-300/70" />
        </button>
      </template>
    </MobileNavBar>

    <main class="px-4 pt-4">
      <!-- 问候 + 战绩摘要 -->
      <section class="mj-card px-4 py-3.5">
        <p class="text-[11px] tracking-[0.3em] text-gold-400/70">LOBBY</p>
        <h1 class="mt-1 truncate text-[22px] font-semibold leading-tight text-cream-100">
          {{ auth.displayName }}，来一局？
        </h1>
        <div class="mt-3 grid grid-cols-3 gap-2 text-center">
          <div class="mj-card-flat px-1 py-2">
            <p class="font-num text-[18px] font-bold" :class="(stats?.total_score ?? 0) >= 0 ? 'text-jade-400' : 'text-vermilion-400'">
              {{ stats?.total_score ?? 0 }}
            </p>
            <p class="mt-0.5 text-[10px] text-ink-300/65">累计积分</p>
          </div>
          <div class="mj-card-flat px-1 py-2">
            <p class="font-num text-[18px] font-bold text-cream-100">{{ stats?.games_played ?? 0 }}</p>
            <p class="mt-0.5 text-[10px] text-ink-300/65">打过场次</p>
          </div>
          <div class="mj-card-flat px-1 py-2">
            <p class="font-num text-[18px] font-bold text-gold-300">{{ stats?.rounds_won ?? 0 }}</p>
            <p class="mt-0.5 text-[10px] text-ink-300/65">胡牌局数</p>
          </div>
        </div>
      </section>

      <!-- 进行中的牌桌 -->
      <section class="mt-4">
        <div class="mb-2 flex items-center gap-1.5">
          <Trophy class="h-4 w-4 text-gold-300" />
          <h2 class="text-[13px] font-medium text-cream-100">家里的牌桌</h2>
          <span class="text-[11px] text-ink-300/60">点开就能接着打</span>
        </div>

        <p v-if="loading" class="flex items-center justify-center gap-2 py-8 text-[13px] text-ink-300/60">
          <Loader2 class="h-4 w-4 animate-spin" /> 加载中…
        </p>

        <div v-else-if="!rooms.length" class="mj-card px-4 py-8 text-center">
          <div class="mb-3 flex justify-center gap-1.5 opacity-45">
            <div class="h-11 w-7 rounded-md border border-gold-400/30" />
            <div class="h-11 w-7 rounded-md border border-gold-400/30" />
            <div class="h-11 w-7 rounded-md border border-gold-400/30" />
          </div>
          <p class="text-[13px] text-ink-300/70">还没有牌桌，开一桌吧</p>
        </div>

        <div v-else class="space-y-2.5">
          <article
            v-for="room in rooms"
            :key="room.id"
            class="mj-card overflow-hidden"
          >
            <button type="button" class="mj-press flex w-full items-start gap-3 px-3.5 py-3 text-left" @click="enterRoom(room)">
              <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gold-400/10 text-gold-300">
                <Sparkles class="h-5 w-5" />
              </span>
              <span class="min-w-0 flex-1">
                <span class="flex items-center gap-2">
                  <span class="truncate text-[14px] font-medium text-cream-100">{{ room.room_name }}</span>
                  <span class="shrink-0 rounded bg-felt-950/60 px-1.5 py-0.5 font-mono text-[10px] tracking-[0.14em] text-gold-300">
                    {{ room.room_code }}
                  </span>
                </span>
                <span class="mt-1 flex items-center gap-1.5 text-[11px] text-ink-300/70">
                  <span class="badge-rule">{{ room.rule_family_code }}</span>
                  <span class="truncate">{{ room.rule_name }}</span>
                </span>
                <span class="mt-1.5 flex items-center gap-2.5 text-[11px] text-ink-300/60">
                  <span class="flex items-center gap-1"><Users class="h-3 w-3" />{{ room.player_count }} / 4</span>
                  <span v-if="room.spectator_count">{{ room.spectator_count }} 人围观</span>
                  <span>{{ room.status === 'OPEN' ? '等待开局' : '已关闭' }}</span>
                </span>
              </span>
              <ChevronRight class="mt-1 h-4 w-4 shrink-0 text-ink-300/50" />
            </button>

            <!-- 房主可以直接在大厅收桌，不必先进屋 -->
            <div v-if="room.host_login_id === auth.loginId" class="border-t border-cream-100/10 px-3.5 py-2">
              <div v-if="closingId === room.id" class="flex items-center gap-2 text-[11px]">
                <span class="text-cream-100">关闭这桌？大厅不再显示</span>
                <button
                  type="button"
                  class="ml-auto shrink-0 rounded-lg bg-vermilion-500 px-2.5 py-1 font-semibold text-cream-50 disabled:opacity-60"
                  :disabled="closing"
                  @click="doClose(room)"
                >
                  关闭
                </button>
                <button type="button" class="shrink-0 rounded-lg px-2 py-1 text-ink-300/70" @click="closingId = null">
                  取消
                </button>
              </div>
              <button
                v-else
                type="button"
                class="flex items-center gap-1 text-[11px] text-ink-300/55"
                @click="closingId = room.id"
              >
                <X class="h-3 w-3" />
                我是房主，关闭这桌
              </button>
            </div>
          </article>
        </div>
      </section>

      <!-- 邀请码入座 -->
      <section class="mj-card mt-4 px-4 py-4">
        <div class="mb-1 flex items-center gap-1.5">
          <Sparkles class="h-4 w-4 text-gold-300" />
          <h2 class="text-[13px] font-medium text-cream-100">用邀请码入座</h2>
        </div>
        <p class="mb-3 text-[11px] leading-relaxed text-ink-300/70">
          问一下开桌的家人，输满 6 位数字会自动进桌；长按第一格可以直接粘贴整串。
        </p>
        <JoinCodeInput ref="codeInput" :disabled="checking" :error="codeError" @complete="joinByCode" />
        <p v-if="checking" class="mt-2 flex items-center gap-1.5 text-[11px] text-ink-300/70">
          <Loader2 class="h-3.5 w-3.5 animate-spin" /> 正在找这桌…
        </p>
      </section>

      <!-- 快捷入口 -->
      <section class="mt-4 space-y-2">
        <button
          type="button"
          class="mj-press mj-card-flat flex w-full items-center gap-3 px-3.5 py-3 text-left"
          @click="router.push({ name: 'history' })"
        >
          <History class="h-4 w-4 shrink-0 text-gold-300" />
          <span class="min-w-0 flex-1">
            <span class="block text-[13px] text-cream-100">历史战绩</span>
            <span class="block text-[11px] text-ink-300/60">每局明细与终局手牌</span>
          </span>
          <ChevronRight class="h-4 w-4 shrink-0 text-ink-300/50" />
        </button>

        <button
          type="button"
          class="mj-press mj-card-flat flex w-full items-center gap-3 px-3.5 py-3 text-left"
          @click="openPc('规则模板')"
        >
          <BookOpen class="h-4 w-4 shrink-0 text-gold-300" />
          <span class="min-w-0 flex-1">
            <span class="block text-[13px] text-cream-100">规则模板</span>
            <span class="block text-[11px] text-ink-300/60">底分、番种、杠分在电脑版调</span>
          </span>
          <span class="shrink-0 rounded-full border border-cream-100/15 px-2 py-0.5 text-[10px] text-ink-300/60">PC</span>
        </button>

        <button
          type="button"
          class="mj-press mj-card-flat flex w-full items-center gap-3 px-3.5 py-3 text-left"
          @click="router.push({ name: 'families' })"
        >
          <Users class="h-4 w-4 shrink-0 text-gold-300" />
          <span class="min-w-0 flex-1">
            <span class="block text-[13px] text-cream-100">我的家庭</span>
            <span class="block text-[11px] text-ink-300/60">{{ auth.families.length }} 个家庭 · 可切换</span>
          </span>
          <ChevronRight class="h-4 w-4 shrink-0 text-ink-300/50" />
        </button>
      </section>
    </main>

    <div class="mj-cta-bar">
      <button
        type="button"
        class="mj-press btn-gold flex min-h-[48px] w-full items-center justify-center gap-2 rounded-xl text-[15px] font-semibold"
        @click="createOpen = true"
      >
        <Plus class="h-4 w-4" />
        创建牌桌
      </button>
    </div>

    <MobileCreateRoomSheet :open="createOpen" @close="createOpen = false" @created="onCreated" />

    <!-- 家庭切换 -->
    <MobileSheet
      :open="familyOpen"
      title="切换家庭"
      subtitle="大厅牌桌、战绩与皮肤都按当前家庭区分"
      @close="familyOpen = false"
    >
      <div class="space-y-2 pt-1">
        <button
          v-for="family in auth.families"
          :key="family.family_code"
          type="button"
          class="mj-press flex w-full items-center gap-2.5 rounded-xl border px-3 py-2.5 text-left"
          :class="
            family.family_code === familyCode
              ? 'border-gold-400/50 bg-gold-400/10'
              : 'border-cream-100/10 bg-cream-100/[0.03]'
          "
          @click="pickFamily(family.family_code)"
        >
          <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-family text-[11px] font-semibold text-felt-950">
            {{ (family.family_name || '家').slice(0, 1) }}
          </span>
          <span class="min-w-0 flex-1">
            <span class="block truncate text-[13px] text-cream-100">{{ family.family_name }}</span>
            <span class="block truncate font-mono text-[10px] text-ink-300/60">{{ family.family_code }}</span>
          </span>
          <Check v-if="family.family_code === familyCode" class="h-4 w-4 shrink-0 text-gold-300" />
        </button>

        <button
          type="button"
          class="mj-press btn-ghost mt-1 flex min-h-[44px] w-full items-center justify-center gap-1.5 rounded-xl text-[13px]"
          @click="familyOpen = false; router.push({ name: 'families' })"
        >
          <Plus class="h-4 w-4" />
          新建 / 管理家庭
        </button>
      </div>
    </MobileSheet>

    <DesktopOnlySheet
      :open="pcOpen"
      :feature="pcFeature"
      desc="规则模板要逐项填底分、番表、杠分与封顶，电脑上一屏能对着看，改完还能立刻试算。"
      @close="pcOpen = false"
    />

    <MobileTabBar />
  </div>
</template>

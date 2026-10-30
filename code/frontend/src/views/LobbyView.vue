<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { BookOpen, History, Palette, Plus, Sparkles, Trophy, Users, X } from 'lucide-vue-next'

import AppHeader from '../components/AppHeader.vue'
import CreateRoomDialog from '../components/CreateRoomDialog.vue'
import { api } from '../api/http'
import { useToast } from '../composables/useToast'
import { useAuthStore } from '../stores/auth'
import { useFamiliesStore } from '../stores/families'
import type { RoomInfo, RoomJoinCheck, StatsInfo } from '../types'

const router = useRouter()
const auth = useAuthStore()
const families = useFamiliesStore()
const toast = useToast()

const rooms = ref<RoomInfo[]>([])
const stats = ref<StatsInfo | null>(null)
const loading = ref(true)
const creating = ref(false)
const digits = ref<string[]>(['', '', '', '', '', ''])
const checking = ref(false)
const codeError = ref('')
const inputs = ref<HTMLInputElement[]>([])
const switching = ref(false)

const code = computed(() => digits.value.join(''))
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
  digits.value = ['', '', '', '', '', '']
  codeError.value = ''
  void load()
})

async function pickFamily(next: string): Promise<void> {
  if (next === familyCode.value) return
  switching.value = true
  try {
    await families.switchTo(next)
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    switching.value = false
  }
}

function setInputRef(element: Element | null, index: number): void {
  if (element) inputs.value[index] = element as HTMLInputElement
}

/** 只保留数字：粘贴/输入法/自动填充都可能带进非数字（验收：粘贴非法字符被过滤） */
function onlyDigits(text: string): string {
  return (text || '').replace(/\D/g, '')
}

function fillFrom(index: number, raw: string): void {
  const cleaned = onlyDigits(raw)
  if (!cleaned) {
    digits.value[index] = ''
    return
  }
  let cursor = index
  for (const char of cleaned) {
    if (cursor > 5) break
    digits.value[cursor] = char
    cursor += 1
  }
  const focusIndex = Math.min(cursor, 5)
  void nextTick(() => inputs.value[focusIndex]?.focus())
  if (code.value.length === 6) void join()
}

function onInput(index: number, event: Event): void {
  const target = event.target as HTMLInputElement
  const cleaned = onlyDigits(target.value)
  target.value = ''
  fillFrom(index, cleaned)
}

function onPaste(index: number, event: ClipboardEvent): void {
  const text = event.clipboardData?.getData('text') || ''
  if (!text) return
  event.preventDefault()
  // 粘贴整串：从第 1 格开始覆盖，符合「一次贴完 6 位」的直觉
  const cleaned = onlyDigits(text)
  if (cleaned.length > 1) {
    digits.value = ['', '', '', '', '', '']
    fillFrom(0, cleaned)
  } else {
    fillFrom(index, cleaned)
  }
}

function onKeydown(index: number, event: KeyboardEvent): void {
  if (event.key === 'Backspace' && !digits.value[index] && index > 0) {
    inputs.value[index - 1]?.focus()
  }
  if (event.key === 'ArrowLeft' && index > 0) inputs.value[index - 1]?.focus()
  if (event.key === 'ArrowRight' && index < 5) inputs.value[index + 1]?.focus()
}

async function join(): Promise<void> {
  codeError.value = ''
  if (code.value.length !== 6) {
    codeError.value = '邀请码是 6 位数字'
    return
  }
  checking.value = true
  try {
    const info = await api.get<RoomJoinCheck>(`/rooms/code/${code.value}`)
    if (!info.can_join && !info.spectate.available) {
      codeError.value = '牌桌满了，围观位也满了，稍后再试'
      toast.warn('牌桌满了，围观位也满了，稍后再试')
      return
    }
    if (!info.can_join) {
      toast.info(`座位已满，将以观战身份进入（可围观 ${info.spectate.limit_per_seat * 4} 人）`)
    }
    if (info.needs_approval) {
      // 不是本家庭的牌桌：先进等候页，房主在牌桌上点头后才真正进桌（S10）
      toast.info('这是别人家的牌桌，进桌要等房主同意')
    }
    router.push({ name: 'room', params: { code: info.room_code } })
  } catch (error) {
    codeError.value = (error as Error).message
    digits.value = ['', '', '', '', '', '']
    void nextTick(() => inputs.value[0]?.focus())
  } finally {
    checking.value = false
  }
}

function onCreated(room: RoomInfo): void {
  creating.value = false
  router.push({ name: 'room', params: { code: room.room_code } })
}

function enterRoom(room: RoomInfo): void {
  router.push({ name: 'room', params: { code: room.room_code } })
}

// ---- 收桌：房主可以不进屋，直接在大厅关掉自己开的桌（列表只列 OPEN）----
const closingId = ref<number | null>(null)
const closing = ref(false)

function askClose(room: RoomInfo): void {
  closingId.value = closingId.value === room.id ? null : room.id
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

const quickLinks = computed(() => {
  const links = [
    { key: 'rules', label: '我的规则模板', desc: '底分、番种、杠分都在这里调', icon: BookOpen, to: 'rules' },
    { key: 'history', label: '历史战绩', desc: '每局明细，随时对账', icon: History, to: 'history' },
    { key: 'families', label: '家庭成员', desc: '按手机号加人、看角色', icon: Users, to: 'families' }
  ]
  if (auth.canManageSkins) {
    links.splice(2, 0, { key: 'skins', label: '皮肤管理', desc: '上传 35 张牌面，一键换肤', icon: Palette, to: 'skins' })
  }
  return links
})
</script>

<template>
  <div class="min-h-screen pb-16">
    <AppHeader />

    <main class="mx-auto max-w-[1400px] px-4 pt-24 sm:px-5">
      <div class="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div class="min-w-0">
          <p class="text-[11px] tracking-[0.32em] text-gold-400/70">LOBBY</p>
          <h1 class="mt-1 truncate text-2xl font-semibold text-cream-100">
            {{ auth.displayName }}，来一局？
          </h1>
          <p class="mt-1 text-sm text-ink-300/80">
            {{ auth.currentFamilyName }} · 累计积分
            <span class="font-num text-base text-gold-300">{{ stats?.total_score ?? 0 }}</span>
            · 打过 {{ stats?.games_played ?? 0 }} 场 · 赢过 {{ stats?.rounds_won ?? 0 }} 局
          </p>
        </div>
        <button type="button" class="btn-gold flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold" @click="creating = true">
          <Plus class="h-4 w-4" />
          创建牌桌
        </button>
      </div>

      <!-- 家庭筛选：当前家庭下的牌桌/战绩；切换即重拉 -->
      <div class="mb-5 flex flex-wrap items-center gap-2">
        <span class="text-[11px] tracking-[0.2em] text-ink-300/60">家庭</span>
        <button
          v-for="family in auth.families"
          :key="family.family_code"
          type="button"
          class="badge-family transition"
          :class="
            family.family_code === familyCode
              ? 'border-family bg-family/25 text-cream-50'
              : 'opacity-70 hover:opacity-100'
          "
          :disabled="switching"
          @click="pickFamily(family.family_code)"
        >
          {{ family.family_name }}
        </button>
        <router-link to="/families" class="text-[11px] text-gold-300/80 transition hover:text-gold-300">
          + 新建 / 管理
        </router-link>
      </div>

      <div class="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
        <!-- 我的房间 -->
        <section class="glass rounded-2xl p-4 sm:p-5">
          <div class="mb-4 flex items-center gap-2">
            <Trophy class="h-4 w-4 text-gold-300" />
            <h2 class="text-sm font-medium text-cream-100">家里的牌桌</h2>
            <span class="text-[11px] text-ink-300/60">本家庭进行中的桌，点开就能接着打</span>
          </div>

          <p v-if="loading" class="py-10 text-center text-sm text-ink-300/60">加载中…</p>

          <div v-else-if="!rooms.length" class="flex flex-col items-center gap-3 py-12">
            <div class="flex gap-1.5 opacity-50">
              <div class="h-12 w-8 rounded-md border border-gold-400/30" />
              <div class="h-12 w-8 rounded-md border border-gold-400/30" />
              <div class="h-12 w-8 rounded-md border border-gold-400/30" />
            </div>
            <p class="text-sm text-ink-300/70">还没有牌桌，开一桌吧</p>
            <button type="button" class="btn-gold rounded-lg px-4 py-2 text-sm font-semibold" @click="creating = true">
              创建牌桌
            </button>
          </div>

          <div v-else class="grid gap-2.5 sm:grid-cols-2">
            <div
              v-for="room in rooms"
              :key="room.id"
              class="group cursor-pointer rounded-xl border border-cream-100/12 bg-cream-100/[0.03] p-3.5 text-left transition hover:border-gold-400/40 hover:bg-gold-400/[0.06]"
              role="button"
              tabindex="0"
              @click="enterRoom(room)"
              @keydown.enter="enterRoom(room)"
            >
              <div class="flex items-start justify-between gap-2">
                <span class="truncate text-sm font-medium text-cream-100">{{ room.room_name }}</span>
                <span class="flex shrink-0 items-center gap-1">
                  <span class="rounded bg-felt-950/60 px-1.5 py-0.5 font-mono text-[10px] tracking-[0.16em] text-gold-300">
                    {{ room.room_code }}
                  </span>
                  <!-- 房主可以在大厅直接收桌，不必先进屋 -->
                  <button
                    v-if="room.host_login_id === auth.loginId"
                    type="button"
                    class="flex h-5 w-5 items-center justify-center rounded text-ink-300/45 transition hover:bg-vermilion-500/20 hover:text-vermilion-400"
                    :aria-label="`关闭牌桌 ${room.room_name}`"
                    title="关闭这桌（大厅不再显示）"
                    @click.stop="askClose(room)"
                  >
                    <X class="h-3.5 w-3.5" />
                  </button>
                </span>
              </div>
              <p class="mt-1.5 flex items-center gap-1.5 text-[11px] text-ink-300/70">
                <span class="badge-rule">{{ room.rule_family_code }}</span>
                {{ room.rule_name }}
              </p>
              <div class="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-ink-300/60">
                <span>{{ room.player_count }} / 4 人</span>
                <span v-if="room.spectator_count">· {{ room.spectator_count }} 人围观</span>
                <span>{{ room.status === 'OPEN' ? '等待开局' : '已关闭' }}</span>
              </div>

              <div
                v-if="closingId === room.id"
                class="mt-2 flex items-center gap-2 rounded-lg border border-vermilion-500/30 bg-vermilion-500/10 px-2 py-1.5 text-[11px]"
                @click.stop
              >
                <span class="text-cream-100">关闭这桌？大厅不再显示</span>
                <button
                  type="button"
                  class="ml-auto shrink-0 rounded bg-vermilion-500 px-2 py-0.5 font-semibold text-cream-50 transition hover:bg-vermilion-400 disabled:opacity-60"
                  :disabled="closing"
                  @click.stop="doClose(room)"
                >
                  关闭
                </button>
                <button type="button" class="shrink-0 rounded px-2 py-0.5 text-ink-300/70" @click.stop="closingId = null">
                  取消
                </button>
              </div>
            </div>
          </div>
        </section>

        <!-- 加入房间 -->
        <section class="glass rounded-2xl p-4 sm:p-5">
          <div class="mb-4 flex items-center gap-2">
            <Sparkles class="h-4 w-4 text-gold-300" />
            <h2 class="text-sm font-medium text-cream-100">用邀请码入座</h2>
          </div>
          <p class="mb-4 text-xs leading-relaxed text-ink-300/70">
            问一下开桌的家人，输入 6 位数字邀请码就能坐到牌桌上。
          </p>

          <div class="flex justify-between gap-1.5 sm:gap-2">
            <input
              v-for="(digit, index) in digits"
              :key="index"
              :ref="(element) => setInputRef(element as Element | null, index)"
              :value="digit"
              class="h-14 w-full rounded-xl border border-cream-100/15 bg-felt-950/60 text-center font-mono text-xl font-bold tracking-widest text-gold-300 outline-none transition focus:border-gold-400/70 focus:shadow-[0_0_0_3px_rgba(201,160,99,0.15)]"
              maxlength="1"
              inputmode="numeric"
              pattern="[0-9]*"
              autocomplete="one-time-code"
              :aria-label="`邀请码第 ${index + 1} 位`"
              @input="onInput(index, $event)"
              @paste="onPaste(index, $event)"
              @keydown="onKeydown(index, $event)"
            />
          </div>

          <p v-if="codeError" class="mt-3 text-xs text-vermilion-400">{{ codeError }}</p>

          <button
            type="button"
            class="btn-gold mt-4 w-full rounded-xl py-2.5 text-sm font-semibold"
            :disabled="checking || code.length !== 6"
            @click="join"
          >
            {{ checking ? '查询中…' : '进入牌桌' }}
          </button>

          <div class="divider-gold my-5" />

          <div class="space-y-2">
            <button
              v-for="link in quickLinks"
              :key="link.key"
              type="button"
              class="flex w-full items-center gap-3 rounded-xl border border-transparent px-2 py-2 text-left transition hover:border-gold-400/25 hover:bg-cream-100/[0.04]"
              @click="router.push({ name: link.to })"
            >
              <component :is="link.icon" class="h-4 w-4 shrink-0 text-gold-300" />
              <div class="min-w-0">
                <p class="text-xs text-cream-100">{{ link.label }}</p>
                <p class="truncate text-[11px] text-ink-300/60">{{ link.desc }}</p>
              </div>
            </button>
          </div>
        </section>
      </div>
    </main>

    <CreateRoomDialog v-if="creating" @close="creating = false" @created="onCreated" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { BookOpen, History, Plus, Sparkles, Trophy, Users } from 'lucide-vue-next'

import AppHeader from '../components/AppHeader.vue'
import CreateRoomDialog from '../components/CreateRoomDialog.vue'
import { api } from '../api/http'
import { useToast } from '../composables/useToast'
import { useAuthStore } from '../stores/auth'
import type { RoomInfo, RoomJoinCheck, StatsInfo } from '../types'

const router = useRouter()
const auth = useAuthStore()
const toast = useToast()

const rooms = ref<RoomInfo[]>([])
const stats = ref<StatsInfo | null>(null)
const loading = ref(true)
const creating = ref(false)
const digits = ref<string[]>(['', '', '', '', '', ''])
const checking = ref(false)
const codeError = ref('')
const inputs = ref<HTMLInputElement[]>([])

const code = computed(() => digits.value.join(''))

async function load(): Promise<void> {
  loading.value = true
  try {
    const [roomList, stat] = await Promise.all([
      api.get<RoomInfo[]>('/rooms'),
      api.get<StatsInfo>('/history/stats')
    ])
    rooms.value = roomList
    stats.value = stat
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    loading.value = false
  }
}

onMounted(load)

function setInputRef(element: Element | null, index: number): void {
  if (element) inputs.value[index] = element as HTMLInputElement
}

function onInput(index: number, event: Event): void {
  const target = event.target as HTMLInputElement
  const value = target.value.replace(/[^0-9A-Za-z]/g, '').toUpperCase()
  digits.value[index] = value.slice(-1)
  target.value = digits.value[index]
  if (digits.value[index] && index < 5) inputs.value[index + 1]?.focus()
  if (code.value.length === 6) void join()
}

function onKeydown(index: number, event: KeyboardEvent): void {
  if (event.key === 'Backspace' && !digits.value[index] && index > 0) {
    inputs.value[index - 1]?.focus()
  }
}

async function join(): Promise<void> {
  codeError.value = ''
  if (code.value.length !== 6) {
    codeError.value = '邀请码是 6 位'
    return
  }
  checking.value = true
  try {
    const info = await api.get<RoomJoinCheck>(`/rooms/code/${code.value}`)
    if (!info.can_join && !info.spectate.available) {
      toast.warn('牌桌满了，围观位也满了，稍后再试')
      return
    }
    if (!info.can_join) toast.info(`座位已满，将以观战身份进入（可围观 ${info.spectate.limit_per_seat * 4} 人）`)
    router.push({ name: 'room', params: { code: info.room_code } })
  } catch (error) {
    codeError.value = (error as Error).message
    digits.value = ['', '', '', '', '', '']
    inputs.value[0]?.focus()
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

const quickLinks = computed(() => [
  { key: 'rules', label: '我的规则模板', desc: '底分、番种、杠分都在这里调', icon: BookOpen, to: { name: 'rules' } },
  { key: 'history', label: '历史战绩', desc: '每局明细，随时对账', icon: History, to: { name: 'history' } },
  { key: 'members', label: '家庭成员', desc: auth.isAdmin ? '添加家人账号' : '找管理员加人', icon: Users, to: null }
])
</script>

<template>
  <div class="min-h-screen pb-16">
    <AppHeader />

    <main class="mx-auto max-w-[1400px] px-5 pt-24">
      <div class="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p class="text-[11px] tracking-[0.32em] text-gold-400/70">LOBBY</p>
          <h1 class="mt-1 text-2xl font-semibold text-cream-100">
            {{ auth.displayName }}，来一局？
          </h1>
          <p class="mt-1 text-sm text-ink-300/80">
            累计积分
            <span class="font-num text-base text-gold-300">{{ stats?.total_score ?? 0 }}</span>
            · 打过 {{ stats?.games_played ?? 0 }} 场 · 赢过 {{ stats?.rounds_won ?? 0 }} 局
          </p>
        </div>
        <button type="button" class="btn-gold flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold" @click="creating = true">
          <Plus class="h-4 w-4" />
          创建牌桌
        </button>
      </div>

      <div class="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
        <!-- 我的房间 -->
        <section class="glass rounded-2xl p-5">
          <div class="mb-4 flex items-center gap-2">
            <Trophy class="h-4 w-4 text-gold-300" />
            <h2 class="text-sm font-medium text-cream-100">我开的牌桌</h2>
            <span class="text-[11px] text-ink-300/60">点开就能接着打</span>
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
            <button
              v-for="room in rooms"
              :key="room.id"
              type="button"
              class="group rounded-xl border border-cream-100/12 bg-cream-100/[0.03] p-3.5 text-left transition hover:border-gold-400/40 hover:bg-gold-400/[0.06]"
              @click="enterRoom(room)"
            >
              <div class="flex items-start justify-between gap-2">
                <span class="text-sm font-medium text-cream-100">{{ room.room_name }}</span>
                <span class="rounded bg-felt-950/60 px-1.5 py-0.5 font-mono text-[10px] tracking-[0.16em] text-gold-300">
                  {{ room.room_code }}
                </span>
              </div>
              <p class="mt-1.5 text-[11px] text-ink-300/70">{{ room.rule_name }}</p>
              <div class="mt-2 flex items-center gap-3 text-[11px] text-ink-300/60">
                <span>{{ room.player_count }} / 4 人</span>
                <span v-if="room.spectator_count">· {{ room.spectator_count }} 人围观</span>
                <span>{{ room.status === 'OPEN' ? '等待开局' : '已关闭' }}</span>
              </div>
            </button>
          </div>
        </section>

        <!-- 加入房间 -->
        <section class="glass rounded-2xl p-5">
          <div class="mb-4 flex items-center gap-2">
            <Sparkles class="h-4 w-4 text-gold-300" />
            <h2 class="text-sm font-medium text-cream-100">用邀请码入座</h2>
          </div>
          <p class="mb-4 text-xs leading-relaxed text-ink-300/70">
            问一下开桌的家人，输入 6 位邀请码就能坐到牌桌上。
          </p>

          <div class="flex justify-between gap-2">
            <input
              v-for="(digit, index) in digits"
              :key="index"
              :ref="(element) => setInputRef(element as Element | null, index)"
              :value="digit"
              class="h-14 w-full rounded-xl border border-cream-100/15 bg-felt-950/60 text-center font-mono text-xl font-bold tracking-widest text-gold-300 outline-none transition focus:border-gold-400/70 focus:shadow-[0_0_0_3px_rgba(201,160,99,0.15)]"
              maxlength="1"
              inputmode="text"
              autocomplete="off"
              @input="onInput(index, $event)"
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
            <component
              :is="link.to ? 'button' : 'div'"
              v-for="link in quickLinks"
              :key="link.key"
              class="flex w-full items-center gap-3 rounded-xl border border-transparent px-2 py-2 text-left transition"
              :class="link.to ? 'hover:border-gold-400/25 hover:bg-cream-100/[0.04]' : 'opacity-70'"
              @click="link.to && router.push(link.to)"
            >
              <component :is="link.icon" class="h-4 w-4 shrink-0 text-gold-300" />
              <div class="min-w-0">
                <p class="text-xs text-cream-100">{{ link.label }}</p>
                <p class="truncate text-[11px] text-ink-300/60">{{ link.desc }}</p>
              </div>
            </component>
          </div>
        </section>
      </div>
    </main>

    <CreateRoomDialog v-if="creating" @close="creating = false" @created="onCreated" />
  </div>
</template>

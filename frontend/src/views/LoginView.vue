<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { CircleAlert, Loader2, LogIn, Sparkles } from 'lucide-vue-next'

import Tile from '../components/table/Tile.vue'
import { api } from '../api/http'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const form = reactive({ username: '', password: '' })
const error = ref('')
const serverOk = ref<boolean | null>(null)
const version = ref('1.0.0')

const floating = [
  { tile: 31, className: 'left-[8%] top-[16%]', tilt: '-12deg', delay: '0s' },
  { tile: 4, className: 'left-[26%] top-[52%]', tilt: '8deg', delay: '1.2s' },
  { tile: 13, className: 'right-[18%] top-[24%]', tilt: '14deg', delay: '0.6s' },
  { tile: 22, className: 'right-[30%] bottom-[18%]', tilt: '-6deg', delay: '2s' },
  { tile: 33, className: 'left-[46%] top-[8%]', tilt: '4deg', delay: '1.6s' }
]

onMounted(async () => {
  try {
    const health = await api.get<{ ok: boolean; version: string }>('/health')
    serverOk.value = Boolean(health.ok)
    version.value = health.version
  } catch {
    serverOk.value = false
  }
})

async function submit(): Promise<void> {
  error.value = ''
  if (!form.username.trim() || !form.password) {
    error.value = '账号和密码都要填一下'
    return
  }
  try {
    await auth.login(form.username.trim().toLowerCase(), form.password)
    const redirect = (route.query.redirect as string) || '/'
    router.replace(redirect)
  } catch (err) {
    error.value = (err as Error).message
  }
}
</script>

<template>
  <div class="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10">
    <div class="pointer-events-none absolute inset-0">
      <div
        v-for="item in floating"
        :key="item.tile"
        class="absolute opacity-[0.13] animate-floaty blur-[0.4px]"
        :class="item.className"
        :style="{ '--tilt': item.tilt, animationDelay: item.delay }"
      >
        <Tile :tile="item.tile" size="lg" class="scale-[2.4]" />
      </div>
      <div class="absolute left-1/2 top-1/2 h-[520px] w-[520px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-gold-400/[0.06] blur-3xl" />
    </div>

    <div class="relative grid w-full max-w-5xl gap-10 md:grid-cols-[1.05fr_0.95fr] md:items-center">
      <!-- 品牌区 -->
      <div class="hidden md:block">
        <div class="mb-5 flex items-center gap-2 text-[11px] tracking-[0.4em] text-gold-400/80">
          <span class="h-px w-8 bg-gold-400/50" />
          FAMILY MAHJONG
        </div>
        <h1 class="font-num text-6xl font-bold leading-tight text-gold-gradient">家庭麻将</h1>
        <p class="mt-4 max-w-md text-[15px] leading-relaxed text-ink-300/85">
          一家人，一张桌。规则自己定，牌局自动算——从开局到结算，分数明明白白，聊天热热闹闹。
        </p>
        <div class="mt-8 grid max-w-md grid-cols-3 gap-3">
          <div v-for="item in [
            { title: '自定义规则', desc: '底分、番种、杠分随你' },
            { title: '自动算番', desc: '判胡算分不会错' },
            { title: '实时闲聊', desc: '碰杠胡全桌都知道' }
          ]" :key="item.title" class="glass-soft rounded-xl px-3 py-2.5">
            <p class="text-xs font-medium text-gold-300">{{ item.title }}</p>
            <p class="mt-0.5 text-[11px] text-ink-300/70">{{ item.desc }}</p>
          </div>
        </div>
      </div>

      <!-- 登录卡 -->
      <div class="relative">
        <transition name="dropbar">
          <div
            v-if="error"
            class="mb-3 flex items-center gap-2 rounded-lg border border-vermilion-500/45 bg-vermilion-500/12 px-3 py-2 text-xs text-vermilion-400"
          >
            <CircleAlert class="h-3.5 w-3.5 shrink-0" />
            {{ error }}
          </div>
        </transition>

        <form class="glass rounded-2xl p-7 shadow-table" @submit.prevent="submit">
          <div class="mb-6 flex items-center gap-2">
            <Sparkles class="h-4 w-4 text-gold-300" />
            <h2 class="text-lg font-semibold text-cream-100">登录牌桌</h2>
          </div>

          <label class="mb-4 block">
            <span class="mb-1.5 block text-xs tracking-wide text-ink-300/85">家庭账号</span>
            <input
              v-model="form.username"
              class="field"
              autocomplete="username"
              placeholder="由管理员为你创建，比如 father"
            />
          </label>

          <label class="mb-5 block">
            <span class="mb-1.5 block text-xs tracking-wide text-ink-300/85">密码</span>
            <input
              v-model="form.password"
              class="field"
              type="password"
              autocomplete="current-password"
              placeholder="输入你的密码"
            />
          </label>

          <button
            type="submit"
            class="btn-gold flex w-full items-center justify-center gap-2 rounded-xl py-3 text-sm font-semibold"
            :disabled="auth.loading"
          >
            <Loader2 v-if="auth.loading" class="h-4 w-4 animate-spin" />
            <LogIn v-else class="h-4 w-4" />
            {{ auth.loading ? '正在进桌…' : '进入牌桌' }}
          </button>

          <p class="mt-4 text-center text-[11px] text-ink-300/60">
            账号由家里的管理员统一创建，忘了密码找管理员重置
          </p>
        </form>

        <div class="mt-4 flex items-center justify-between px-1 text-[11px] text-ink-300/60">
          <span class="flex items-center gap-1.5">
            <span
              class="h-1.5 w-1.5 rounded-full"
              :class="serverOk === null ? 'bg-ink-400' : serverOk ? 'bg-jade-400' : 'bg-vermilion-400'"
            />
            {{ serverOk === null ? '正在连接服务…' : serverOk ? '服务正常' : '服务不可达' }}
          </span>
          <span>v{{ version }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dropbar-enter-active,
.dropbar-leave-active {
  transition: all 0.2s ease;
}
.dropbar-enter-from,
.dropbar-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>

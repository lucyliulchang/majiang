<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { BookOpen, History, LayoutGrid, LogOut, UserPlus, Users } from 'lucide-vue-next'

import MembersDialog from './MembersDialog.vue'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const membersOpen = ref(false)

const navItems = computed(() => [
  { name: 'lobby', label: '大厅', icon: LayoutGrid, active: route.name === 'lobby' },
  { name: 'rules', label: '规则模板', icon: BookOpen, active: route.name === 'rules' },
  { name: 'history', label: '战绩', icon: History, active: route.name === 'history' }
])

function go(name: string): void {
  if (route.name !== name) router.push({ name })
}

function logout(): void {
  auth.logout()
  router.replace({ name: 'login' })
}
</script>

<template>
  <header class="fixed inset-x-0 top-0 z-40 h-16 border-b border-gold-400/15 bg-felt-950/80 backdrop-blur-xl">
    <div class="mx-auto flex h-full max-w-[1400px] items-center gap-6 px-5">
      <div class="flex items-center gap-2.5">
        <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-cream-100 shadow-tile">
          <span class="font-num text-lg font-bold text-vermilion-500">中</span>
        </div>
        <div class="leading-tight">
          <p class="text-sm font-semibold tracking-[0.2em] text-cream-100">家庭麻将</p>
          <p class="text-[10px] tracking-[0.32em] text-ink-300/70">FAMILY TABLE</p>
        </div>
      </div>

      <nav class="flex items-center gap-1">
        <button
          v-for="item in navItems"
          :key="item.name"
          type="button"
          class="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm transition"
          :class="
            item.active
              ? 'bg-gold-400/12 text-gold-300'
              : 'text-ink-300/80 hover:bg-cream-100/5 hover:text-cream-100'
          "
          @click="go(item.name)"
        >
          <component :is="item.icon" class="h-4 w-4" />
          {{ item.label }}
        </button>
        <button
          v-if="auth.isAdmin"
          type="button"
          class="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-ink-300/80 transition hover:bg-cream-100/5 hover:text-cream-100"
          @click="membersOpen = true"
        >
          <Users class="h-4 w-4" />
          成员
        </button>
      </nav>

      <div class="ml-auto flex items-center gap-3">
        <div class="flex items-center gap-2 rounded-full border border-cream-100/10 bg-cream-100/5 py-1 pl-1 pr-3">
          <span
            class="flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold text-felt-950"
            :style="{ backgroundColor: auth.user?.color || '#C9A063' }"
          >
            {{ auth.displayName.slice(0, 1) }}
          </span>
          <span class="text-sm text-cream-100">{{ auth.displayName }}</span>
          <span
            v-if="auth.isAdmin"
            class="rounded bg-gold-400/20 px-1.5 py-0.5 text-[10px] text-gold-300"
          >
            管理员
          </span>
        </div>
        <button type="button" class="btn-ghost flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm" @click="logout">
          <LogOut class="h-4 w-4" />
          退出
        </button>
      </div>
    </div>
  </header>

  <MembersDialog v-if="membersOpen" @close="membersOpen = false" />

  <!-- 让管理员入口在窄屏也能触达 -->
  <button
    v-if="auth.isAdmin && !membersOpen"
    type="button"
    class="fixed bottom-6 right-6 z-30 hidden h-12 w-12 items-center justify-center rounded-full border border-gold-400/40 bg-felt-800 text-gold-300 shadow-gold md:hidden"
    @click="membersOpen = true"
  >
    <UserPlus class="h-5 w-5" />
  </button>
</template>

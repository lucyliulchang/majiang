<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  BookOpen,
  Check,
  ChevronDown,
  History,
  LayoutGrid,
  LogOut,
  Menu,
  Palette,
  Plus,
  Users,
  X
} from 'lucide-vue-next'

import { useToast } from '../composables/useToast'
import { useAuthStore } from '../stores/auth'
import { useFamiliesStore } from '../stores/families'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const families = useFamiliesStore()
const toast = useToast()

const ROLE_TEXT: Record<string, string> = { OWNER: '家长', ADMIN: '管理员', MEMBER: '成员' }

const navItems = computed(() => [
  { name: 'lobby', label: '大厅', icon: LayoutGrid, active: route.name === 'lobby' },
  { name: 'rules', label: '规则模板', icon: BookOpen, active: route.name === 'rules' },
  { name: 'history', label: '战绩', icon: History, active: route.name === 'history' }
])

const familyMenuOpen = ref(false)
const mobileOpen = ref(false)
const familyWrap = ref<HTMLElement | null>(null)
const switching = ref(false)

const familyName = computed(() => auth.currentFamilyName)
const familyBadge = computed(() => (familyName.value || '家').slice(0, 1))
const roleText = computed(() => ROLE_TEXT[auth.familyRole] || '')
const hasSkinsEntry = computed(() => auth.canManageSkins)

function go(target: { name?: string; path?: string }): void {
  mobileOpen.value = false
  familyMenuOpen.value = false
  if (target.name && route.name === target.name) return
  void router.push(target.name ? { name: target.name } : (target.path as string))
}

/** 当前家庭的成员管理（家庭管理员/成员都能进：成员只读 + 自助退出） */
function goMembers(): void {
  mobileOpen.value = false
  familyMenuOpen.value = false
  const code = auth.currentFamilyCode
  if (!code) return
  void router.push({ name: 'family-members', params: { familyCode: code } })
}

async function pickFamily(code: string): Promise<void> {
  familyMenuOpen.value = false
  if (code === auth.currentFamilyCode) return
  switching.value = true
  try {
    await families.switchTo(code)
    toast.success(`已切到「${auth.currentFamilyName}」`)
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    switching.value = false
  }
}

function onDocPointerDown(event: PointerEvent): void {
  if (!familyMenuOpen.value) return
  const target = event.target as Node | null
  if (familyWrap.value && target && familyWrap.value.contains(target)) return
  familyMenuOpen.value = false
}

onMounted(() => {
  document.addEventListener('pointerdown', onDocPointerDown, true)
  // 家庭列表在 App 已拉过；这里只补一次空列表的情况（直接刷新子页面进来）
  if (!auth.families.length) void families.load().catch(() => undefined)
})

onBeforeUnmount(() => document.removeEventListener('pointerdown', onDocPointerDown, true))

async function logout(): Promise<void> {
  // 后端 A5A0 是尽力而为，本地一定清干净再跳登录页
  mobileOpen.value = false
  await auth.logout()
  router.replace({ name: 'login' })
}
</script>

<template>
  <header class="fixed inset-x-0 top-0 z-40 h-16 border-b border-gold-400/15 bg-felt-950/80 backdrop-blur-xl">
    <div class="mx-auto flex h-full max-w-[1400px] items-center gap-3 px-4 sm:gap-5 sm:px-5">
      <button type="button" class="flex items-center gap-2.5" @click="go({ name: 'lobby' })">
        <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-cream-100 shadow-tile">
          <span class="font-num text-lg font-bold text-vermilion-500">中</span>
        </div>
        <div class="hidden leading-tight text-left sm:block">
          <p class="text-sm font-semibold tracking-[0.2em] text-cream-100">家庭麻将</p>
          <p class="text-[10px] tracking-[0.32em] text-ink-300/70">FAMILY TABLE</p>
        </div>
      </button>

      <!-- 家庭切换器（徽标 + 名称 + 下拉） -->
      <div ref="familyWrap" class="relative">
        <button
          type="button"
          class="flex items-center gap-1.5 rounded-full border border-family/40 bg-family/10 py-1 pl-1 pr-2 text-xs text-cream-100/90 transition hover:border-family/70"
          :aria-expanded="familyMenuOpen"
          aria-label="切换家庭"
          @click="familyMenuOpen = !familyMenuOpen"
        >
          <span class="flex h-6 w-6 items-center justify-center rounded-full bg-family text-[11px] font-semibold text-felt-950">
            {{ switching ? '…' : familyBadge }}
          </span>
          <span class="max-w-[92px] truncate sm:max-w-[140px]">{{ familyName }}</span>
          <ChevronDown class="h-3 w-3 shrink-0 transition" :class="familyMenuOpen ? 'rotate-180' : ''" />
        </button>

        <transition name="drop">
          <div
            v-if="familyMenuOpen"
            class="absolute left-0 top-full z-50 mt-2 w-[248px] rounded-xl border border-gold-400/25 bg-felt-950/97 p-2 text-xs shadow-table backdrop-blur"
          >
            <p class="px-2 py-1 text-[10px] tracking-[0.24em] text-gold-400/70">我的家庭</p>
            <button
              v-for="family in auth.families"
              :key="family.family_code"
              type="button"
              class="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left transition"
              :class="
                family.family_code === auth.currentFamilyCode
                  ? 'bg-gold-400/10 text-cream-100'
                  : 'text-ink-300/85 hover:bg-cream-100/[0.06]'
              "
              @click="pickFamily(family.family_code)"
            >
              <span class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-family/80 text-[10px] font-semibold text-felt-950">
                {{ (family.family_name || '家').slice(0, 1) }}
              </span>
              <span class="min-w-0 flex-1">
                <span class="block truncate text-[13px] text-cream-100">{{ family.family_name }}</span>
                <span class="block truncate text-[10px] text-ink-300/60">
                  {{ ROLE_TEXT[family.member_role] || family.member_role || '成员' }} · {{ family.family_code }}
                </span>
              </span>
              <Check v-if="family.family_code === auth.currentFamilyCode" class="h-3.5 w-3.5 shrink-0 text-gold-300" />
            </button>

            <p v-if="!auth.families.length" class="px-2 py-3 text-center text-[11px] text-ink-300/60">
              还没有家庭
            </p>

            <div class="divider-gold my-1.5" />
            <button
              v-if="auth.currentFamilyCode"
              type="button"
              class="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-ink-300/85 transition hover:bg-cream-100/[0.06]"
              @click="goMembers"
            >
              <Users class="h-3.5 w-3.5 text-gold-300" />
              家庭成员
            </button>
            <button
              type="button"
              class="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-ink-300/85 transition hover:bg-cream-100/[0.06]"
              @click="go({ name: 'families' })"
            >
              <Users class="h-3.5 w-3.5 text-gold-300" />
              管理家庭 / 新建
            </button>
          </div>
        </transition>
      </div>

      <nav class="hidden items-center gap-1 md:flex">
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
          @click="go({ name: item.name })"
        >
          <component :is="item.icon" class="h-4 w-4" />
          {{ item.label }}
        </button>
        <button
          v-if="hasSkinsEntry"
          type="button"
          class="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm transition"
          :class="
            String(route.name).startsWith('skin')
              ? 'bg-skin/15 text-cream-100'
              : 'text-ink-300/80 hover:bg-cream-100/5 hover:text-cream-100'
          "
          @click="go({ name: 'skins' })"
        >
          <Palette class="h-4 w-4" />
          皮肤
        </button>
      </nav>

      <div class="ml-auto hidden items-center gap-3 md:flex">
        <div class="flex items-center gap-2 rounded-full border border-cream-100/10 bg-cream-100/5 py-1 pl-1 pr-3">
          <span
            class="flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold text-felt-950"
            :style="{ backgroundColor: auth.avatarColor }"
          >
            {{ auth.displayName.slice(0, 1) }}
          </span>
          <span class="max-w-[120px] truncate text-sm text-cream-100">{{ auth.displayName }}</span>
          <span v-if="roleText" class="rounded bg-family/20 px-1.5 py-0.5 text-[10px] text-cream-100/90">
            {{ roleText }}
          </span>
          <span v-if="auth.isAdmin" class="rounded bg-gold-400/20 px-1.5 py-0.5 text-[10px] text-gold-300">
            系统管理员
          </span>
        </div>
        <button type="button" class="btn-ghost flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm" @click="logout">
          <LogOut class="h-4 w-4" />
          退出
        </button>
      </div>

      <!-- 移动端汉堡 -->
      <button
        type="button"
        class="btn-ghost ml-auto flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-xs md:hidden"
        :aria-expanded="mobileOpen"
        aria-label="打开菜单"
        @click="mobileOpen = !mobileOpen"
      >
        <X v-if="mobileOpen" class="h-4 w-4" />
        <Menu v-else class="h-4 w-4" />
        菜单
      </button>
    </div>

    <!-- 移动端菜单 -->
    <transition name="drop">
      <div
        v-if="mobileOpen"
        class="fixed inset-x-0 top-16 z-40 border-b border-gold-400/20 bg-felt-950/97 px-4 py-3 backdrop-blur md:hidden"
      >
        <div class="space-y-1">
          <button
            v-for="item in navItems"
            :key="item.name"
            type="button"
            class="flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-sm"
            :class="item.active ? 'bg-gold-400/12 text-gold-300' : 'text-ink-300/85'"
            @click="go({ name: item.name })"
          >
            <component :is="item.icon" class="h-4 w-4" />
            {{ item.label }}
          </button>
          <button
            v-if="hasSkinsEntry"
            type="button"
            class="flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-sm text-ink-300/85"
            @click="go({ name: 'skins' })"
          >
            <Palette class="h-4 w-4" />
            皮肤管理
          </button>
          <button
            v-if="auth.currentFamilyCode"
            type="button"
            class="flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-sm text-ink-300/85"
            @click="goMembers"
          >
            <Users class="h-4 w-4" />
            家庭成员
          </button>
          <button
            type="button"
            class="flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-sm text-ink-300/85"
            @click="go({ name: 'families' })"
          >
            <Users class="h-4 w-4" />
            我的家庭
          </button>
          <button
            type="button"
            class="flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-sm text-ink-300/85"
            @click="go({ name: 'families' })"
          >
            <Plus class="h-4 w-4" />
            新建家庭
          </button>
        </div>

        <div class="divider-gold my-2" />
        <div class="flex items-center justify-between gap-2 px-1">
          <span class="min-w-0">
            <span class="block truncate text-xs text-cream-100">{{ auth.displayName }}</span>
            <span class="block truncate text-[10px] text-ink-300/60">{{ auth.loginId }}</span>
          </span>
          <button type="button" class="btn-ghost flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs" @click="logout">
            <LogOut class="h-3.5 w-3.5" />
            退出
          </button>
        </div>
      </div>
    </transition>
  </header>
</template>

<style scoped>
.drop-enter-active,
.drop-leave-active {
  transition: all 0.18s ease;
}
.drop-enter-from,
.drop-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Check, UserPlus, X } from 'lucide-vue-next'

import { api } from '../api/http'
import { useToast } from '../composables/useToast'
import type { UserInfo } from '../types'

const emit = defineEmits<{ close: [] }>()
const toast = useToast()

const members = ref<UserInfo[]>([])
const loading = ref(false)
const saving = ref(false)
const form = reactive({
  username: '',
  display_name: '',
  password: '',
  color: '#C9A063'
})

const palette = ['#C9A063', '#2E7D5B', '#C0392B', '#4A7EBB', '#8B5FBF', '#E8A33D']

async function load(): Promise<void> {
  loading.value = true
  try {
    members.value = await api.get<UserInfo[]>('/users')
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    loading.value = false
  }
}

async function create(): Promise<void> {
  if (!form.username.trim() || !form.display_name.trim() || form.password.length < 6) {
    toast.warn('账号、昵称要填，密码至少 6 位')
    return
  }
  saving.value = true
  try {
    await api.post('/users', { ...form })
    toast.success(`已添加 ${form.display_name}`)
    form.username = ''
    form.display_name = ''
    form.password = ''
    await load()
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    saving.value = false
  }
}

async function toggleActive(member: UserInfo): Promise<void> {
  try {
    await api.patch(`/users/${member.id}`, { is_active: !member.is_active })
    await load()
  } catch (error) {
    toast.error((error as Error).message)
  }
}

async function resetPassword(member: UserInfo): Promise<void> {
  const password = window.prompt(`给「${member.display_name}」设置新密码（至少 6 位）`)
  if (!password) return
  if (password.length < 6) {
    toast.warn('密码至少 6 位')
    return
  }
  try {
    await api.patch(`/users/${member.id}`, { password })
    toast.success('密码已重置')
  } catch (error) {
    toast.error((error as Error).message)
  }
}

onMounted(load)
</script>

<template>
  <div class="fixed inset-0 z-[70] flex items-center justify-center bg-felt-950/80 px-4 backdrop-blur-sm">
    <div class="glass max-h-[86vh] w-full max-w-3xl overflow-hidden rounded-2xl shadow-table animate-riseIn">
      <div class="flex items-center justify-between border-b border-cream-100/10 px-6 py-4">
        <div>
          <h2 class="text-lg font-semibold text-cream-100">家庭成员</h2>
          <p class="mt-0.5 text-xs text-ink-300/80">账号由管理员统一创建，家里人不用自己注册</p>
        </div>
        <button type="button" class="btn-ghost rounded-lg p-2" @click="emit('close')">
          <X class="h-4 w-4" />
        </button>
      </div>

      <div class="grid max-h-[70vh] gap-6 overflow-y-auto p-6 md:grid-cols-[1.1fr_1fr]">
        <div class="space-y-2">
          <p v-if="loading" class="text-sm text-ink-300/70">加载中…</p>
          <div
            v-for="member in members"
            :key="member.id"
            class="flex items-center gap-3 rounded-xl border border-cream-100/10 bg-cream-100/[0.03] px-3 py-2.5"
          >
            <span
              class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-felt-950"
              :style="{ backgroundColor: member.color }"
            >
              {{ member.display_name.slice(0, 1) }}
            </span>
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm text-cream-100">
                {{ member.display_name }}
                <span v-if="member.role === 'admin'" class="ml-1 text-[10px] text-gold-300">管理员</span>
              </p>
              <p class="truncate text-xs text-ink-300/70">@{{ member.username }}</p>
            </div>
            <span
              class="rounded px-1.5 py-0.5 text-[11px]"
              :class="member.is_active ? 'text-jade-400' : 'text-ink-400'"
            >
              {{ member.is_active ? '正常' : '已停用' }}
            </span>
            <button type="button" class="btn-ghost rounded-md px-2 py-1 text-xs" @click="resetPassword(member)">
              改密码
            </button>
            <button
              type="button"
              class="rounded-md px-2 py-1 text-xs transition"
              :class="member.is_active ? 'text-vermilion-400 hover:bg-vermilion-500/10' : 'text-jade-400 hover:bg-jade-500/10'"
              @click="toggleActive(member)"
            >
              {{ member.is_active ? '停用' : '启用' }}
            </button>
          </div>
        </div>

        <div class="rounded-xl border border-gold-400/20 bg-felt-950/40 p-4">
          <p class="mb-3 flex items-center gap-1.5 text-sm font-medium text-gold-300">
            <UserPlus class="h-4 w-4" /> 添加成员
          </p>
          <div class="space-y-3">
            <label class="block">
              <span class="mb-1 block text-xs text-ink-300/80">登录账号</span>
              <input v-model="form.username" class="field" placeholder="比如 father" autocomplete="off" />
            </label>
            <label class="block">
              <span class="mb-1 block text-xs text-ink-300/80">显示昵称</span>
              <input v-model="form.display_name" class="field" placeholder="比如 爸爸" />
            </label>
            <label class="block">
              <span class="mb-1 block text-xs text-ink-300/80">初始密码</span>
              <input v-model="form.password" class="field" type="password" placeholder="至少 6 位" />
            </label>
            <div>
              <span class="mb-1.5 block text-xs text-ink-300/80">头像色标</span>
              <div class="flex gap-2">
                <button
                  v-for="color in palette"
                  :key="color"
                  type="button"
                  class="h-7 w-7 rounded-full border-2 transition"
                  :class="form.color === color ? 'border-cream-100 scale-110' : 'border-transparent'"
                  :style="{ backgroundColor: color }"
                  @click="form.color = color"
                >
                  <Check v-if="form.color === color" class="mx-auto h-3.5 w-3.5 text-felt-950" />
                </button>
              </div>
            </div>
            <button type="button" class="btn-gold w-full rounded-lg py-2.5 text-sm font-semibold" :disabled="saving" @click="create">
              {{ saving ? '保存中…' : '添加成员' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

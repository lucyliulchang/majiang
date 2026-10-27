<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { CircleAlert, Loader2, LogIn, Sparkles } from 'lucide-vue-next'

import AuthShell from '../components/auth/AuthShell.vue'
import { api } from '../api/http'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const form = reactive({ loginId: '', passwd: '' })
const error = ref('')
const serverOk = ref<boolean | null>(null)
const version = ref('1.0.0')

onMounted(async () => {
  // 注册/找回成功后回填账号（05 §4.1.1、§4.1.2）
  const prefill = route.query.login_id
  if (typeof prefill === 'string') form.loginId = prefill

  auth.loadOptions()
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
  if (!form.loginId.trim() || !form.passwd) {
    error.value = '账号和密码都要填一下'
    return
  }
  try {
    // 账号是手机号，不做大小写/首尾以外的加工；口令明文交给后端（HTTPS 覆盖）
    await auth.login(form.loginId.trim(), form.passwd)
    const redirect = (route.query.redirect as string) || '/'
    router.replace(redirect)
  } catch (err) {
    // 失败不区分账号不存在/口令错（04 §2.5）；503 由后端给出账号服务不可用文案
    error.value = (err as Error).message
  }
}
</script>

<template>
  <AuthShell
    title="登录牌桌"
    subtitle="用手机号和密码登录；账号由家庭管理员在账号服务里开通"
    @submit="submit"
  >
    <template #alerts>
      <transition name="dropbar">
        <div
          v-if="error"
          class="mb-3 flex items-center gap-2 rounded-lg border border-vermilion-500/45 bg-vermilion-500/12 px-3 py-2 text-xs text-vermilion-400"
        >
          <CircleAlert class="h-3.5 w-3.5 shrink-0" />
          {{ error }}
        </div>
      </transition>
    </template>

    <label class="mb-4 block">
      <span class="mb-1.5 block text-xs tracking-wide text-ink-300/85">手机号 / 账号</span>
      <input
        v-model="form.loginId"
        class="field"
        autocomplete="username"
        inputmode="tel"
        placeholder="比如 13800000000"
      />
    </label>

    <label class="mb-5 block">
      <span class="mb-1.5 flex items-center justify-between text-xs tracking-wide text-ink-300/85">
        <span>密码</span>
        <router-link
          to="/forgot-password"
          class="text-[11px] text-gold-300/80 transition hover:text-gold-300"
        >
          忘记密码
        </router-link>
      </span>
      <input
        v-model="form.passwd"
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

    <p
      v-if="auth.options.register_enabled"
      class="mt-4 text-center text-[11px] text-ink-300/70"
    >
      还没有账号？
      <router-link to="/register" class="text-gold-300 transition hover:text-gold-400">
        注册一个
      </router-link>
    </p>

    <template #footer>
      <span class="flex items-center gap-1.5">
        <span
          class="h-1.5 w-1.5 rounded-full"
          :class="serverOk === null ? 'bg-ink-400' : serverOk ? 'bg-jade-400' : 'bg-vermilion-400'"
        />
        {{ serverOk === null ? '正在连接服务…' : serverOk ? '服务正常' : '服务不可达' }}
      </span>
      <span>v{{ version }}</span>
    </template>
  </AuthShell>
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

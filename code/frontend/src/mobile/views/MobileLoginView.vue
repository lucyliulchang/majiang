<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { CircleAlert, Loader2, LogIn } from 'lucide-vue-next'

import MobileAuthShell from '../components/MobileAuthShell.vue'
import { api } from '../../api/http'
import { useAuthStore } from '../../stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const form = reactive({ loginId: '', passwd: '' })
const error = ref('')
const serverOk = ref<boolean | null>(null)
const version = ref('1.1.2')

onMounted(async () => {
  // 注册/找回成功后回填账号（05 §4.1.1、§4.1.2）
  const prefill = route.query.login_id
  if (typeof prefill === 'string') form.loginId = prefill

  void auth.loadOptions()
  try {
    const health = await api.get<{ ok: boolean; version: string }>('/health')
    serverOk.value = Boolean(health.ok)
    version.value = health.version
  } catch {
    serverOk.value = false
  }
})

/** 只接受站内绝对路径，避免 redirect 被塞成外链 */
function targetPath(): string {
  const redirect = route.query.redirect
  if (typeof redirect === 'string' && redirect.startsWith('/') && !redirect.startsWith('//')) return redirect
  return '/'
}

async function submit(): Promise<void> {
  error.value = ''
  if (!form.loginId.trim() || !form.passwd) {
    error.value = '账号和密码都要填一下'
    return
  }
  try {
    await auth.login(form.loginId.trim(), form.passwd)
    router.replace(targetPath())
  } catch (err) {
    // 失败不区分账号不存在/口令错（04 §2.5）
    error.value = (err as Error).message
  }
}
</script>

<template>
  <MobileAuthShell
    title="登录牌桌"
    subtitle="用手机号和密码登录；账号由家庭管理员在账号服务里开通"
    @submit="submit"
  >
    <template #alerts>
      <div
        v-if="error"
        class="mb-3 flex items-center gap-2 rounded-xl border border-vermilion-500/45 bg-vermilion-500/10 px-3 py-2.5 text-[12px] text-vermilion-400"
      >
        <CircleAlert class="h-4 w-4 shrink-0" />
        {{ error }}
      </div>
    </template>

    <label class="mb-4 block">
      <span class="mb-1.5 block text-[12px] tracking-wide text-ink-300/85">手机号 / 账号</span>
      <input
        v-model="form.loginId"
        class="field"
        autocomplete="username"
        inputmode="tel"
        placeholder="比如 13800000000"
      />
    </label>

    <label class="mb-5 block">
      <span class="mb-1.5 flex items-center justify-between text-[12px] tracking-wide text-ink-300/85">
        <span>密码</span>
        <router-link to="/forgot-password" class="text-[11px] text-gold-300/85">忘记密码</router-link>
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
      class="mj-press btn-gold flex min-h-[48px] w-full items-center justify-center gap-2 rounded-xl text-[15px] font-semibold"
      :disabled="auth.loading"
    >
      <Loader2 v-if="auth.loading" class="h-4 w-4 animate-spin" />
      <LogIn v-else class="h-4 w-4" />
      {{ auth.loading ? '正在进桌…' : '进入牌桌' }}
    </button>

    <p v-if="auth.options.register_enabled" class="mt-4 text-center text-[12px] text-ink-300/70">
      还没有账号？
      <router-link to="/register" class="text-gold-300">注册一个</router-link>
    </p>

    <template #footer>
      <span class="flex items-center gap-1.5">
        <span
          class="h-1.5 w-1.5 rounded-full"
          :class="serverOk === null ? 'bg-ink-400' : serverOk ? 'bg-jade-400' : 'bg-vermilion-400'"
        />
        {{ serverOk === null ? '正在连接服务…' : serverOk ? '服务正常' : '服务不可达' }}
      </span>
      <span class="flex items-center gap-2">
        <span
          class="rounded-full border border-gold-400/35 bg-gold-400/10 px-1.5 py-0.5 text-[10px] leading-none text-gold-300/85"
          >软件开发测试</span
        >
        <span>手机版 v{{ version }}</span>
      </span>
    </template>
  </MobileAuthShell>
</template>

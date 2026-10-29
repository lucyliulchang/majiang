<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, CircleAlert, Eye, EyeOff, KeyRound, Loader2 } from 'lucide-vue-next'

import MobileAuthShell from '../components/MobileAuthShell.vue'
import { api, ApiError } from '../../api/http'
import { useAuthStore } from '../../stores/auth'
import { useToast } from '../../composables/useToast'
import type { VerifyCodeResult } from '../../types'

const router = useRouter()
const auth = useAuthStore()
const toast = useToast()

const PHONE_PATTERN = /^1[3-9]\d{9}$/
const CODE_PATTERN = /^\d{6}$/

const step = ref<1 | 2>(1)
const loginId = ref('')
const code = ref('')
const passwd = ref('')
const confirm = ref('')
const showPasswd = ref(false)
const error = ref('')
const sending = ref(false)
const submitting = ref(false)
const countdown = ref(0)
const optionsLoaded = ref(false)
let timer: number | undefined

const enabled = computed(() => auth.options.password_reset_enabled)
const phoneOk = computed(() => PHONE_PATTERN.test(loginId.value.trim()))
const maskedPhone = computed(() => {
  const text = loginId.value.trim()
  if (text.length !== 11) return text
  return `${text.slice(0, 3)}****${text.slice(7)}`
})

onMounted(async () => {
  await auth.loadOptions()
  optionsLoaded.value = true
})

onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})

function startCountdown(seconds: number): void {
  countdown.value = Math.max(0, Math.floor(seconds))
  if (timer) window.clearInterval(timer)
  if (countdown.value <= 0) return
  timer = window.setInterval(() => {
    countdown.value = Math.max(0, countdown.value - 1)
    if (countdown.value === 0 && timer) {
      window.clearInterval(timer)
      timer = undefined
    }
  }, 1000)
}

async function sendCode(): Promise<void> {
  error.value = ''
  if (!phoneOk.value) {
    error.value = '请输入正确的手机号'
    return
  }
  sending.value = true
  try {
    const result = await api.post<VerifyCodeResult>('/auth/verify-code', {
      login_id: loginId.value.trim(),
      scene: 'reset_password'
    })
    startCountdown(result.cooldown_seconds || auth.options.verify_code_cooldown_seconds)
    // 不暴露账号是否存在（04 §2.2-2）
    toast.success('若该手机号已注册，验证码已发送')
    step.value = 2
  } catch (err) {
    const apiError = err as ApiError
    error.value = apiError.message
    if (apiError.code === 'VERIFY_CODE_SEND_TOO_FAST') startCountdown(auth.options.verify_code_cooldown_seconds)
  } finally {
    sending.value = false
  }
}

async function submit(): Promise<void> {
  error.value = ''
  if (!CODE_PATTERN.test(code.value.trim())) {
    error.value = '请输入 6 位数字验证码'
    return
  }
  if (passwd.value.length < 6 || passwd.value.length > 32) {
    error.value = '新密码需为 6-32 位'
    return
  }
  if (passwd.value !== confirm.value) {
    error.value = '两次输入的密码不一致'
    return
  }

  submitting.value = true
  try {
    await api.post('/auth/password/reset', {
      login_id: loginId.value.trim(),
      verify_code: code.value.trim(),
      new_passwd: passwd.value
    })
    toast.success('密码已重置，请用新密码登录')
    const target = loginId.value.trim()
    window.setTimeout(() => {
      router.replace({ path: '/login', query: { login_id: target } })
    }, 1200)
  } catch (err) {
    // 失败只清空验证码，保留手机号与新密码（05 §4.1.2）
    code.value = ''
    error.value = (err as Error).message
  } finally {
    submitting.value = false
  }
}

function back(): void {
  error.value = ''
  code.value = ''
  step.value = 1
}
</script>

<template>
  <MobileAuthShell
    v-if="optionsLoaded && enabled"
    title="找回密码"
    subtitle="两步完成：验证手机号 → 设置新密码"
    @submit="step === 1 ? sendCode() : submit()"
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

    <div class="mb-5 flex items-center gap-2 text-[11px]">
      <span
        class="rounded-full px-2.5 py-1"
        :class="step === 1 ? 'bg-gold-400/15 text-gold-300' : 'text-ink-300/60'"
      >
        1 验证账号
      </span>
      <span class="h-px flex-1 bg-cream-100/10" />
      <span
        class="rounded-full px-2.5 py-1"
        :class="step === 2 ? 'bg-gold-400/15 text-gold-300' : 'text-ink-300/60'"
      >
        2 设置新密码
      </span>
    </div>

    <template v-if="step === 1">
      <label class="mb-4 block">
        <span class="mb-1.5 block text-[12px] tracking-wide text-ink-300/85">注册手机号</span>
        <div class="flex items-stretch gap-2">
          <input
            v-model="loginId"
            class="field min-w-0 flex-1"
            inputmode="tel"
            autocomplete="username"
            placeholder="11 位手机号"
          />
          <button
            type="button"
            class="mj-press btn-ghost shrink-0 whitespace-nowrap rounded-xl px-3 text-[12px]"
            :disabled="sending || countdown > 0 || !phoneOk"
            @click="sendCode"
          >
            {{ sending ? '发送中…' : countdown > 0 ? `${countdown}s 后重发` : '获取验证码' }}
          </button>
        </div>
      </label>
      <p class="text-[11px] leading-relaxed text-ink-300/60">
        验证码由账号服务下发，10 分钟内有效。为保护隐私，无论手机号是否注册，提示都一样。
      </p>
    </template>

    <template v-else>
      <div class="mb-4 flex items-center justify-between text-[12px]">
        <span class="text-ink-300/85">
          手机号 <span class="font-num tracking-wide text-cream-100">{{ maskedPhone }}</span>
        </span>
        <button
          type="button"
          class="text-[11px] text-gold-300/85"
          :disabled="sending || countdown > 0 || !phoneOk"
          @click="sendCode"
        >
          {{ countdown > 0 ? `${countdown}s 后重发` : '重新发送' }}
        </button>
      </div>

      <label class="mb-3.5 block">
        <span class="mb-1.5 block text-[12px] tracking-wide text-ink-300/85">验证码</span>
        <input
          v-model="code"
          class="field tracking-[0.3em]"
          inputmode="numeric"
          maxlength="6"
          autocomplete="one-time-code"
          placeholder="6 位数字"
        />
      </label>

      <label class="mb-3.5 block">
        <span class="mb-1.5 block text-[12px] tracking-wide text-ink-300/85">新密码</span>
        <div class="relative">
          <input
            v-model="passwd"
            class="field pr-12"
            :type="showPasswd ? 'text' : 'password'"
            autocomplete="new-password"
            placeholder="6-32 位，不含空格"
          />
          <button
            type="button"
            class="absolute right-1.5 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-lg text-ink-300/70"
            :aria-label="showPasswd ? '隐藏密码' : '显示密码'"
            @click="showPasswd = !showPasswd"
          >
            <EyeOff v-if="showPasswd" class="h-4 w-4" />
            <Eye v-else class="h-4 w-4" />
          </button>
        </div>
      </label>

      <label class="mb-4 block">
        <span class="mb-1.5 block text-[12px] tracking-wide text-ink-300/85">确认新密码</span>
        <input
          v-model="confirm"
          class="field"
          :type="showPasswd ? 'text' : 'password'"
          autocomplete="new-password"
          placeholder="再输入一次"
        />
      </label>
    </template>

    <button
      type="submit"
      class="mj-press btn-gold flex min-h-[48px] w-full items-center justify-center gap-2 rounded-xl text-[15px] font-semibold"
      :disabled="submitting || sending"
    >
      <Loader2 v-if="submitting || sending" class="h-4 w-4 animate-spin" />
      <KeyRound v-else class="h-4 w-4" />
      {{ step === 1 ? '发送验证码' : submitting ? '正在提交…' : '重置密码' }}
    </button>

    <div class="mt-4 flex items-center justify-between text-[11px]">
      <button
        v-if="step === 2"
        type="button"
        class="flex items-center gap-1 text-ink-300/70"
        @click="back"
      >
        <ArrowLeft class="h-3.5 w-3.5" />
        返回上一步
      </button>
      <router-link to="/login" class="ml-auto text-gold-300/80">返回登录</router-link>
    </div>
  </MobileAuthShell>

  <MobileAuthShell
    v-else-if="optionsLoaded"
    title="自助找回已关闭"
    subtitle="当前环境关闭了自助找回密码，请联系家庭管理员重置"
  >
    <router-link to="/login" class="mj-press btn-ghost flex min-h-[48px] w-full items-center justify-center rounded-xl text-sm">
      返回登录
    </router-link>
  </MobileAuthShell>

  <MobileAuthShell v-else title="正在加载…" subtitle="正在读取账号服务开关">
    <div class="flex items-center justify-center py-6 text-ink-300/60">
      <Loader2 class="h-5 w-5 animate-spin" />
    </div>
  </MobileAuthShell>
</template>

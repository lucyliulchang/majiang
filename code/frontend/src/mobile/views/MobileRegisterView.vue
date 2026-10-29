<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { CircleAlert, Eye, EyeOff, Loader2, UserPlus } from 'lucide-vue-next'

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

const form = reactive({ loginId: '', verifyCode: '', passwd: '', confirm: '', nickName: '', agreed: false })
const error = ref('')
const fieldError = ref('')
const showPasswd = ref(false)
const sending = ref(false)
const submitting = ref(false)
const countdown = ref(0)
const optionsLoaded = ref(false)
let timer: number | undefined

const enabled = computed(() => auth.options.register_enabled)
const phoneOk = computed(() => PHONE_PATTERN.test(form.loginId.trim()))
const canSubmit = computed(() => enabled.value && form.agreed && !submitting.value && !auth.loading)

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
  fieldError.value = ''
  if (!phoneOk.value) {
    fieldError.value = '请输入正确的手机号'
    return
  }
  sending.value = true
  try {
    const result = await api.post<VerifyCodeResult>('/auth/verify-code', {
      login_id: form.loginId.trim(),
      scene: 'register'
    })
    startCountdown(result.cooldown_seconds || auth.options.verify_code_cooldown_seconds)
    toast.success('验证码已发送')
  } catch (err) {
    const apiError = err as ApiError
    error.value = apiError.message
    if (apiError.code === 'VERIFY_CODE_SEND_TOO_FAST') {
      startCountdown(auth.options.verify_code_cooldown_seconds)
    }
  } finally {
    sending.value = false
  }
}

async function submit(): Promise<void> {
  error.value = ''
  fieldError.value = ''

  if (!phoneOk.value) {
    fieldError.value = '请输入正确的手机号'
    return
  }
  if (!CODE_PATTERN.test(form.verifyCode.trim())) {
    fieldError.value = '请输入 6 位数字验证码'
    return
  }
  if (form.passwd.length < 6 || form.passwd.length > 32) {
    fieldError.value = '密码长度需为 6-32 位'
    return
  }
  if (form.passwd !== form.confirm) {
    fieldError.value = '两次输入的密码不一致'
    return
  }
  if (form.nickName.trim().length > 20) {
    fieldError.value = '昵称最多 20 字'
    return
  }
  if (!form.agreed) {
    fieldError.value = '请先同意服务条款'
    return
  }

  submitting.value = true
  try {
    const result = await api.post<{ ok: boolean; login_id: string }>('/auth/register', {
      login_id: form.loginId.trim(),
      passwd: form.passwd,
      verify_code: form.verifyCode.trim(),
      nick_name: form.nickName.trim()
    })
    toast.success('注册成功，请登录')
    window.setTimeout(() => {
      router.replace({ path: '/login', query: { login_id: result.login_id } })
    }, 1200)
  } catch (err) {
    const apiError = err as ApiError
    // 失败保留输入，只清空验证码（05 §4.1.1）
    form.verifyCode = ''
    if (apiError.code === 'ACCOUNT_LOGIN_ID_EXISTS') fieldError.value = '这个账号已经注册过了'
    else error.value = apiError.message
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <MobileAuthShell
    v-if="optionsLoaded && enabled"
    title="注册账号"
    subtitle="手机号即登录号；验证码由账号服务下发，10 分钟内有效"
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
      <div
        v-if="fieldError"
        class="mb-3 rounded-xl border border-amber-400/40 bg-amber-400/10 px-3 py-2.5 text-[12px] text-amber-400"
      >
        {{ fieldError }}
        <router-link v-if="fieldError.includes('已经注册过')" to="/login" class="ml-1 underline decoration-dotted">
          去登录
        </router-link>
      </div>
    </template>

    <label class="mb-3.5 block">
      <span class="mb-1.5 block text-[12px] tracking-wide text-ink-300/85">手机号</span>
      <input
        v-model="form.loginId"
        class="field"
        inputmode="tel"
        autocomplete="username"
        placeholder="11 位手机号"
      />
    </label>

    <label class="mb-3.5 block">
      <span class="mb-1.5 block text-[12px] tracking-wide text-ink-300/85">验证码</span>
      <div class="flex items-stretch gap-2">
        <input
          v-model="form.verifyCode"
          class="field min-w-0 flex-1 tracking-[0.3em]"
          inputmode="numeric"
          maxlength="6"
          autocomplete="one-time-code"
          placeholder="6 位数字"
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

    <label class="mb-3.5 block">
      <span class="mb-1.5 block text-[12px] tracking-wide text-ink-300/85">密码</span>
      <div class="relative">
        <input
          v-model="form.passwd"
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

    <label class="mb-3.5 block">
      <span class="mb-1.5 block text-[12px] tracking-wide text-ink-300/85">确认密码</span>
      <input
        v-model="form.confirm"
        class="field"
        :type="showPasswd ? 'text' : 'password'"
        autocomplete="new-password"
        placeholder="再输入一次"
      />
    </label>

    <label class="mb-3.5 block">
      <span class="mb-1.5 block text-[12px] tracking-wide text-ink-300/85">昵称（可选）</span>
      <input v-model="form.nickName" class="field" maxlength="20" placeholder="比如 爸爸" />
    </label>

    <label class="mb-4 flex items-start gap-2 text-[11px] leading-relaxed text-ink-300/75">
      <input v-model="form.agreed" type="checkbox" class="mt-0.5 h-4 w-4 accent-gold-400" />
      <span>我已阅读并同意服务条款与隐私政策</span>
    </label>

    <button
      type="submit"
      class="mj-press btn-gold flex min-h-[48px] w-full items-center justify-center gap-2 rounded-xl text-[15px] font-semibold"
      :disabled="!canSubmit"
    >
      <Loader2 v-if="submitting" class="h-4 w-4 animate-spin" />
      <UserPlus v-else class="h-4 w-4" />
      {{ submitting ? '正在注册…' : '注册账号' }}
    </button>

    <p class="mt-4 text-center text-[12px] text-ink-300/70">
      已有账号？
      <router-link to="/login" class="text-gold-300">去登录</router-link>
    </p>
  </MobileAuthShell>

  <MobileAuthShell
    v-else-if="optionsLoaded"
    title="注册未开放"
    subtitle="当前环境关闭了自助注册，请联系家庭管理员开通账号"
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

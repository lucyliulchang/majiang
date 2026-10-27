import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { api, getStoredUser, getToken, setStoredUser, setToken } from '../api/http'
import type { AuthOptions, AuthSession, UserInfo } from '../types'

const DEFAULT_OPTIONS: AuthOptions = {
  register_enabled: false,
  password_reset_enabled: true,
  verify_code_cooldown_seconds: 60
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(getToken())
  const user = ref<UserInfo | null>(getStoredUser() as UserInfo | null)
  const families = ref<Record<string, unknown>[]>([])
  const currentFamilyCode = ref<string | null>(null)
  const loading = ref(false)
  const options = ref<AuthOptions>({ ...DEFAULT_OPTIONS })

  const isLoggedIn = computed(() => Boolean(token.value))
  const isAdmin = computed(() => user.value?.role === 'admin')
  const displayName = computed(() => user.value?.nick_name || user.value?.login_id || '家人')
  /** 头像底色：USER_BASIC 没有颜色列，统一用主题金色（S4 家庭成员页再按成员区分） */
  const avatarColor = computed(() => '#C9A063')
  /** 牌桌/聊天按 loginID 字符串关联（S5 起实时层与 REST 全部使用 login_id） */
  const loginId = computed(() => user.value?.login_id || '')

  function applySession(session: AuthSession): void {
    token.value = session.token
    user.value = session.user
    families.value = session.families ?? []
    currentFamilyCode.value = session.current_family_code ?? null
    setToken(session.token)
    setStoredUser(session.user)
  }

  async function login(loginId: string, passwd: string): Promise<void> {
    loading.value = true
    try {
      const result = await api.post<AuthSession>('/auth/login', {
        login_id: loginId,
        passwd
      })
      applySession(result)
    } finally {
      loading.value = false
    }
  }

  async function refresh(): Promise<void> {
    if (!token.value) return
    const me = await api.get<Omit<AuthSession, 'token'>>('/auth/me')
    user.value = me.user
    families.value = me.families ?? []
    currentFamilyCode.value = me.current_family_code ?? null
    setStoredUser(me.user)
  }

  async function loadOptions(): Promise<void> {
    try {
      options.value = await api.get<AuthOptions>('/auth/options')
    } catch {
      // 开关拿不到时按「最保守」渲染：不显示注册入口，保留忘记密码
      options.value = { ...DEFAULT_OPTIONS, register_enabled: false }
    }
  }

  function clear(): void {
    token.value = ''
    user.value = null
    families.value = []
    currentFamilyCode.value = null
    setToken('')
    setStoredUser(null)
  }

  async function logout(): Promise<void> {
    // A5A0 是尽力而为：本地永远先丢 JWT，账号服务不可达也不影响退出
    try {
      if (token.value) await api.post('/auth/logout')
    } catch {
      // 忽略：401/503 都按已退出处理
    } finally {
      clear()
    }
  }

  return {
    token,
    user,
    families,
    currentFamilyCode,
    loading,
    options,
    isLoggedIn,
    isAdmin,
    displayName,
    avatarColor,
    loginId,
    login,
    refresh,
    loadOptions,
    logout,
    clear
  }
})

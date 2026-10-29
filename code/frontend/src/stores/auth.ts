import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { api, getStoredUser, getToken, setStoredUser, setToken } from '../api/http'
import type { AuthOptions, AuthSession, FamilyInfo, UserInfo, UserPref } from '../types'

const DEFAULT_OPTIONS: AuthOptions = {
  register_enabled: false,
  password_reset_enabled: true,
  verify_code_cooldown_seconds: 60
}

/** 04 §4 的默认偏好（服务端返回前先按它渲染，避免闪烁） */
const DEFAULT_PREF: UserPref = {
  last_family_code: null,
  skin_code: null,
  sound_enabled: true,
  sound_volume: 70,
  chat_sound: true,
  show_tenpai: true
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(getToken())
  const user = ref<UserInfo | null>(getStoredUser() as UserInfo | null)
  const families = ref<FamilyInfo[]>([])
  const currentFamilyCode = ref<string | null>(null)
  const pref = ref<UserPref>({ ...DEFAULT_PREF })
  const loading = ref(false)
  const options = ref<AuthOptions>({ ...DEFAULT_OPTIONS })

  /** 会话信息是否已从 `/auth/me` 拉过（路由守卫据此决定要不要补一次） */
  const sessionLoaded = ref(false)
  let loadingSession: Promise<void> | null = null

  const isLoggedIn = computed(() => Boolean(token.value))
  const isAdmin = computed(() => user.value?.role === 'admin')
  const displayName = computed(() => user.value?.nick_name || user.value?.login_id || '家人')
  /** 头像底色：USER_BASIC 没有颜色列，统一用主题金色 */
  const avatarColor = computed(() => '#C9A063')
  /** 牌桌/聊天按 loginID 字符串关联（S5 起实时层与 REST 全部使用 login_id） */
  const loginId = computed(() => user.value?.login_id || '')
  const currentFamily = computed<FamilyInfo | null>(
    () => families.value.find((item) => item.family_code === currentFamilyCode.value) ?? null
  )
  const currentFamilyName = computed(
    () => currentFamily.value?.family_name || currentFamilyCode.value || '未选家庭'
  )
  const familyRole = computed(() => currentFamily.value?.member_role || '')
  /** 家庭管理员（OWNER/ADMIN）：皮肤管理入口按它判定，不是系统管理员 */
  const isFamilyAdmin = computed(() => ['OWNER', 'ADMIN'].includes(familyRole.value))
  /** 皮肤管理等入口：系统管理员或家庭管理员（05 §3） */
  const canManageSkins = computed(() => isAdmin.value || isFamilyAdmin.value)

  function applySession(session: AuthSession): void {
    token.value = session.token
    user.value = session.user
    families.value = session.families ?? []
    currentFamilyCode.value = session.current_family_code ?? null
    sessionLoaded.value = true
    setToken(session.token)
    setStoredUser(session.user)
  }

  async function login(loginId: string, passwd: string): Promise<void> {
    loading.value = true
    try {
      const result = await api.post<AuthSession>('/auth/login', {
        // 04 §2：登录字段为 login_id（服务端仍兼容 username 别名，前端只发新字段）
        login_id: loginId,
        passwd
      })
      applySession(result)
      await loadPref()
    } finally {
      loading.value = false
    }
  }

  /** 拉取会话（用户 + 我的家庭 + 当前家庭）；并发调用合并为一次请求 */
  async function refresh(): Promise<void> {
    if (!token.value) return
    if (loadingSession) return loadingSession
    loadingSession = (async () => {
      try {
        const me = await api.get<Omit<AuthSession, 'token'>>('/auth/me')
        user.value = me.user
        families.value = me.families ?? []
        currentFamilyCode.value = me.current_family_code ?? null
        sessionLoaded.value = true
        setStoredUser(me.user)
      } finally {
        loadingSession = null
      }
    })()
    return loadingSession
  }

  /** 路由守卫用：没拉过会话就先补一次（离线/失败不阻塞导航） */
  async function ensureSession(): Promise<void> {
    if (!token.value || sessionLoaded.value) return
    try {
      await refresh()
    } catch {
      // 401 由 http 层统一跳登录；其他错误留给页面自己提示
    }
  }

  async function loadPref(): Promise<void> {
    if (!token.value) return
    try {
      pref.value = await api.get<UserPref>('/user/pref')
    } catch {
      pref.value = { ...DEFAULT_PREF }
    }
  }

  /** 04 §4：局部更新偏好（`skin_code` 空串表示回到默认皮肤） */
  async function savePref(patch: Partial<UserPref>): Promise<UserPref> {
    const result = await api.put<UserPref>('/user/pref', patch)
    pref.value = result
    return result
  }

  /**
   * 切换当前家庭（04 §4：写 `last_family_code`，服务端校验成员关系）。
   * 切换只改本地 `currentFamilyCode`，各页 watch 它重新拉数据（无缓存串数据）。
   */
  async function switchFamily(familyCode: string): Promise<void> {
    const result = await api.put<UserPref>('/user/pref', { last_family_code: familyCode })
    pref.value = result
    currentFamilyCode.value = result.last_family_code || familyCode
  }

  async function loadOptions(): Promise<void> {
    try {
      options.value = await api.get<AuthOptions>('/auth/options')
    } catch {
      // 开关拿不到时按「最保守」渲染：不显示注册入口，保留忘记密码
      options.value = { ...DEFAULT_OPTIONS, register_enabled: false }
    }
  }

  /** 家庭列表变更（新建家庭）后同步会话里的 families */
  function setFamilies(list: FamilyInfo[], familyCode?: string | null): void {
    families.value = list
    if (familyCode !== undefined) currentFamilyCode.value = familyCode
    if (!families.value.some((item) => item.family_code === currentFamilyCode.value)) {
      currentFamilyCode.value = families.value[0]?.family_code ?? null
    }
  }

  function clear(): void {
    token.value = ''
    user.value = null
    families.value = []
    currentFamilyCode.value = null
    pref.value = { ...DEFAULT_PREF }
    sessionLoaded.value = false
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
    currentFamily,
    currentFamilyName,
    familyRole,
    pref,
    loading,
    options,
    isLoggedIn,
    isAdmin,
    isFamilyAdmin,
    canManageSkins,
    displayName,
    avatarColor,
    loginId,
    sessionLoaded,
    login,
    refresh,
    ensureSession,
    loadPref,
    savePref,
    switchFamily,
    setFamilies,
    loadOptions,
    logout,
    clear
  }
})

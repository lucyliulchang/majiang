import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { api, getStoredUser, getToken, setStoredUser, setToken } from '../api/http'
import type { UserInfo } from '../types'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(getToken())
  const user = ref<UserInfo | null>(getStoredUser() as UserInfo | null)
  const loading = ref(false)

  const isLoggedIn = computed(() => Boolean(token.value))
  const isAdmin = computed(() => user.value?.role === 'admin')
  const displayName = computed(() => user.value?.display_name || '家人')

  async function login(username: string, password: string): Promise<void> {
    loading.value = true
    try {
      const result = await api.post<{ token: string; user: UserInfo }>('/auth/login', {
        username,
        password
      })
      token.value = result.token
      user.value = result.user
      setToken(result.token)
      setStoredUser(result.user)
    } finally {
      loading.value = false
    }
  }

  async function refresh(): Promise<void> {
    if (!token.value) return
    const me = await api.get<UserInfo>('/auth/me')
    user.value = me
    setStoredUser(me)
  }

  function logout(): void {
    token.value = ''
    user.value = null
    setToken('')
    setStoredUser(null)
  }

  return { token, user, loading, isLoggedIn, isAdmin, displayName, login, refresh, logout }
})

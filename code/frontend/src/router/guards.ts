/**
 * 路由守卫（PC 与手机版共用）。
 *
 * 抽出来的原因：两套路由表都要「未登录跳登录 / 已登录别回登录页 / 没有当前家庭先选家庭」，
 * 分两处各写一份必然漂移（例如以后加了新的公开页只改了一边）。
 */
import type { Router } from 'vue-router'

import { getToken } from '../api/http'
import { useAuthStore } from '../stores/auth'

/** 已登录时不该停留的页面：统一回大厅（05 §3） */
const PUBLIC_AUTH_ROUTES = ['login', 'register', 'forgot-password']

export function installGuards(router: Router): void {
  router.beforeEach(async (to) => {
    const logged = Boolean(getToken())
    if (!to.meta.public && !logged) {
      return { name: 'login', query: { redirect: to.fullPath } }
    }
    if (logged && PUBLIC_AUTH_ROUTES.includes(String(to.name))) return { name: 'lobby' }
    if (!logged) return true

    const auth = useAuthStore()
    // 会话（用户 + 我的家庭 + 当前家庭）没拉过先补一次：直接刷新页面进 /rules 也能判守卫
    await auth.ensureSession()

    if (to.meta.requiresFamily && !auth.currentFamilyCode) {
      return { name: 'families', query: { redirect: to.fullPath } }
    }
    // 皮肤管理：家庭管理员或系统管理员（05 §3）
    if (to.meta.requiresAdmin && !auth.canManageSkins) {
      return { name: 'lobby' }
    }
    return true
  })

  router.afterEach((to) => {
    const title = (to.meta.title as string) || '家庭麻将'
    document.title = `${title} · 家庭麻将`
  })
}

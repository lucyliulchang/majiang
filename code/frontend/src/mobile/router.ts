import { createRouter, createWebHistory } from 'vue-router'

import { installGuards } from '../router/guards'

/**
 * 手机版路由：只包含「打牌闭环」的页面。
 * 规则模板编辑、皮肤管理、成员管理在手机端一律给「请用电脑」提示（见 DesktopOnlySheet）。
 */
const router = createRouter({
  // base 由构建模式决定：/mjmobile/（生产）或 /（本地 dev）
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('./views/MobileLoginView.vue'),
      meta: { public: true, title: '登录' }
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('./views/MobileRegisterView.vue'),
      meta: { public: true, title: '注册' }
    },
    {
      path: '/forgot-password',
      name: 'forgot-password',
      component: () => import('./views/MobileForgotPasswordView.vue'),
      meta: { public: true, title: '找回密码' }
    },
    {
      path: '/',
      name: 'lobby',
      component: () => import('./views/MobileLobbyView.vue'),
      meta: { title: '大厅', requiresFamily: true }
    },
    {
      path: '/families',
      name: 'families',
      component: () => import('./views/MobileFamiliesView.vue'),
      meta: { title: '我的家庭' }
    },
    {
      path: '/history',
      name: 'history',
      component: () => import('./views/MobileHistoryView.vue'),
      meta: { title: '战绩', requiresFamily: true }
    },
    {
      // 牌桌自带家庭上下文：凭邀请码可进任意家庭的房间
      path: '/room/:code',
      name: 'room',
      component: () => import('./views/MobileRoomView.vue'),
      meta: { title: '牌桌' }
    },
    { path: '/:pathMatch(.*)*', redirect: '/' }
  ]
})

installGuards(router)

export default router

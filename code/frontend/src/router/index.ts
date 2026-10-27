import { createRouter, createWebHistory } from 'vue-router'

import { getToken } from '../api/http'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { public: true, title: '登录' }
    },
    {
      path: '/',
      name: 'lobby',
      component: () => import('../views/LobbyView.vue'),
      meta: { title: '大厅' }
    },
    {
      path: '/rules',
      name: 'rules',
      component: () => import('../views/RulesView.vue'),
      meta: { title: '规则模板' }
    },
    {
      path: '/room/:code',
      name: 'room',
      component: () => import('../views/RoomView.vue'),
      meta: { title: '牌桌' }
    },
    {
      path: '/history',
      name: 'history',
      component: () => import('../views/HistoryView.vue'),
      meta: { title: '战绩' }
    },
    { path: '/:pathMatch(.*)*', redirect: '/' }
  ]
})

router.beforeEach((to) => {
  const logged = Boolean(getToken())
  if (!to.meta.public && !logged) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && logged) return { name: 'lobby' }
  return true
})

router.afterEach((to) => {
  const title = (to.meta.title as string) || '家庭麻将'
  document.title = `${title} · 家庭麻将`
})

export default router

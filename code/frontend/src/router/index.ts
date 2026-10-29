import { createRouter, createWebHistory } from 'vue-router'

import { installGuards } from './guards'

const router = createRouter({
  // 与 vite base 对齐：部署在 /majiangapp/ 下时，刷新子路由才不会 404
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { public: true, title: '登录' }
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('../views/RegisterView.vue'),
      meta: { public: true, title: '注册' }
    },
    {
      path: '/forgot-password',
      name: 'forgot-password',
      component: () => import('../views/ForgotPasswordView.vue'),
      meta: { public: true, title: '找回密码' }
    },
    {
      path: '/families',
      name: 'families',
      component: () => import('../views/FamilyView.vue'),
      meta: { title: '我的家庭' }
    },
    {
      // 家庭成员管理：页面内部校验「是不是这个家庭的 OWNER/ADMIN」
      path: '/families/:familyCode/members',
      name: 'family-members',
      component: () => import('../views/FamilyMembersView.vue'),
      meta: { title: '家庭成员' }
    },
    {
      path: '/',
      name: 'lobby',
      component: () => import('../views/LobbyView.vue'),
      meta: { title: '大厅', requiresFamily: true }
    },
    {
      path: '/rules',
      name: 'rules',
      component: () => import('../views/RulesView.vue'),
      meta: { title: '规则模板', requiresFamily: true }
    },
    {
      // 房间自带家庭上下文：凭邀请码可进任意家庭的房间，不再要求「当前家庭」
      path: '/room/:code',
      name: 'room',
      component: () => import('../views/RoomView.vue'),
      meta: { title: '牌桌' }
    },
    {
      path: '/history',
      name: 'history',
      component: () => import('../views/HistoryView.vue'),
      meta: { title: '战绩', requiresFamily: true }
    },
    {
      path: '/admin/skins',
      name: 'skins',
      component: () => import('../views/admin/SkinsView.vue'),
      meta: { title: '皮肤管理', requiresFamily: true, requiresAdmin: true }
    },
    {
      path: '/admin/skins/:skinCode',
      name: 'skin-edit',
      component: () => import('../views/admin/SkinEditView.vue'),
      meta: { title: '皮肤资源', requiresFamily: true, requiresAdmin: true }
    },
    { path: '/:pathMatch(.*)*', redirect: '/' }
  ]
})

installGuards(router)

export default router

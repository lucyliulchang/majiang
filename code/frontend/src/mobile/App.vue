<script setup lang="ts">
import { watch } from 'vue'
import { useRouter } from 'vue-router'

import ToastHost from '../components/ToastHost.vue'
import { onUnauthorized } from '../api/http'
import { refreshSoundPrefs } from '../audio/soundPrefs'
import { useAuthStore } from '../stores/auth'
import { useSkinsStore } from '../stores/skins'

/**
 * 手机版外壳：与 PC 的 App.vue 保持同一套「登录态 → 会话/偏好/皮肤」时序，
 * 只是把容器换成 100dvh 的单列布局（iOS 地址栏收放不会把底部 Tab 顶飞）。
 */
const router = useRouter()
const auth = useAuthStore()
const skins = useSkinsStore()

onUnauthorized(() => {
  // 这里只清本地：再调 /auth/logout 会拿到 401 而再次触发本回调
  auth.clear()
  if (router.currentRoute.value.name !== 'login') {
    router.replace({ name: 'login' })
  }
})

// 登录拿到 token 后，用服务端偏好覆盖 localStorage（08 §5）
let lastToken = ''
watch(
  () => auth.token,
  async (token) => {
    if (!token) {
      lastToken = ''
      skins.reset()
      return
    }
    if (token === lastToken) return
    lastToken = token
    void refreshSoundPrefs()
    await auth.ensureSession()
    await auth.loadPref()
    skins.syncWithPref()
  },
  { immediate: true }
)

// 切家庭：皮肤清单必须失效重拉，否则牌面会串到上一个家庭（04 §8）
watch(
  () => auth.currentFamilyCode,
  (code) => {
    skins.reset()
    if (code) void skins.load()
  },
  { immediate: true }
)
</script>

<template>
  <div class="mj-app mj-root">
    <router-view v-slot="{ Component }">
      <transition name="mj-page" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>
    <ToastHost />
  </div>
</template>

<style scoped>
.mj-page-enter-active,
.mj-page-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.mj-page-enter-from {
  opacity: 0;
  transform: translateY(10px);
}
.mj-page-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>

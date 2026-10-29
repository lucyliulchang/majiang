<script setup lang="ts">
import { watch } from 'vue'
import { useRouter } from 'vue-router'

import ToastHost from './components/ToastHost.vue'
import { onUnauthorized } from './api/http'
import { refreshSoundPrefs } from './audio/soundPrefs'
import { useAuthStore } from './stores/auth'
import { useSkinsStore } from './stores/skins'

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
    try {
      await auth.ensureSession()
      await auth.loadPref()
      // 偏好里的 skin_code 可能晚于皮肤清单到达：到达后校正选中项
      skins.syncWithPref()
    } catch {
      // 401 由 http 层统一跳登录；其余错误留给页面提示
    }
  },
  { immediate: true }
)

// 切家庭：皮肤清单必须失效重拉，否则牌面会串到上一个家庭（04 §8）
watch(
  () => auth.currentFamilyCode,
  (code) => {
    if (!code) {
      skins.reset()
      return
    }
    skins.reset()
    void skins.load()
  },
  { immediate: true }
)
</script>

<template>
  <div class="min-h-screen">
    <router-view v-slot="{ Component }">
      <transition name="page" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>
    <ToastHost />
  </div>
</template>

<style scoped>
.page-enter-active,
.page-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}
.page-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.page-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>

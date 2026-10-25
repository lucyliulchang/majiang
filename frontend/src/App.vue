<script setup lang="ts">
import { useRouter } from 'vue-router'

import ToastHost from './components/ToastHost.vue'
import { onUnauthorized } from './api/http'
import { useAuthStore } from './stores/auth'

const router = useRouter()
const auth = useAuthStore()

onUnauthorized(() => {
  auth.logout()
  if (router.currentRoute.value.name !== 'login') {
    router.replace({ name: 'login' })
  }
})
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

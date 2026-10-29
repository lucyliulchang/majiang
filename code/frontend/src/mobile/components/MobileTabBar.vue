<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { History, LayoutGrid, Users } from 'lucide-vue-next'

/**
 * 底部 Tab：大厅 / 战绩 / 家庭。
 * 牌桌页不挂 TabBar（横屏沉浸），所以这个组件只在竖屏页面出现。
 */
const route = useRoute()
const router = useRouter()

const items = [
  { name: 'lobby', label: '大厅', icon: LayoutGrid },
  { name: 'history', label: '战绩', icon: History },
  { name: 'families', label: '家庭', icon: Users }
]

function go(name: string): void {
  if (route.name === name) return
  void router.push({ name })
}
</script>

<template>
  <nav class="mj-safe-b fixed inset-x-0 bottom-0 z-40 mj-bar-bottom">
    <div class="flex h-[60px] items-stretch">
      <button
        v-for="item in items"
        :key="item.name"
        type="button"
        class="mj-press relative flex flex-1 flex-col items-center justify-center gap-0.5"
        :class="route.name === item.name ? 'text-gold-300' : 'text-ink-300/70'"
        :aria-current="route.name === item.name ? 'page' : undefined"
        @click="go(item.name)"
      >
        <span
          v-if="route.name === item.name"
          class="absolute inset-x-6 top-0 h-[2px] rounded-full bg-gold-400/80"
          aria-hidden="true"
        />
        <component :is="item.icon" class="h-5 w-5" />
        <span class="text-[11px] leading-none">{{ item.label }}</span>
      </button>
    </div>
  </nav>
</template>

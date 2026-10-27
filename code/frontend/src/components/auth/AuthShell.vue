<script setup lang="ts">
import { computed } from 'vue'

import Tile from '../table/Tile.vue'

const props = defineProps<{
  title: string
  subtitle?: string
  /** 卡片宽度档位：登录/注册用 md，找回口令用 sm */
  width?: 'sm' | 'md'
}>()

defineEmits<{ submit: [] }>()

const gridClass = computed(() =>
  props.width === 'sm'
    ? 'max-w-4xl md:grid-cols-[1fr_0.85fr]'
    : 'max-w-5xl md:grid-cols-[1.05fr_0.95fr]'
)

const floating = [
  { tile: 31, className: 'left-[8%] top-[16%]', tilt: '-12deg', delay: '0s' },
  { tile: 4, className: 'left-[26%] top-[52%]', tilt: '8deg', delay: '1.2s' },
  { tile: 13, className: 'right-[18%] top-[24%]', tilt: '14deg', delay: '0.6s' },
  { tile: 22, className: 'right-[30%] bottom-[18%]', tilt: '-6deg', delay: '2s' },
  { tile: 33, className: 'left-[46%] top-[8%]', tilt: '4deg', delay: '1.6s' }
]
</script>

<template>
  <div class="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10">
    <div class="pointer-events-none absolute inset-0">
      <div
        v-for="item in floating"
        :key="item.tile"
        class="absolute opacity-[0.13] animate-floaty blur-[0.4px]"
        :class="item.className"
        :style="{ '--tilt': item.tilt, animationDelay: item.delay }"
      >
        <Tile :tile="item.tile" size="lg" class="scale-[2.4]" />
      </div>
      <div
        class="absolute left-1/2 top-1/2 h-[520px] w-[520px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-gold-400/[0.06] blur-3xl"
      />
    </div>

    <div class="relative grid w-full gap-10" :class="gridClass">
      <!-- 品牌区（窄屏隐藏，只留卡片） -->
      <div class="hidden md:block">
        <div class="mb-5 flex items-center gap-2 text-[11px] tracking-[0.4em] text-gold-400/80">
          <span class="h-px w-8 bg-gold-400/50" />
          FAMILY MAHJONG
        </div>
        <h1 class="font-num text-6xl font-bold leading-tight text-gold-gradient">家庭麻将</h1>
        <p class="mt-4 max-w-md text-[15px] leading-relaxed text-ink-300/85">
          一家人，一张桌。规则自己定，牌局自动算——从开局到结算，分数明明白白，聊天热热闹闹。
        </p>
        <div class="mt-8 grid max-w-md grid-cols-3 gap-3">
          <div
            v-for="item in [
              { title: '自定义规则', desc: '底分、番种、杠分随你' },
              { title: '自动算番', desc: '判胡算分不会错' },
              { title: '实时闲聊', desc: '碰杠胡全桌都知道' }
            ]"
            :key="item.title"
            class="glass-soft rounded-xl px-3 py-2.5"
          >
            <p class="text-xs font-medium text-gold-300">{{ item.title }}</p>
            <p class="mt-0.5 text-[11px] text-ink-300/70">{{ item.desc }}</p>
          </div>
        </div>
      </div>

      <!-- 表单区 -->
      <div class="relative">
        <slot name="alerts" />

        <form class="glass rounded-2xl p-7 shadow-table" @submit.prevent="$emit('submit')">
          <div class="mb-6">
            <h2 class="text-lg font-semibold text-cream-100">{{ title }}</h2>
            <p v-if="subtitle" class="mt-1 text-[11px] leading-relaxed text-ink-300/70">
              {{ subtitle }}
            </p>
          </div>
          <slot />
        </form>

        <div class="mt-4 flex items-center justify-between px-1 text-[11px] text-ink-300/60">
          <slot name="footer">
            <span class="flex items-center gap-1.5">
              <span class="h-1.5 w-1.5 rounded-full bg-jade-400" />
              服务正常
            </span>
          </slot>
        </div>
      </div>
    </div>
  </div>
</template>

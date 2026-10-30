<script setup lang="ts">
import { computed, watch } from 'vue'
import { Check, Copy, DoorOpen, Flag, Palette, Play, ScrollText, Volume2, VolumeX } from 'lucide-vue-next'

import MobileSheet from '../MobileSheet.vue'
import { audioManager, audioState } from '../../../audio/audioManager'
import { setChatSound, setSoundEnabled, setSoundVolume, soundPrefs } from '../../../audio/soundPrefs'
import { CSS_CLASSIC, useSkinsStore } from '../../../stores/skins'
import type { RuleBrief } from '../../../types'

/**
 * 牌桌「更多」抽屉：把 PC 顶栏上那堆按钮（规则、皮肤、音效、结束牌局、离桌）
 * 全部收进一张底部抽屉，横屏顶栏只留一条信息带。
 */
const props = defineProps<{
  open: boolean
  code: string
  ruleName: string
  ruleBrief: RuleBrief | null
  canEndGame: boolean
  /** 按钮文案：进行中是「结束本场牌局」，打满后是「关闭牌桌」（B-1） */
  endGameLabel?: string
}>()

const emit = defineEmits<{ close: []; copy: []; exit: []; endGame: [] }>()

const skins = useSkinsStore()
const endText = computed(() => props.endGameLabel || '结束本场牌局')

watch(
  () => props.open,
  (open) => {
    if (open) void skins.ensureLoaded()
  }
)

const skinOptions = computed(() =>
  [
    { skin_code: CSS_CLASSIC, skin_name: '经典（CSS 牌面）', preview_url: null as string | null, is_default: false }
  ].concat(
    skins.enabledSkins.map((item) => ({
      skin_code: item.skin_code,
      skin_name: item.skin_name,
      preview_url: item.preview_url || item.assets['1m'] || null,
      is_default: item.is_default
    }))
  )
)

const timeoutText = computed(() => {
  const brief = props.ruleBrief
  if (!brief) return '—'
  return brief.turn_timeout.enabled ? `${brief.turn_timeout.seconds} 秒` : '不限时'
})

const kongText = computed(() => {
  const brief = props.ruleBrief
  if (!brief) return '—'
  const kong = brief.kong_score
  if (!kong.enabled) return '不计分'
  return `明${kong.exposed} / 暗${kong.hidden} / 补${kong.added}`
})

const modeText = computed(() => (props.ruleBrief?.fan_mode === 'exponential' ? '2 的 N 次方' : '线性累加'))

function pickSkin(skinCode: string): void {
  void skins.setActive(skinCode)
}

function onVolumeInput(event: Event): void {
  setSoundVolume(Number((event.target as HTMLInputElement).value))
}

function previewDiscard(): void {
  audioManager.unlock()
  audioManager.preview('discard')
}
</script>

<template>
  <MobileSheet :open="open" title="牌桌设置" :subtitle="`${ruleName} · 只影响你自己这台设备`" max-height="88vh" @close="emit('close')">
    <div class="space-y-4 pt-1">
      <!-- 规则 -->
      <section class="mj-card-flat p-3">
        <p class="mb-2 flex items-center gap-1.5 text-[12px] font-medium text-gold-300">
          <ScrollText class="h-3.5 w-3.5" />
          本局规则
        </p>
        <dl class="space-y-1 text-[11px] text-ink-300/85">
          <div class="flex justify-between"><dt>底分</dt><dd class="text-cream-100">{{ ruleBrief?.base_score ?? '—' }}</dd></div>
          <div class="flex justify-between"><dt>番数算法</dt><dd class="text-cream-100">{{ modeText }}</dd></div>
          <div class="flex justify-between">
            <dt>封顶</dt>
            <dd class="text-cream-100">{{ ruleBrief?.fan_cap === null || ruleBrief?.fan_cap === undefined ? '不封顶' : `${ruleBrief.fan_cap} 番` }}</dd>
          </div>
          <div class="flex justify-between"><dt>吃牌</dt><dd class="text-cream-100">{{ ruleBrief?.allow_chow ? '允许' : '不允许' }}</dd></div>
          <div class="flex justify-between"><dt>出牌限时</dt><dd class="text-cream-100">{{ timeoutText }}</dd></div>
          <div class="flex justify-between"><dt>杠分</dt><dd class="text-cream-100">{{ kongText }}</dd></div>
          <div class="flex justify-between"><dt>听牌提示</dt><dd class="text-cream-100">{{ ruleBrief?.ting_hint ? '开启' : '关闭' }}</dd></div>
        </dl>
        <p class="mt-2 border-t border-cream-100/10 pt-2 text-[10px] leading-relaxed text-ink-300/65">
          牌型：{{ (ruleBrief?.patterns || []).join('、') || '—' }}
        </p>
      </section>

      <!-- 皮肤 -->
      <section>
        <p class="mb-2 flex items-center gap-1.5 text-[12px] font-medium text-gold-300">
          <Palette class="h-3.5 w-3.5" />
          牌面皮肤
        </p>
        <div class="space-y-1.5">
          <button
            v-for="option in skinOptions"
            :key="option.skin_code"
            type="button"
            class="mj-press flex w-full items-center gap-2.5 rounded-xl border px-2.5 py-2 text-left"
            :class="skins.activeCode === option.skin_code ? 'border-skin/60 bg-skin/15' : 'border-cream-100/10 bg-cream-100/[0.03]'"
            @click="pickSkin(option.skin_code)"
          >
            <span class="flex h-9 w-7 shrink-0 items-center justify-center overflow-hidden rounded border border-gold-400/25 bg-cream-100/10">
              <img v-if="option.preview_url" :src="option.preview_url" alt="" class="h-full w-full object-contain" loading="lazy" />
              <span v-else class="text-[9px] text-ink-300/70">CSS</span>
            </span>
            <span class="min-w-0 flex-1">
              <span class="block truncate text-[12px] text-cream-100">{{ option.skin_name }}</span>
              <span class="block truncate text-[10px] text-ink-300/60">{{ option.is_default ? '家庭默认' : option.skin_code }}</span>
            </span>
            <Check v-if="skins.activeCode === option.skin_code" class="h-4 w-4 shrink-0 text-gold-300" />
          </button>
        </div>
        <p class="mt-1.5 text-[10px] text-ink-300/50">上传与管理牌面图片请用电脑版（/majiangapp/）</p>
      </section>

      <!-- 音效 -->
      <section class="mj-card-flat p-3">
        <div class="mb-2.5 flex items-center justify-between">
          <p class="flex items-center gap-1.5 text-[12px] font-medium text-gold-300">
            <Volume2 v-if="soundPrefs.enabled" class="h-3.5 w-3.5" />
            <VolumeX v-else class="h-3.5 w-3.5" />
            音效
          </p>
          <button
            type="button"
            role="switch"
            :aria-checked="soundPrefs.enabled"
            aria-label="全部音效开关"
            class="relative h-7 w-12 shrink-0 rounded-full transition"
            :class="soundPrefs.enabled ? 'bg-gold-400' : 'bg-cream-100/15'"
            @click="setSoundEnabled(!soundPrefs.enabled)"
          >
            <span
              class="absolute top-1 h-5 w-5 rounded-full bg-felt-950 shadow transition-all"
              :class="soundPrefs.enabled ? 'left-[26px]' : 'left-1'"
            />
          </button>
        </div>

        <div class="mb-2.5">
          <div class="mb-1 flex items-center justify-between text-[11px]">
            <span :class="soundPrefs.enabled ? 'text-cream-100' : 'text-ink-300/50'">音量</span>
            <span class="font-num text-gold-300">{{ soundPrefs.volume }}</span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            step="5"
            :value="soundPrefs.volume"
            :disabled="!soundPrefs.enabled"
            aria-label="音效音量"
            class="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-cream-100/15 accent-gold-400 disabled:cursor-not-allowed disabled:opacity-40"
            @input="onVolumeInput"
          />
        </div>

        <div class="flex items-center justify-between gap-2 border-t border-cream-100/10 pt-2.5">
          <span class="text-[11px] text-cream-100/90">聊天提示音</span>
          <button
            type="button"
            role="switch"
            :aria-checked="soundPrefs.chat"
            aria-label="聊天提示音开关"
            class="relative h-7 w-12 shrink-0 rounded-full transition"
            :class="soundPrefs.chat ? 'bg-gold-400' : 'bg-cream-100/15'"
            @click="setChatSound(!soundPrefs.chat)"
          >
            <span
              class="absolute top-1 h-5 w-5 rounded-full bg-felt-950 shadow transition-all"
              :class="soundPrefs.chat ? 'left-[26px]' : 'left-1'"
            />
          </button>
        </div>

        <button
          type="button"
          class="mj-press btn-ghost mt-2.5 flex min-h-[40px] w-full items-center justify-center gap-1.5 rounded-xl text-[12px]"
          :disabled="!soundPrefs.enabled"
          @click="previewDiscard"
        >
          <Play class="h-3.5 w-3.5" />
          试听（出牌声）
        </button>

        <p class="mt-2 text-[10px] leading-relaxed text-ink-300/55">
          {{ audioState.unlocked ? '音频已解锁，进桌时预加载全部音效' : '浏览器要求先点一下页面才允许出声，点任意位置即可解锁' }}
        </p>
      </section>

      <!-- 动作 -->
      <section class="space-y-2">
        <button
          type="button"
          class="mj-press btn-ghost flex min-h-[46px] w-full items-center justify-center gap-1.5 rounded-xl text-[13px]"
          @click="emit('copy')"
        >
          <Copy class="h-4 w-4" />
          复制邀请码 {{ code }}
        </button>
        <button
          v-if="canEndGame"
          type="button"
          class="mj-press flex min-h-[46px] w-full items-center justify-center gap-1.5 rounded-xl border border-vermilion-500/40 bg-vermilion-500/10 text-[13px] text-vermilion-400"
          @click="emit('endGame')"
        >
          <Flag class="h-4 w-4" />
          {{ endText }}
        </button>
        <button
          type="button"
          class="mj-press btn-ghost flex min-h-[46px] w-full items-center justify-center gap-1.5 rounded-xl text-[13px]"
          @click="emit('exit')"
        >
          <DoorOpen class="h-4 w-4" />
          离桌回大厅
        </button>
      </section>
    </div>
  </MobileSheet>
</template>

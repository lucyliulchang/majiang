<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Check, ChevronDown, Copy, DoorOpen, Flag, Palette, Play, ScrollText, Volume2, VolumeX, Wifi, WifiOff } from 'lucide-vue-next'

import { audioManager, audioState } from '../../audio/audioManager'
import { setChatSound, setSoundEnabled, setSoundVolume, soundPrefs } from '../../audio/soundPrefs'
import { CSS_CLASSIC, useSkinsStore } from '../../stores/skins'
import type { RuleBrief } from '../../types'

const props = defineProps<{
  roomName: string
  code: string
  ruleName: string
  ruleBrief: RuleBrief | null
  wallCount: number
  roundNo: number
  /** 一圈几个庄次（固定 4，04 §9.5 的 rounds_per_circle） */
  totalRounds: number
  /** 本圈第几局（1–4）；缺省退回 roundNo（老快照） */
  roundInCircle?: number | null
  /** 本场第几圈 / 共几圈（v1.1.0）；totalCircles<=1 时只显示局数 */
  circleNo?: number | null
  totalCircles?: number | null
  /** 本局是否连庄（庄家胡牌后庄位与局风不变） */
  dealerContinue?: boolean
  connected: boolean
  /** 家庭徽标（05 §4.5）；观战/断线时也只读展示 */
  familyName?: string
  familyCode?: string
  /** 本局局风 0 东 / 1 南 / 2 西 / 3 北（04 §9.5 的 round_wind） */
  roundWind?: number | null
  dealerName?: string | null
  /** 开桌的人且牌局进行中时，顶栏多一个「结束牌局」入口（提前收场） */
  canEndGame?: boolean
  /** 按钮文案：进行中是「结束牌局」，打满后是「关闭牌桌」（B-1） */
  endGameLabel?: string
}>()

const emit = defineEmits<{ exit: []; copy: []; endGame: [] }>()

const endText = computed(() => props.endGameLabel || '结束牌局')

const open = ref(false)
const skins = useSkinsStore()

// ---- 皮肤（仅自己的偏好；切换即时生效，不刷新牌桌）----
const skinOpen = ref(false)
const skinWrap = ref<HTMLElement | null>(null)

const skinOptions = computed(() =>
  [
    {
      skin_code: CSS_CLASSIC,
      skin_name: '经典（CSS 牌面）',
      preview_url: null as string | null,
      is_default: false
    }
  ].concat(
    skins.enabledSkins.map((item) => ({
      skin_code: item.skin_code,
      skin_name: item.skin_name,
      preview_url: item.preview_url || item.assets['1m'] || null,
      is_default: item.is_default
    }))
  )
)

function toggleSkinPanel(): void {
  skinOpen.value = !skinOpen.value
  if (skinOpen.value) void skins.ensureLoaded()
}

function pickSkin(skinCode: string): void {
  skinOpen.value = false
  void skins.setActive(skinCode)
}

const WIND_TEXT = ['东', '南', '西', '北']
const roundWindText = computed(() => {
  const wind = props.roundWind
  if (wind === null || wind === undefined) return ''
  return `${WIND_TEXT[wind] || ''}风局`
})

// 圈 / 局进度（v1.1.0）：多圈时显示「第 2/4 圈 · 第 3/4 局」，单圈只显示局数
const roundProgress = computed(() => {
  const inCircle = props.roundInCircle ?? props.roundNo
  const total = props.totalRounds || 4
  const circles = props.totalCircles ?? 1
  const circle = props.circleNo ?? 1
  if (circles <= 1) {
    return { num: inCircle, total, circleText: '' }
  }
  return {
    num: inCircle,
    total,
    circleText: `第 ${circle} / ${circles} 圈`
  }
})

// ---- 音效（仅 SFX，无 BGM）----
const soundOpen = ref(false)
const soundWrap = ref<HTMLElement | null>(null)

function toggleSoundPanel(): void {
  soundOpen.value = !soundOpen.value
  // 点击本身就是用户手势：顺手解锁 AudioContext
  if (soundOpen.value) audioManager.unlock()
}

function toggleSoundEnabled(): void {
  setSoundEnabled(!soundPrefs.enabled)
}

function toggleChatSound(): void {
  setChatSound(!soundPrefs.chat)
}

function onVolumeInput(event: Event): void {
  const value = Number((event.target as HTMLInputElement).value)
  setSoundVolume(value)
}

function previewDiscard(): void {
  audioManager.unlock()
  audioManager.preview('discard')
}

function onDocPointerDown(event: PointerEvent): void {
  const target = event.target as Node | null
  if (soundOpen.value && !(soundWrap.value && target && soundWrap.value.contains(target))) {
    soundOpen.value = false
  }
  if (skinOpen.value && !(skinWrap.value && target && skinWrap.value.contains(target))) {
    skinOpen.value = false
  }
}

onMounted(() => document.addEventListener('pointerdown', onDocPointerDown, true))
onBeforeUnmount(() => document.removeEventListener('pointerdown', onDocPointerDown, true))

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

const modeText = computed(() =>
  props.ruleBrief?.fan_mode === 'exponential' ? '2 的 N 次方' : '线性累加'
)
</script>

<template>
  <div class="relative flex w-full flex-wrap items-center gap-x-3 gap-y-1">
    <div class="flex min-w-0 items-center gap-2">
      <span class="max-w-[30vw] truncate text-sm font-semibold text-cream-100 sm:max-w-none sm:text-base">{{ roomName }}</span>
      <button
        type="button"
        class="flex shrink-0 items-center gap-1 rounded-md border border-gold-400/30 bg-gold-400/10 px-2 py-0.5 font-mono text-xs tracking-[0.18em] text-gold-300 transition hover:bg-gold-400/20"
        @click="emit('copy')"
      >
        {{ code }}
        <Copy class="h-3 w-3" />
      </button>
      <!-- 家庭徽标：一眼看出这桌属于哪个家 -->
      <span
        v-if="familyName"
        class="badge-family hidden shrink-0 sm:inline-flex"
        :title="familyCode ? `家庭编码 ${familyCode}` : familyName"
      >
        {{ familyName }}
      </span>
    </div>

    <button
      type="button"
      class="flex items-center gap-1.5 rounded-full border border-cream-100/15 bg-cream-100/5 px-3 py-1 text-xs text-cream-100/90 transition hover:border-gold-400/40"
      @click="open = !open"
    >
      <ScrollText class="h-3.5 w-3.5 shrink-0 text-gold-300" />
      <span class="max-w-[36vw] truncate sm:max-w-none">{{ ruleName }}</span>
      <span class="hidden text-ink-300/70 sm:inline">· 底分 {{ ruleBrief?.base_score ?? '—' }} · {{ timeoutText }}</span>
      <ChevronDown class="h-3.5 w-3.5 shrink-0 transition" :class="open ? 'rotate-180' : ''" />
    </button>

    <div class="ml-auto flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-300/80 sm:gap-x-4">
      <span class="whitespace-nowrap" :title="dealerContinue ? `一圈 ${totalRounds} 个庄次，庄家胡牌连庄局数顺延` : ''">
        <template v-if="roundWindText">{{ roundWindText }} · </template>
        <template v-if="roundProgress.circleText">{{ roundProgress.circleText }} · </template>
        第 <b class="font-num text-cream-100">{{ roundProgress.num }}</b> / {{ roundProgress.total }} 局<template
          v-if="dealerContinue"
        >
          （连庄）</template
        >
      </span>
      <span v-if="dealerName" class="hidden whitespace-nowrap md:inline">庄家 {{ dealerName }}</span>
      <span class="whitespace-nowrap">牌墙 <b class="font-num text-gold-300">{{ wallCount }}</b></span>
      <span class="flex items-center gap-1" :class="connected ? 'text-jade-400' : 'text-vermilion-400'">
        <Wifi v-if="connected" class="h-3.5 w-3.5" />
        <WifiOff v-else class="h-3.5 w-3.5" />
        <span class="hidden sm:inline">{{ connected ? '已连接' : '重连中' }}</span>
      </span>

      <!-- 皮肤：仅自己的偏好，切换即时生效（05 §4.5、§6.4） -->
      <div ref="skinWrap" class="relative">
        <button
          type="button"
          class="flex items-center gap-1 rounded-lg border px-2.5 py-1 transition"
          :class="
            !skins.isCssClassic
              ? 'border-skin/60 bg-skin/15 text-cream-50 hover:bg-skin/25'
              : 'border-cream-100/15 bg-cream-100/5 text-ink-300/70 hover:border-skin/50'
          "
          :aria-expanded="skinOpen"
          aria-label="切换牌面皮肤"
          @click="toggleSkinPanel"
        >
          <Palette class="h-3.5 w-3.5" />
          <span class="hidden sm:inline">皮肤</span>
        </button>

        <transition name="drop">
          <div
            v-if="skinOpen"
            class="absolute right-0 top-full z-40 mt-1 w-[240px] rounded-xl border border-gold-400/25 bg-felt-950/97 p-2 text-xs shadow-table backdrop-blur sm:mt-2"
          >
            <p class="px-1 pb-1 text-[10px] tracking-[0.2em] text-gold-400/70">牌面皮肤</p>
            <button
              v-for="option in skinOptions"
              :key="option.skin_code"
              type="button"
              class="flex w-full items-center gap-2 rounded-lg px-1.5 py-1.5 text-left transition"
              :class="skins.activeCode === option.skin_code ? 'bg-skin/15 text-cream-50' : 'hover:bg-cream-100/[0.06]'"
              @click="pickSkin(option.skin_code)"
            >
              <span class="flex h-8 w-6 shrink-0 items-center justify-center overflow-hidden rounded border border-gold-400/25 bg-cream-100/10">
                <img v-if="option.preview_url" :src="option.preview_url" alt="" class="h-full w-full object-contain" loading="lazy" />
                <span v-else class="text-[9px] text-ink-300/70">CSS</span>
              </span>
              <span class="min-w-0 flex-1">
                <span class="block truncate text-[12px] text-cream-100">{{ option.skin_name }}</span>
                <span class="block truncate text-[10px] text-ink-300/60">
                  {{ option.is_default ? '家庭默认' : option.skin_code }}
                </span>
              </span>
              <Check v-if="skins.activeCode === option.skin_code" class="h-3.5 w-3.5 shrink-0 text-gold-300" />
            </button>
            <p v-if="skins.loading" class="px-1 py-2 text-center text-[10px] text-ink-300/60">加载皮肤…</p>
          </div>
        </transition>
      </div>

      <!-- 音效入口：仅自己的偏好，不影响他人；无 BGM 开关 -->
      <div ref="soundWrap" class="static sm:relative">
        <button
          type="button"
          class="relative flex items-center gap-1 rounded-lg border px-2.5 py-1 transition"
          :class="
            soundPrefs.enabled
              ? 'border-gold-400/35 bg-gold-400/10 text-gold-300 hover:bg-gold-400/20'
              : 'border-cream-100/15 bg-cream-100/5 text-ink-300/70 hover:border-gold-400/30'
          "
          :aria-label="soundPrefs.enabled ? '音效设置（已开启）' : '音效设置（已关闭）'"
          :aria-expanded="soundOpen"
          @click="toggleSoundPanel"
        >
          <Volume2 v-if="soundPrefs.enabled" class="h-3.5 w-3.5" />
          <VolumeX v-else class="h-3.5 w-3.5" />
          音效
          <span
            v-if="!audioState.unlocked"
            class="absolute -right-1.5 -top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-gold-400 text-[10px] font-bold leading-none text-felt-950"
            aria-label="音频未解锁"
          >
            ♪
          </span>
        </button>

        <transition name="drop">
          <div
            v-if="soundOpen"
            data-sound-panel
            class="absolute left-0 right-0 top-full z-40 mt-1 max-h-[70vh] overflow-y-auto rounded-xl border border-gold-400/25 bg-felt-950/95 p-4 text-xs shadow-table backdrop-blur sm:left-auto sm:right-0 sm:mt-2 sm:w-[320px]"
          >
            <div class="mb-3 flex items-center justify-between">
              <p class="text-sm font-medium text-gold-300">音效</p>
              <span class="rounded-full border border-cream-100/15 px-2 py-0.5 text-[10px] text-ink-300/60">
                仅 SFX · 无背景音乐
              </span>
            </div>

            <div class="space-y-3.5">
              <div class="flex items-center justify-between gap-3">
                <div class="leading-tight">
                  <p class="text-cream-100">全部音效</p>
                  <p class="mt-0.5 text-[10px] text-ink-300/60">{{ soundPrefs.enabled ? '开' : '关' }} · 只影响自己这台设备</p>
                </div>
                <button
                  type="button"
                  role="switch"
                  :aria-checked="soundPrefs.enabled"
                  aria-label="全部音效开关"
                  class="relative h-6 w-11 shrink-0 rounded-full transition"
                  :class="soundPrefs.enabled ? 'bg-gold-400' : 'bg-cream-100/15'"
                  @click="toggleSoundEnabled"
                >
                  <span
                    class="absolute top-0.5 h-5 w-5 rounded-full bg-felt-950 shadow transition-all"
                    :class="soundPrefs.enabled ? 'left-[22px]' : 'left-0.5'"
                  />
                </button>
              </div>

              <div>
                <div class="mb-1 flex items-center justify-between">
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
                <div class="mt-1 flex justify-between text-[10px] text-ink-300/50">
                  <span>静音</span>
                  <span>最大</span>
                </div>
              </div>

              <button
                type="button"
                class="btn-ghost flex w-full items-center justify-center gap-1.5 rounded-lg py-1.5"
                :disabled="!soundPrefs.enabled"
                @click="previewDiscard"
              >
                <Play class="h-3.5 w-3.5" />
                试听（出牌声）
              </button>

              <div class="flex items-center justify-between gap-3 border-t border-cream-100/10 pt-3">
                <div class="leading-tight">
                  <p class="text-cream-100">聊天提示</p>
                  <p class="mt-0.5 text-[10px] text-ink-300/60">家人发言时轻响一声</p>
                </div>
                <button
                  type="button"
                  role="switch"
                  :aria-checked="soundPrefs.chat"
                  aria-label="聊天提示音开关"
                  class="relative h-6 w-11 shrink-0 rounded-full transition"
                  :class="soundPrefs.chat ? 'bg-gold-400' : 'bg-cream-100/15'"
                  @click="toggleChatSound"
                >
                  <span
                    class="absolute top-0.5 h-5 w-5 rounded-full bg-felt-950 shadow transition-all"
                    :class="soundPrefs.chat ? 'left-[22px]' : 'left-0.5'"
                  />
                </button>
              </div>
            </div>

            <p class="mt-3 border-t border-cream-100/10 pt-2 text-[10px] leading-relaxed text-ink-300/60">
              {{
                audioState.unlocked
                  ? '音频已解锁，进桌时预加载全部音效'
                  : '浏览器要求先点一下页面才允许出声，点任意位置即可解锁'
              }}
            </p>
          </div>
        </transition>
      </div>

      <!-- 开桌的人：不必等打满局数，随时可以结束本场（打满后文案变「关闭牌桌」） -->
      <button
        v-if="canEndGame"
        type="button"
        class="flex items-center gap-1 rounded-lg border border-vermilion-500/35 bg-vermilion-500/10 px-2.5 py-1 text-vermilion-400 transition hover:border-vermilion-500/60 hover:bg-vermilion-500/20"
        :aria-label="endText"
        @click="emit('endGame')"
      >
        <Flag class="h-3.5 w-3.5" />
        <span class="hidden sm:inline">{{ endText }}</span>
      </button>

      <button type="button" class="btn-ghost flex items-center gap-1 rounded-lg px-2.5 py-1" @click="emit('exit')">
        <DoorOpen class="h-3.5 w-3.5" />
        离桌
      </button>
    </div>

    <transition name="drop">
      <div
        v-if="open"
        class="absolute left-0 top-full z-30 mt-2 w-[330px] rounded-xl border border-gold-400/25 bg-felt-950/95 p-4 text-xs shadow-table backdrop-blur"
      >
        <p class="mb-2 text-sm font-medium text-gold-300">本局规则</p>
        <dl class="space-y-1.5 text-ink-300/90">
          <div class="flex justify-between"><dt>底分</dt><dd class="text-cream-100">{{ ruleBrief?.base_score }}</dd></div>
          <div class="flex justify-between"><dt>番数算法</dt><dd class="text-cream-100">{{ modeText }}</dd></div>
          <div class="flex justify-between">
            <dt>封顶</dt>
            <dd class="text-cream-100">{{ ruleBrief?.fan_cap === null ? '不封顶' : `${ruleBrief?.fan_cap} 番` }}</dd>
          </div>
          <div class="flex justify-between"><dt>吃牌</dt><dd class="text-cream-100">{{ ruleBrief?.allow_chow ? '允许' : '不允许' }}</dd></div>
          <div class="flex justify-between"><dt>出牌限时</dt><dd class="text-cream-100">{{ timeoutText }}</dd></div>
          <div class="flex justify-between"><dt>杠分</dt><dd class="text-cream-100">{{ kongText }}</dd></div>
          <div class="flex justify-between">
            <dt>圈数</dt>
            <dd class="text-cream-100">
              {{ totalCircles ?? ruleBrief?.circles_per_game ?? 4 }} 圈 × {{ totalRounds }} 局
            </dd>
          </div>
          <div class="flex justify-between"><dt>听牌提示</dt><dd class="text-cream-100">{{ ruleBrief?.ting_hint ? '开启' : '关闭' }}</dd></div>
        </dl>
        <div class="mt-2.5 border-t border-cream-100/10 pt-2 text-[11px] text-ink-300/70">
          牌型：{{ (ruleBrief?.patterns || []).join('、') || '—' }}
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.drop-enter-active,
.drop-leave-active {
  transition: all 0.18s ease;
}
.drop-enter-from,
.drop-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>

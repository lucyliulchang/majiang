<script setup lang="ts">
/**
 * 规则表单：**只按 `capability` 渲染**（05 §4.4、03 §2.2）。
 *
 * - 族不支持的开关/字段一律不显示（不是灰掉），避免用户改完才被服务端拒绝；
 * - 同一套字段名跨族复用（`turn_timeout` / `kong_score` / `ting_hint` / `draw_penalty` / `pause`）；
 * - 族扩展字段（柏氏 min_fan_to_win / 倍数 / 包牌，四川 lack_suit_required）只在配置里真有该键时出现。
 */
import { computed } from 'vue'
import { Clock, Coins, Layers, Lightbulb, PauseCircle, Sparkles, Scale } from 'lucide-vue-next'

import SwitchField from './SwitchField.vue'
import type { RuleConfig } from '../types'

const props = defineProps<{ config: RuleConfig; capability?: Record<string, any> }>()

const cfg = computed(() => props.config as unknown as Record<string, any>)
const cap = computed<Record<string, any>>(() => props.capability || {})

const PATTERN_META: Record<string, { title: string; desc: string }> = {
  standard: { title: '标准胡', desc: '4 面子 + 1 将，最通用的胡法' },
  seven_pairs: { title: '七对', desc: '门前清 14 张全部成对' },
  long_seven_pairs: { title: '龙七对', desc: '七对里含四张相同，番数更高' },
  thirteen_orphans: { title: '十三幺', desc: '13 种幺九字牌齐 + 一对' },
  thirteen_unrelated: { title: '十三不靠', desc: '不构成面子的特殊牌型，各地规矩不同' }
}

function hasKey(key: string): boolean {
  return cfg.value[key] !== undefined && cfg.value[key] !== null
}

/** 开关可用 = 族声明支持 + 本模板配置里真有这个字段 */
function switchOn(name: string): boolean {
  const switches: string[] = cap.value.switches || []
  return switches.includes(name) && hasKey(name)
}

function patternEnabled(id: string): boolean {
  const patterns = cap.value.patterns as string[] | undefined
  const value = cfg.value.patterns?.[id]
  if (value === undefined) return false
  if (patterns && patterns.length) return patterns.includes(id)
  return true
}

/** capability.patterns 里声明的牌型（顺序按声明），过滤掉配置里没有的 */
const patternCards = computed(() =>
  ((cap.value.patterns as string[] | undefined) || [])
    .filter((id) => cfg.value.patterns?.[id] !== undefined)
    .map((id) => ({ id, ...(PATTERN_META[id] || { title: id, desc: '' }) }))
)

const thirteenUnrelated = computed(() => {
  const value = cfg.value.patterns?.thirteen_unrelated
  return value && typeof value === 'object' ? value : null
})

const fanModes = computed(() => {
  const modes: string[] = cap.value.fan_modes || ['linear', 'exponential']
  return modes.map((mode) => ({
    value: mode,
    label: mode === 'exponential' ? '2 的 N 次方（越大越刺激）' : '线性累加（稳一点）'
  }))
})

const fanCapAllowed = computed(() => cap.value.fan_cap_allowed !== false)
const allowChowVisible = computed(() => cap.value.allow_chow !== false)
const fanCapMax = computed(() => Number(cap.value.fan_cap_max || 30))

function toggleCap(): void {
  props.config.fan_cap = props.config.fan_cap === null ? 8 : null
}

function togglePattern(id: string): void {
  const value = cfg.value.patterns?.[id]
  if (typeof value === 'object' && value !== null) value.enabled = !value.enabled
  else cfg.value.patterns[id] = !value
}

function patternActive(id: string): boolean {
  const value = cfg.value.patterns?.[id]
  return typeof value === 'object' && value !== null ? Boolean(value.enabled) : Boolean(value)
}
</script>

<template>
  <div class="space-y-5">
    <!-- 基础 -->
    <section class="rounded-2xl border border-cream-100/12 bg-felt-950/35 p-4">
      <p class="mb-3 flex items-center gap-1.5 text-sm font-medium text-gold-300">
        <Coins class="h-4 w-4" /> 基础设置
      </p>
      <div class="grid gap-3 sm:grid-cols-2">
        <label class="block">
          <span class="mb-1 block text-xs text-ink-300/80">底分（每个番值折算的基数）</span>
          <input v-model.number="config.base_score" class="field" type="number" min="1" max="100" />
        </label>

        <label v-if="fanModes.length > 1" class="block">
          <span class="mb-1 block text-xs text-ink-300/80">番数算法</span>
          <select v-model="config.fan_mode" class="field">
            <option v-for="mode in fanModes" :key="mode.value" :value="mode.value">{{ mode.label }}</option>
          </select>
        </label>

        <div v-else class="block">
          <span class="mb-1 block text-xs text-ink-300/80">番数算法</span>
          <p class="field flex items-center opacity-70">
            {{ cap.fan_combine?.includes('sum_all') ? '番值累加（该族固定）' : '2 的 N 次方（该族固定）' }}
          </p>
        </div>

        <label v-if="fanCapAllowed" class="block">
          <span class="mb-1 block text-xs text-ink-300/80">封顶番数</span>
          <div class="flex gap-2">
            <input
              v-model.number="config.fan_cap"
              class="field"
              type="number"
              min="0"
              :max="fanCapMax"
              :disabled="config.fan_cap === null"
              :placeholder="config.fan_cap === null ? '不封顶' : ''"
            />
            <button type="button" class="btn-ghost shrink-0 rounded-lg px-3 text-xs" @click="toggleCap">
              {{ config.fan_cap === null ? '改回封顶' : '不封顶' }}
            </button>
          </div>
        </label>

        <label v-if="hasKey('claim_window_seconds')" class="block">
          <span class="mb-1 block text-xs text-ink-300/80">碰杠胡询问窗口（秒）</span>
          <input v-model.number="config.claim_window_seconds" class="field" type="number" min="3" max="30" />
        </label>

        <div class="block">
          <span class="mb-1 block text-xs text-ink-300/80">一场打几局</span>
          <p class="field flex items-center opacity-70">
            {{ config.rounds_per_game }} 局（一圈 4 个庄次，固定）
          </p>
        </div>

        <label v-if="hasKey('discard_pay_mode')" class="block">
          <span class="mb-1 block text-xs text-ink-300/80">点炮怎么付</span>
          <select v-model="config.discard_pay_mode" class="field">
            <option value="single">放炮的一家独付</option>
            <option value="all">三家各付一份</option>
          </select>
        </label>

        <label v-if="hasKey('min_fan_to_win')" class="block">
          <span class="mb-1 block text-xs text-ink-300/80">起胡番数</span>
          <input v-model.number="cfg.min_fan_to_win" class="field" type="number" min="0" max="100" />
        </label>

        <label v-if="hasKey('self_draw_multiplier')" class="block">
          <span class="mb-1 block text-xs text-ink-300/80">自摸倍数</span>
          <input v-model.number="cfg.self_draw_multiplier" class="field" type="number" min="1" max="10" />
        </label>
      </div>

      <div class="mt-3 flex flex-wrap gap-4">
        <label v-if="allowChowVisible" class="flex cursor-pointer items-center gap-2 text-xs text-ink-300/85">
          <input v-model="config.allow_chow" type="checkbox" class="h-3.5 w-3.5 accent-[#C9A063]" />
          允许吃牌
        </label>
        <label v-if="hasKey('dealer_continue_on_win')" class="flex cursor-pointer items-center gap-2 text-xs text-ink-300/85">
          <input v-model="config.dealer_continue_on_win" type="checkbox" class="h-3.5 w-3.5 accent-[#C9A063]" />
          庄家胡牌连庄
        </label>
        <label v-if="hasKey('dealer_continue_on_draw')" class="flex cursor-pointer items-center gap-2 text-xs text-ink-300/85">
          <input v-model="config.dealer_continue_on_draw" type="checkbox" class="h-3.5 w-3.5 accent-[#C9A063]" />
          荒庄连庄
        </label>
        <span v-if="cap.lack_suit" class="badge-rule">缺一门（该族固定）</span>
        <span v-if="cap.multi_winner" class="badge-rule">一炮多响 / 血战到底</span>
      </div>
    </section>

    <!-- 族扩展：庄家倍数与包牌（柏氏） -->
    <section v-if="hasKey('dealer_rule') || hasKey('bao_pai')" class="rounded-2xl border border-cream-100/12 bg-felt-950/35 p-4">
      <p class="mb-3 flex items-center gap-1.5 text-sm font-medium text-gold-300">
        <Scale class="h-4 w-4" /> 倍数与包牌
      </p>
      <div class="grid gap-3 sm:grid-cols-2">
        <template v-if="hasKey('dealer_rule')">
          <label class="block">
            <span class="mb-1 block text-xs text-ink-300/80">庄家胡牌倍数</span>
            <input v-model.number="cfg.dealer_rule.win_multiplier" class="field" type="number" min="1" max="10" />
          </label>
          <label class="block">
            <span class="mb-1 block text-xs text-ink-300/80">庄家付分倍数</span>
            <input v-model.number="cfg.dealer_rule.pay_multiplier" class="field" type="number" min="1" max="10" />
          </label>
        </template>

        <template v-if="hasKey('bao_pai')">
          <label class="flex items-center gap-2 text-xs text-ink-300/85 sm:col-span-2">
            <input v-model="cfg.bao_pai.enabled" type="checkbox" class="h-3.5 w-3.5 accent-[#C9A063]" />
            开启包牌（点炮者独付三家之和）
          </label>
          <label class="block">
            <span class="mb-1 block text-xs text-ink-300/80">至少明牌组数</span>
            <input
              v-model.number="cfg.bao_pai.min_exposed_melds"
              class="field"
              type="number"
              min="2"
              max="4"
              :disabled="!cfg.bao_pai.enabled"
            />
          </label>
        </template>
      </div>
    </section>

    <!-- 三组联动开关：只渲染族能力声明里有的 -->
    <section v-if="switchOn('turn_timeout') || switchOn('kong_score') || switchOn('ting_hint') || switchOn('draw_penalty') || switchOn('pause')" class="space-y-2.5">
      <p class="flex items-center gap-1.5 text-sm font-medium text-gold-300">
        <Sparkles class="h-4 w-4" /> 可选功能（关闭后从属设置不生效）
      </p>

      <SwitchField
        v-if="switchOn('turn_timeout')"
        v-model:enabled="config.turn_timeout.enabled"
        label="出牌限时"
        description="打开后轮到谁都有倒计时，超时系统自动出牌；关闭就无限等"
        :icon="Clock"
      >
        <template #default="{ disabled }">
          <label class="block">
            <span class="mb-1 block text-xs text-ink-300/80">每步限时 {{ config.turn_timeout.seconds }} 秒</span>
            <input
              v-model.number="config.turn_timeout.seconds"
              class="field"
              type="number"
              min="10"
              max="120"
              :disabled="disabled"
            />
            <span v-if="!disabled" class="mt-1 block text-[11px] text-ink-300/55">可填 10-120 秒</span>
            <span v-else class="mt-1 block text-[11px] text-ink-300/55">当前不限时</span>
          </label>
        </template>
      </SwitchField>

      <SwitchField
        v-if="switchOn('kong_score')"
        v-model:enabled="config.kong_score.enabled"
        label="杠分"
        description="关闭后杠牌照常能杠，只是不产生任何分数"
        :icon="Coins"
      >
        <template #default="{ disabled }">
          <div class="grid grid-cols-3 gap-2">
            <label class="block">
              <span class="mb-1 block text-xs text-ink-300/80">明杠</span>
              <input v-model.number="config.kong_score.exposed" class="field" type="number" min="0" max="20" :disabled="disabled" />
            </label>
            <label class="block">
              <span class="mb-1 block text-xs text-ink-300/80">暗杠</span>
              <input v-model.number="config.kong_score.hidden" class="field" type="number" min="0" max="20" :disabled="disabled" />
            </label>
            <label class="block">
              <span class="mb-1 block text-xs text-ink-300/80">补杠</span>
              <input v-model.number="config.kong_score.added" class="field" type="number" min="0" max="20" :disabled="disabled" />
            </label>
          </div>
        </template>
      </SwitchField>

      <SwitchField
        v-if="switchOn('ting_hint')"
        v-model:enabled="config.ting_hint.enabled"
        label="听牌提示"
        description="关闭后轮到你时不再提示“打这张能听什么牌”"
        :icon="Lightbulb"
      >
        <template #default>
          <p class="text-[11px] text-ink-300/60">
            开启时，牌桌会标出打掉哪张之后能听牌，并列出听的口子；关闭后既不算也不提示。
          </p>
        </template>
      </SwitchField>

      <SwitchField
        v-if="switchOn('draw_penalty')"
        v-model:enabled="config.draw_penalty.enabled"
        label="荒庄罚分"
        description="牌摸完了还没人胡时，其余三家要不要给庄家罚分"
      >
        <template #default="{ disabled }">
          <label class="block">
            <span class="mb-1 block text-xs text-ink-300/80">每家罚 {{ config.draw_penalty.value ?? 0 }} 分给庄家</span>
            <input
              v-model.number="config.draw_penalty.value"
              class="field"
              type="number"
              min="0"
              max="20"
              :disabled="disabled"
            />
          </label>
        </template>
      </SwitchField>

      <SwitchField
        v-if="switchOn('pause')"
        v-model:enabled="cfg.pause.enabled"
        label="允许暂停"
        description="牌桌上任一在座玩家可以暂停，暂停期间不接受出牌与响应"
        :icon="PauseCircle"
      >
        <template #default>
          <p class="text-[11px] text-ink-300/60">暂停为纯牌桌态：不改变分数、不掉线，恢复后按剩余时间继续。</p>
        </template>
      </SwitchField>
    </section>

    <!-- 牌型开关：按 capability.patterns 渲染 -->
    <section v-if="patternCards.length" class="rounded-2xl border border-cream-100/12 bg-felt-950/35 p-4">
      <p class="mb-3 flex items-center gap-1.5 text-sm font-medium text-gold-300">
        <Layers class="h-4 w-4" /> 胡牌牌型
      </p>
      <div class="grid gap-2 sm:grid-cols-3">
        <button
          v-for="card in patternCards"
          :key="card.id"
          type="button"
          class="rounded-xl border px-3 py-2.5 text-left transition"
          :class="
            patternActive(card.id)
              ? 'border-gold-400/55 bg-gold-400/10'
              : 'border-cream-100/12 bg-cream-100/[0.02] opacity-70'
          "
          @click="togglePattern(card.id)"
        >
          <p class="text-xs font-medium text-cream-100">{{ card.title }}</p>
          <p class="mt-0.5 text-[10px] leading-relaxed text-ink-300/65">{{ card.desc }}</p>
        </button>
      </div>

      <!-- 13 不靠的族内子参数：只有配置里真有这些键时才出现 -->
      <div v-if="thirteenUnrelated && (thirteenUnrelated.min_gap !== undefined || thirteenUnrelated.require_all_honors !== undefined)" class="mt-3">
        <div class="grid gap-2 sm:grid-cols-3">
          <label v-if="thirteenUnrelated.require_all_honors !== undefined" class="flex items-center gap-2 text-xs text-ink-300/85">
            <input
              v-model="thirteenUnrelated.require_all_honors"
              type="checkbox"
              class="h-3.5 w-3.5 accent-[#C9A063]"
              :disabled="!thirteenUnrelated.enabled"
            />
            必须七星齐全
          </label>
          <label v-if="thirteenUnrelated.allow_pair !== undefined" class="flex items-center gap-2 text-xs text-ink-300/85">
            <input
              v-model="thirteenUnrelated.allow_pair"
              type="checkbox"
              class="h-3.5 w-3.5 accent-[#C9A063]"
              :disabled="!thirteenUnrelated.enabled"
            />
            允许一对将
          </label>
          <label v-if="thirteenUnrelated.min_gap !== undefined" class="block">
            <span class="mb-1 block text-xs text-ink-300/80">同花色最小间隔</span>
            <input
              v-model.number="thirteenUnrelated.min_gap"
              class="field"
              type="number"
              min="2"
              max="9"
              :disabled="!thirteenUnrelated.enabled"
            />
          </label>
        </div>
      </div>
    </section>
  </div>
</template>

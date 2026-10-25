<script setup lang="ts">
import { computed } from 'vue'
import { Clock, Coins, Lightbulb, Layers, Sparkles } from 'lucide-vue-next'

import SwitchField from './SwitchField.vue'
import type { RuleConfig } from '../types'

const props = defineProps<{ config: RuleConfig }>()

const patternCards = computed(() => [
  {
    key: 'standard' as const,
    title: '标准胡',
    desc: '4 面子 + 1 将，最通用的胡法'
  },
  {
    key: 'seven_pairs' as const,
    title: '七对',
    desc: '门前清 14 张全部成对，含龙七对'
  },
  {
    key: 'thirteen_orphans' as const,
    title: '十三幺',
    desc: '13 种幺九字牌齐 + 一对'
  }
])

function toggleCap(): void {
  props.config.fan_cap = props.config.fan_cap === null ? 8 : null
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

        <label class="block">
          <span class="mb-1 block text-xs text-ink-300/80">番数算法</span>
          <select v-model="config.fan_mode" class="field">
            <option value="exponential">2 的 N 次方（越大越刺激）</option>
            <option value="linear">线性累加（稳一点）</option>
          </select>
        </label>

        <label class="block">
          <span class="mb-1 block text-xs text-ink-300/80">封顶番数</span>
          <div class="flex gap-2">
            <input
              v-model.number="config.fan_cap"
              class="field"
              type="number"
              min="0"
              max="30"
              :disabled="config.fan_cap === null"
              :placeholder="config.fan_cap === null ? '不封顶' : ''"
            />
            <button type="button" class="btn-ghost shrink-0 rounded-lg px-3 text-xs" @click="toggleCap">
              {{ config.fan_cap === null ? '改回封顶' : '不封顶' }}
            </button>
          </div>
        </label>

        <label class="block">
          <span class="mb-1 block text-xs text-ink-300/80">一场打几局</span>
          <input v-model.number="config.rounds_per_game" class="field" type="number" min="1" max="32" />
        </label>

        <label class="block">
          <span class="mb-1 block text-xs text-ink-300/80">点炮怎么付</span>
          <select v-model="config.discard_pay_mode" class="field">
            <option value="single">放炮的一家独付</option>
            <option value="all">三家各付一份</option>
          </select>
        </label>

        <label class="block">
          <span class="mb-1 block text-xs text-ink-300/80">碰杠胡询问窗口（秒）</span>
          <input v-model.number="config.claim_window_seconds" class="field" type="number" min="3" max="30" />
        </label>
      </div>

      <div class="mt-3 flex flex-wrap gap-4">
        <label class="flex cursor-pointer items-center gap-2 text-xs text-ink-300/85">
          <input v-model="config.allow_chow" type="checkbox" class="h-3.5 w-3.5 accent-[#C9A063]" />
          允许吃牌
        </label>
        <label class="flex cursor-pointer items-center gap-2 text-xs text-ink-300/85">
          <input v-model="config.dealer_continue_on_win" type="checkbox" class="h-3.5 w-3.5 accent-[#C9A063]" />
          庄家胡牌连庄
        </label>
        <label class="flex cursor-pointer items-center gap-2 text-xs text-ink-300/85">
          <input v-model="config.dealer_continue_on_draw" type="checkbox" class="h-3.5 w-3.5 accent-[#C9A063]" />
          荒庄连庄
        </label>
      </div>
    </section>

    <!-- 三组联动开关 -->
    <section class="space-y-2.5">
      <p class="flex items-center gap-1.5 text-sm font-medium text-gold-300">
        <Sparkles class="h-4 w-4" /> 可选功能（关闭后从属设置不生效）
      </p>

      <SwitchField
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
        v-model:enabled="config.ting_hint.enabled"
        label="听牌提示"
        description="关闭后轮到你时不再提示“打这张能听什么牌”"
        :icon="Lightbulb"
      >
        <template #default>
          <p class="text-[11px] text-ink-300/60">
            开启时，牌桌会标出打掉哪张之后能听牌，并列出听的口子；关闭后既不算也不算力。
          </p>
        </template>
      </SwitchField>

      <SwitchField
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
    </section>

    <!-- 牌型开关 -->
    <section class="rounded-2xl border border-cream-100/12 bg-felt-950/35 p-4">
      <p class="mb-3 flex items-center gap-1.5 text-sm font-medium text-gold-300">
        <Layers class="h-4 w-4" /> 胡牌牌型
      </p>
      <div class="grid gap-2 sm:grid-cols-3">
        <button
          v-for="card in patternCards"
          :key="card.key"
          type="button"
          class="rounded-xl border px-3 py-2.5 text-left transition"
          :class="
            config.patterns[card.key]
              ? 'border-gold-400/55 bg-gold-400/10'
              : 'border-cream-100/12 bg-cream-100/[0.02] opacity-70'
          "
          @click="config.patterns[card.key] = !config.patterns[card.key]"
        >
          <p class="text-xs font-medium text-cream-100">{{ card.title }}</p>
          <p class="mt-0.5 text-[10px] leading-relaxed text-ink-300/65">{{ card.desc }}</p>
        </button>
      </div>

      <div class="mt-3">
        <SwitchField
          v-model:enabled="config.patterns.thirteen_unrelated.enabled"
          label="十三不靠"
          description="不构成面子的特殊牌型，各地规矩不同，下面三个参数说了算"
        >
          <template #default="{ disabled }">
            <div class="grid gap-2 sm:grid-cols-3">
              <label class="flex items-center gap-2 text-xs text-ink-300/85">
                <input
                  v-model="config.patterns.thirteen_unrelated.require_all_honors"
                  type="checkbox"
                  class="h-3.5 w-3.5 accent-[#C9A063]"
                  :disabled="disabled"
                />
                必须七星齐全
              </label>
              <label class="flex items-center gap-2 text-xs text-ink-300/85">
                <input
                  v-model="config.patterns.thirteen_unrelated.allow_pair"
                  type="checkbox"
                  class="h-3.5 w-3.5 accent-[#C9A063]"
                  :disabled="disabled"
                />
                允许一对将
              </label>
              <label class="block">
                <span class="mb-1 block text-xs text-ink-300/80">同花色最小间隔</span>
                <input
                  v-model.number="config.patterns.thirteen_unrelated.min_gap"
                  class="field"
                  type="number"
                  min="2"
                  max="9"
                  :disabled="disabled"
                />
              </label>
            </div>
          </template>
        </SwitchField>
      </div>
    </section>
  </div>
</template>

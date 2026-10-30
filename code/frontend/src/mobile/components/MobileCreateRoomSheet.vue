<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Check, Loader2 } from 'lucide-vue-next'

import MobileSheet from './MobileSheet.vue'
import { api } from '../../api/http'
import { useToast } from '../../composables/useToast'
import { useAuthStore } from '../../stores/auth'
import type { RoomInfo, RuleFamily, RuleTemplate } from '../../types'

/**
 * 手机端建桌：规则族横滑选择 + 模板竖排单选 + 桌名。
 * 与 PC 的 CreateRoomDialog 同一套接口（GET /rules、GET /rule-families、POST /rooms），
 * 只是把「两列网格」压成「一列单选项」，避免小屏上误点。
 */
const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: []; created: [room: RoomInfo] }>()

const toast = useToast()
const auth = useAuthStore()

const rules = ref<RuleTemplate[]>([])
const ruleFamilies = ref<RuleFamily[]>([])
const activeFamily = ref('')
const selectedId = ref<number | null>(null)
const name = ref('')
const loading = ref(true)
const saving = ref(false)
/** 一场几圈（v1.1.0）：每圈固定 4 个庄次，默认 4 圈，开桌时可按桌覆盖 */
const CIRCLE_OPTIONS = [1, 2, 4, 8]
const circles = ref(4)
const circlesTouched = ref(false)

const familyQuery = computed(() =>
  auth.currentFamilyCode ? `?family_code=${encodeURIComponent(auth.currentFamilyCode)}` : ''
)

const tabs = computed(() =>
  ruleFamilies.value
    .map((family) => ({
      ...family,
      templates: rules.value.filter((item) => item.rule_family_code === family.rule_family_code)
    }))
    .filter((family) => family.templates.length > 0 || family.ready)
    .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))
)

const currentTab = computed(() => tabs.value.find((item) => item.rule_family_code === activeFamily.value) || null)
const visibleTemplates = computed(() => currentTab.value?.templates ?? [])
const familyReady = computed(() => currentTab.value?.ready !== false)

const selectedRule = computed(() => rules.value.find((item) => item.id === selectedId.value) || null)

/** 规则摘要：各族配置形状不统一，缺字段就退化，不能直接点属性（否则弹窗整块渲染不出来） */
const ruleDetail = computed(() => {
  const config = selectedRule.value?.config as unknown as {
    fan_mode?: string
    fan_table?: unknown
    ting_hint?: { enabled?: boolean }
    rounds_per_game?: number
  }
  if (!config) return null
  return {
    fanMode: config.fan_mode === 'exponential' ? '总番数按 2 的幂放大' : '总番数线性累加',
    fanCount: Array.isArray(config.fan_table) ? config.fan_table.length : 0,
    tingHint: config.ting_hint?.enabled ? '轮到你时能看到听牌提示' : '不给听牌提示',
    rounds: config.rounds_per_game ?? '—'
  }
})

/** 模板里配置的默认圈数（老模板没有该字段时按 4 圈） */
function templateCircles(template: RuleTemplate | null): number {
  const value = Number((template?.config as { circles_per_game?: number } | undefined)?.circles_per_game)
  return CIRCLE_OPTIONS.includes(value) ? value : 4
}

watch(selectedId, (id) => {
  if (circlesTouched.value) return
  circles.value = templateCircles(rules.value.find((item) => item.id === id) || null)
})

function pickCircles(value: number): void {
  circlesTouched.value = true
  circles.value = value
}

function describe(template: RuleTemplate): string {
  const config = template.config as unknown as {
    base_score?: number
    fan_mode?: string
    fan_cap?: number | null
    allow_chow?: boolean
    turn_timeout?: { enabled: boolean; seconds: number }
    kong_score?: { enabled: boolean }
  }
  return [
    `底分 ${config.base_score ?? '—'}`,
    config.fan_mode === 'exponential' ? '2^N 番' : '线性番',
    config.fan_cap === null || config.fan_cap === undefined ? '不封顶' : `封顶 ${config.fan_cap}`,
    config.allow_chow ? '可吃' : '不可吃',
    config.turn_timeout?.enabled ? `限时 ${config.turn_timeout.seconds}s` : '不限时',
    config.kong_score?.enabled ? '杠计分' : '杠不计分'
  ].join(' · ')
}

onMounted(async () => {
  try {
    const [templateList, familyList] = await Promise.all([
      api.get<RuleTemplate[]>(`/rules${familyQuery.value}`),
      api.get<RuleFamily[]>('/rule-families').catch(() => [] as RuleFamily[])
    ])
    rules.value = templateList
    ruleFamilies.value = familyList

    const preferred =
      familyList.find((item) => item.rule_family_code === auth.currentFamily?.default_rule_family_code)?.rule_family_code ||
      familyList.find((item) => item.ready)?.rule_family_code ||
      templateList[0]?.rule_family_code ||
      ''
    activeFamily.value = preferred
    const first = templateList.find((item) => item.rule_family_code === preferred) || templateList[0]
    if (first) selectedId.value = first.id
    name.value = `周末家庭局 · ${new Date().toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })}`
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    loading.value = false
  }
})

function pickFamily(code: string): void {
  activeFamily.value = code
  const first = rules.value.find((item) => item.rule_family_code === code)
  selectedId.value = first?.id ?? null
}

async function submit(): Promise<void> {
  if (!props.open) return
  if (!familyReady.value) {
    toast.warn('该规则族引擎未就绪，暂时不能开桌')
    return
  }
  if (!selectedId.value) {
    toast.warn('先挑一套规则')
    return
  }
  if (!name.value.trim()) {
    toast.warn('给牌桌起个名字')
    return
  }
  saving.value = true
  try {
    const room = await api.post<RoomInfo>('/rooms', {
      family_code: auth.currentFamilyCode || '',
      room_name: name.value.trim(),
      template_id: selectedId.value,
      circles: circles.value
    })
    emit('created', room)
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <MobileSheet
    :open="open"
    title="开一桌"
    :subtitle="`${auth.currentFamilyName} · 选好规则，开局后本局不再变动`"
    max-height="88vh"
    @close="emit('close')"
  >
    <div class="space-y-4 pt-1">
      <label class="block">
        <span class="mb-1.5 block text-[12px] text-ink-300/85">牌桌名字</span>
        <input v-model="name" class="field" placeholder="比如 周末家庭局" maxlength="64" />
      </label>

      <div>
        <span class="mb-2 block text-[12px] text-ink-300/85">规则族</span>
        <p v-if="loading" class="text-sm text-ink-300/70">加载规则…</p>
        <div v-else class="mj-hscroll -mx-1 flex gap-1.5 px-1 pb-1">
          <button
            v-for="tab in tabs"
            :key="tab.rule_family_code"
            type="button"
            class="mj-press flex shrink-0 items-center gap-1.5 rounded-lg border px-3 py-2 text-[12px]"
            :class="
              activeFamily === tab.rule_family_code
                ? 'border-gold-400/60 bg-gold-400/10 text-cream-100'
                : 'border-cream-100/10 bg-cream-100/[0.03] text-ink-300/80'
            "
            @click="pickFamily(tab.rule_family_code)"
          >
            {{ tab.rule_family_name }}
            <span v-if="!tab.ready" class="rounded bg-vermilion-500/20 px-1 text-[10px] text-vermilion-400">未就绪</span>
          </button>
          <span v-if="!tabs.length" class="py-1 text-xs text-ink-300/70">还没有可用的规则族</span>
        </div>
      </div>

      <div v-if="!loading">
        <span class="mb-2 block text-[12px] text-ink-300/85">选择规则模板</span>
        <p
          v-if="!familyReady"
          class="mb-2 rounded-lg border border-vermilion-500/35 bg-vermilion-500/10 px-3 py-2 text-[11px] text-vermilion-400"
        >
          引擎未就绪：该规则族细则尚未配置完成，暂时不能开桌。
        </p>

        <div class="space-y-2">
          <button
            v-for="template in visibleTemplates"
            :key="template.id"
            type="button"
            class="mj-press flex w-full items-start gap-2 rounded-xl border px-3 py-2.5 text-left disabled:opacity-50"
            :class="
              selectedId === template.id
                ? 'border-gold-400/60 bg-gold-400/10'
                : 'border-cream-100/10 bg-cream-100/[0.03]'
            "
            :disabled="!familyReady"
            @click="selectedId = template.id"
          >
            <div class="min-w-0 flex-1">
              <p class="flex items-center gap-1.5">
                <span class="truncate text-[13px] font-medium text-cream-100">{{ template.template_name }}</span>
                <span v-if="template.is_preset" class="shrink-0 rounded bg-jade-500/20 px-1.5 py-0.5 text-[10px] text-jade-400">
                  预置
                </span>
              </p>
              <p class="mt-1 line-clamp-2 text-[11px] leading-relaxed text-ink-300/70">
                {{ template.description || describe(template) }}
              </p>
              <p class="mt-1 text-[10px] text-gold-400/70">{{ describe(template) }}</p>
            </div>
            <Check v-if="selectedId === template.id" class="mt-0.5 h-4 w-4 shrink-0 text-gold-300" />
          </button>
        </div>

        <p v-if="!visibleTemplates.length" class="rounded-xl border border-cream-100/10 bg-cream-100/[0.03] px-3 py-4 text-center text-[12px] text-ink-300/75">
          这个规则族还没有模板，去电脑版的「规则模板」新建一套
        </p>
      </div>

      <div v-if="!loading">
        <div class="mb-2 flex items-center justify-between gap-2">
          <span class="text-[12px] text-ink-300/85">打几圈</span>
          <span class="text-[10px] text-ink-300/60">每圈 4 个庄次，连庄会多打</span>
        </div>
        <div class="mj-hscroll -mx-1 flex gap-1.5 px-1 pb-1">
          <button
            v-for="option in CIRCLE_OPTIONS"
            :key="option"
            type="button"
            class="mj-press flex shrink-0 flex-col items-center rounded-lg border px-3 py-2 text-[12px]"
            :class="
              circles === option
                ? 'border-gold-400/60 bg-gold-400/10 text-cream-100'
                : 'border-cream-100/10 bg-cream-100/[0.03] text-ink-300/80'
            "
            @click="pickCircles(option)"
          >
            <span>{{ option }} 圈</span>
            <span class="text-[10px] text-ink-300/55">约 {{ option * 4 }} 局</span>
          </button>
        </div>
      </div>

      <div v-if="ruleDetail && familyReady" class="mj-card-flat p-3 text-[11px] text-ink-300/80">
        <p class="mb-1 text-[12px] text-gold-300">这套规则会怎么算</p>
        <p class="leading-relaxed">
          {{ ruleDetail.fanMode }}，命中 {{ ruleDetail.fanCount }} 个可选番种；{{ ruleDetail.tingHint }}；每圈
          {{ ruleDetail.rounds }} 个庄次，本桌 {{ circles }} 圈（计划
          {{ (Number(ruleDetail.rounds) || 4) * circles }} 局）。
        </p>
      </div>
    </div>

    <template #footer>
      <button
        type="button"
        class="mj-press btn-gold flex min-h-[48px] w-full items-center justify-center gap-2 rounded-xl text-[15px] font-semibold"
        :disabled="saving || !familyReady || !selectedId"
        @click="submit"
      >
        <Loader2 v-if="saving" class="h-4 w-4 animate-spin" />
        {{ saving ? '创建中…' : '开桌并进入' }}
      </button>
    </template>
  </MobileSheet>
</template>

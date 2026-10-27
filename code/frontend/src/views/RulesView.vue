<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Copy, Loader2, Plus, Save, Trash2 } from 'lucide-vue-next'

import AppHeader from '../components/AppHeader.vue'
import FanTableEditor from '../components/FanTableEditor.vue'
import RuleForm from '../components/RuleForm.vue'
import { api } from '../api/http'
import { useToast } from '../composables/useToast'
import type { RuleConfig, RuleTemplate } from '../types'

const toast = useToast()

const templates = ref<RuleTemplate[]>([])
const loading = ref(true)
const saving = ref(false)
const currentId = ref<number | null>(null)
const presetEditing = ref(false)
const draft = ref<{ name: string; description: string; config: RuleConfig } | null>(null)

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

async function load(selectFirst = false): Promise<void> {
  loading.value = true
  try {
    templates.value = await api.get<RuleTemplate[]>('/rules')
    if (selectFirst || currentId.value === null) {
      const target = templates.value[0]
      if (target) select(target)
    } else {
      const found = templates.value.find((item) => item.id === currentId.value)
      if (found) select(found)
    }
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    loading.value = false
  }
}

function select(template: RuleTemplate): void {
  currentId.value = template.id
  presetEditing.value = template.is_preset
  draft.value = {
    name: template.name,
    description: template.description,
    config: clone(template.config)
  }
}

function createNew(): void {
  const base = templates.value.find((item) => item.is_preset) || templates.value[0]
  currentId.value = null
  presetEditing.value = false
  draft.value = {
    name: '我的家庭规矩',
    description: '',
    config: base ? clone(base.config) : ({} as RuleConfig)
  }
}

const preview = computed(() => {
  const config = draft.value?.config
  if (!config) return ''
  const parts = [
    `底分 ${config.base_score}`,
    config.fan_mode === 'exponential' ? '2 的 N 次方' : '线性累加',
    config.fan_cap === null ? '不封顶' : `封顶 ${config.fan_cap} 番`,
    config.allow_chow ? '可以吃' : '不能吃',
    config.turn_timeout.enabled ? `限时 ${config.turn_timeout.seconds} 秒` : '不限时',
    config.kong_score.enabled
      ? `杠分 明${config.kong_score.exposed}/暗${config.kong_score.hidden}/补${config.kong_score.added}`
      : '杠不计分',
    config.ting_hint.enabled ? '听牌提示开' : '无听牌提示'
  ]
  return parts.join(' · ')
})

const example = computed(() => {
  const config = draft.value?.config
  if (!config) return ''
  const total = 6 + 1
  const capped = config.fan_cap === null ? total : Math.min(total, config.fan_cap)
  const score =
    config.fan_mode === 'exponential'
      ? config.base_score * 2 ** capped
      : config.base_score * Math.max(1, capped)
  return `举例：清一色 6 番 + 自摸 1 番 = ${capped} 番 → ${score} 分`
})

async function save(): Promise<void> {
  if (!draft.value) return
  if (!draft.value.name.trim()) {
    toast.warn('给规则起个名字')
    return
  }
  saving.value = true
  try {
    const payload = {
      name: draft.value.name.trim(),
      description: draft.value.description.trim(),
      config: draft.value.config
    }
    if (currentId.value === null) {
      const created = await api.post<RuleTemplate>('/rules', payload)
      await load()
      select(created)
      toast.success('规则已创建')
    } else {
      const updated = await api.put<RuleTemplate>(`/rules/${currentId.value}`, payload)
      await load()
      select(updated)
      toast.success('规则已保存')
    }
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    saving.value = false
  }
}

async function duplicate(): Promise<void> {
  if (currentId.value === null) {
    toast.warn('先保存再复制')
    return
  }
  try {
    const created = await api.post<RuleTemplate>(`/rules/${currentId.value}/duplicate`)
    await load()
    select(created)
    toast.success('已复制成你自己的模板，可以随便改了')
  } catch (error) {
    toast.error((error as Error).message)
  }
}

async function deactivate(): Promise<void> {
  if (currentId.value === null) return
  try {
    await api.del(`/rules/${currentId.value}`)
    toast.success('已停用这套规则')
    currentId.value = null
    await load(true)
  } catch (error) {
    toast.error((error as Error).message)
  }
}

onMounted(() => load(true))
</script>

<template>
  <div class="min-h-screen pb-16">
    <AppHeader />

    <main class="mx-auto max-w-[1400px] px-5 pt-24">
      <div class="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p class="text-[11px] tracking-[0.32em] text-gold-400/70">RULES</p>
          <h1 class="mt-1 text-2xl font-semibold text-cream-100">自定义积分规则</h1>
          <p class="mt-1 text-sm text-ink-300/80">
            底分、番种、杠分、限时、听牌提示都能单独调；开桌时挑一套，本局内不再变。
          </p>
        </div>
        <button type="button" class="btn-gold flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold" @click="createNew">
          <Plus class="h-4 w-4" />
          新建模板
        </button>
      </div>

      <div class="grid gap-5 lg:grid-cols-[280px_1fr]">
        <!-- 模板列表 -->
        <aside class="glass h-fit rounded-2xl p-3">
          <p v-if="loading" class="py-6 text-center text-xs text-ink-300/60">加载中…</p>
          <div class="space-y-1.5">
            <button
              v-for="template in templates"
              :key="template.id"
              type="button"
              class="w-full rounded-xl border px-3 py-2.5 text-left transition"
              :class="
                currentId === template.id
                  ? 'border-gold-400/55 bg-gold-400/10'
                  : 'border-transparent hover:border-cream-100/15 hover:bg-cream-100/[0.04]'
              "
              @click="select(template)"
            >
              <div class="flex items-center gap-1.5">
                <span class="truncate text-sm text-cream-100">{{ template.name }}</span>
                <span
                  v-if="template.is_preset"
                  class="ml-auto shrink-0 rounded bg-jade-500/20 px-1.5 py-0.5 text-[10px] text-jade-400"
                >
                  预置
                </span>
              </div>
              <p class="mt-0.5 line-clamp-1 text-[11px] text-ink-300/60">
                {{ template.description || '还没写说明' }}
              </p>
            </button>
          </div>
        </aside>

        <!-- 编辑器 -->
        <section v-if="draft" class="space-y-4">
          <div class="glass rounded-2xl p-4">
            <div class="grid gap-3 sm:grid-cols-[1.2fr_1.8fr]">
              <label class="block">
                <span class="mb-1 block text-xs text-ink-300/80">模板名称</span>
                <input v-model="draft.name" class="field" maxlength="64" :disabled="presetEditing" />
              </label>
              <label class="block">
                <span class="mb-1 block text-xs text-ink-300/80">一句话说明</span>
                <input
                  v-model="draft.description"
                  class="field"
                  maxlength="120"
                  placeholder="比如：周末长辈局，慢一点不催人"
                  :disabled="presetEditing"
                />
              </label>
            </div>

            <div class="mt-3 flex flex-wrap items-center gap-2 rounded-xl border border-gold-400/20 bg-gold-400/[0.06] px-3 py-2">
              <span class="text-[11px] text-gold-300">当前规则</span>
              <span class="text-[11px] text-ink-300/85">{{ preview }}</span>
            </div>
            <p class="mt-1.5 text-[11px] text-gold-400/70">{{ example }}</p>

            <p v-if="presetEditing" class="mt-3 rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-[11px] text-amber-400">
              预置模板不能直接改，点右下角「复制为新模板」就能自由调整。
            </p>
          </div>

          <fieldset :disabled="presetEditing" class="space-y-4">
            <RuleForm :config="draft.config" />
            <FanTableEditor :config="draft.config" />
          </fieldset>

          <div class="sticky bottom-4 flex flex-wrap items-center justify-end gap-2 rounded-xl border border-cream-100/10 bg-felt-950/85 px-4 py-3 backdrop-blur">
            <button
              v-if="currentId !== null && !presetEditing"
              type="button"
              class="btn-ghost flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm"
              @click="deactivate"
            >
              <Trash2 class="h-4 w-4" />
              停用
            </button>
            <button
              v-if="currentId !== null"
              type="button"
              class="btn-ghost flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm"
              @click="duplicate"
            >
              <Copy class="h-4 w-4" />
              复制为新模板
            </button>
            <button
              v-if="!presetEditing"
              type="button"
              class="btn-gold flex items-center gap-2 rounded-lg px-5 py-2 text-sm font-semibold"
              :disabled="saving"
              @click="save"
            >
              <Loader2 v-if="saving" class="h-4 w-4 animate-spin" />
              <Save v-else class="h-4 w-4" />
              {{ saving ? '保存中…' : '保存规则' }}
            </button>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>

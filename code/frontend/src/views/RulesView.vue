<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { CircleAlert, Copy, Loader2, Plus, Save, Trash2 } from 'lucide-vue-next'

import AppHeader from '../components/AppHeader.vue'
import FanTableEditor from '../components/FanTableEditor.vue'
import RuleForm from '../components/RuleForm.vue'
import { api } from '../api/http'
import { useToast } from '../composables/useToast'
import { useAuthStore } from '../stores/auth'
import type { RuleConfig, RuleFamily, RuleTemplate, RuleValidateResult } from '../types'

const toast = useToast()
const auth = useAuthStore()

const templates = ref<RuleTemplate[]>([])
const ruleFamilies = ref<RuleFamily[]>([])
const loading = ref(true)
const saving = ref(false)
const currentId = ref<number | null>(null)
const presetEditing = ref(false)
const activeFamily = ref('')
const draft = ref<{ name: string; description: string; config: RuleConfig } | null>(null)

const familyCode = computed(() => auth.currentFamilyCode || '')
const familyQuery = computed(() => (familyCode.value ? `?family_code=${encodeURIComponent(familyCode.value)}` : ''))

const selectedFamily = computed<RuleFamily | null>(
  () => ruleFamilies.value.find((item) => item.rule_family_code === activeFamily.value) || null
)
const capability = computed<Record<string, any>>(() => (selectedFamily.value?.capability || {}) as Record<string, any>)
/** 柏氏等「引擎未就绪」的族：可看模板，但保存/开桌都要拦住（04 §5） */
const notReady = computed(() => selectedFamily.value?.ready === false)

const currentTemplate = computed(() => templates.value.find((item) => item.id === currentId.value) || null)
const canEditCurrent = computed(() => {
  const template = currentTemplate.value
  if (!template) return true
  if (template.is_preset) return false
  // 创建者或家庭管理员；后端仍会再判一次，这里只用于禁用按钮
  return template.owner_login_id === auth.loginId || auth.isFamilyAdmin || auth.isAdmin
})

const visibleTemplates = computed(() =>
  activeFamily.value
    ? templates.value.filter((item) => item.rule_family_code === activeFamily.value)
    : templates.value
)

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

async function load(selectFirst = false): Promise<void> {
  if (!familyCode.value) return
  loading.value = true
  try {
    const [templateList, familyList] = await Promise.all([
      api.get<RuleTemplate[]>(`/rules${familyQuery.value}`),
      api.get<RuleFamily[]>('/rule-families').catch(() => [] as RuleFamily[])
    ])
    templates.value = templateList
    ruleFamilies.value = familyList
    if (!activeFamily.value) {
      activeFamily.value =
        templateList[0]?.rule_family_code || familyList.find((item) => item.ready)?.rule_family_code || ''
    }
    if (selectFirst || currentId.value === null) {
      const target = visibleTemplates.value[0] || templateList[0]
      if (target) select(target)
      else draft.value = null
    } else {
      const found = templateList.find((item) => item.id === currentId.value)
      if (found) select(found)
      else draft.value = null
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
  activeFamily.value = template.rule_family_code || activeFamily.value
  draft.value = {
    name: template.template_name,
    description: template.description,
    config: clone(template.config)
  }
}

function pickFamily(code: string): void {
  activeFamily.value = code
  const first = templates.value.find((item) => item.rule_family_code === code)
  if (first) select(first)
  else {
    currentId.value = null
    presetEditing.value = false
    draft.value = null
  }
}

function createNew(): void {
  const pool = visibleTemplates.value
  const base = pool.find((item) => item.is_preset) || pool[0]
  if (!base) {
    toast.warn('这个规则族还没有模板，先复制一套预置模板')
    return
  }
  currentId.value = null
  presetEditing.value = false
  draft.value = {
    name: `${base.template_name}（我家版）`,
    description: '',
    config: clone(base.config)
  }
}

const preview = computed(() => {
  const config = draft.value?.config as unknown as Record<string, any> | undefined
  if (!config) return ''
  const parts = [
    `底分 ${config.base_score}`,
    config.fan_mode === 'exponential' ? '2 的 N 次方' : '线性累加',
    config.fan_cap === null || config.fan_cap === undefined ? '不封顶' : `封顶 ${config.fan_cap} 番`,
    config.allow_chow ? '可以吃' : '不能吃',
    config.turn_timeout?.enabled ? `限时 ${config.turn_timeout.seconds} 秒` : '不限时',
    config.kong_score?.enabled
      ? `杠分 明${config.kong_score.exposed}/暗${config.kong_score.hidden}/补${config.kong_score.added}`
      : '杠不计分'
  ]
  if (config.min_fan_to_win !== undefined) parts.push(`起胡 ${config.min_fan_to_win} 番`)
  if (config.self_draw_multiplier !== undefined) parts.push(`自摸 ×${config.self_draw_multiplier}`)
  if (config.bao_pai) parts.push(config.bao_pai.enabled ? '包牌开' : '包牌关')
  if (config.ting_hint !== undefined) parts.push(config.ting_hint.enabled ? '听牌提示开' : '无听牌提示')
  return parts.join(' · ')
})

async function validate(): Promise<boolean> {
  if (!draft.value) return false
  try {
    const result = await api.post<RuleValidateResult>('/rules/validate', {
      rule_family_code: activeFamily.value,
      config: draft.value.config
    })
    if (!result.ok) {
      toast.error(result.message || '规则配置不合法')
      return false
    }
    return true
  } catch (error) {
    toast.error((error as Error).message)
    return false
  }
}

async function save(): Promise<void> {
  if (!draft.value) return
  if (notReady.value) {
    toast.warn('该规则族引擎未就绪，暂时不能保存模板')
    return
  }
  if (!draft.value.name.trim()) {
    toast.warn('给规则起个名字')
    return
  }
  if (!(await validate())) return

  saving.value = true
  try {
    const payload = {
      template_name: draft.value.name.trim(),
      description: draft.value.description.trim(),
      config: draft.value.config
    }
    if (currentId.value === null) {
      const created = await api.post<RuleTemplate>('/rules', {
        family_code: familyCode.value,
        rule_family_code: activeFamily.value,
        ...payload
      })
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
    const created = await api.post<RuleTemplate>(`/rules/${currentId.value}/duplicate`, {
      family_code: familyCode.value
    })
    await load()
    select(created)
    toast.success('已复制成你们家的模板，可以随便改了')
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

// 切家庭：模板与族能力整份重拉（无缓存串数据）
watch(familyCode, () => {
  currentId.value = null
  activeFamily.value = ''
  draft.value = null
  void load(true)
})
</script>

<template>
  <div class="min-h-screen pb-16">
    <AppHeader />

    <main class="mx-auto max-w-[1400px] px-4 pt-24 sm:px-5">
      <div class="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div class="min-w-0">
          <p class="text-[11px] tracking-[0.32em] text-gold-400/70">RULES</p>
          <h1 class="mt-1 text-2xl font-semibold text-cream-100">自定义积分规则</h1>
          <p class="mt-1 text-sm text-ink-300/80">
            {{ auth.currentFamilyName }} · 底分、番种、杠分、限时都能单独调；开桌时挑一套，本局内不再变。
          </p>
        </div>
        <button type="button" class="btn-gold flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold" @click="createNew">
          <Plus class="h-4 w-4" />
          新建模板
        </button>
      </div>

      <div class="grid gap-5 lg:grid-cols-[280px_1fr]">
        <!-- 族 + 模板列表 -->
        <aside class="glass h-fit rounded-2xl p-3">
          <p class="mb-2 px-1 text-[10px] tracking-[0.24em] text-gold-400/70">规则族</p>
          <div class="mb-3 flex flex-wrap gap-1.5">
            <button
              v-for="family in ruleFamilies"
              :key="family.rule_family_code"
              type="button"
              class="flex items-center gap-1 rounded-lg border px-2 py-1 text-[11px] transition"
              :class="
                activeFamily === family.rule_family_code
                  ? 'border-gold-400/60 bg-gold-400/12 text-cream-100'
                  : 'border-cream-100/12 bg-cream-100/[0.03] text-ink-300/80 hover:border-gold-400/30'
              "
              @click="pickFamily(family.rule_family_code)"
            >
              {{ family.rule_family_name }}
              <span v-if="!family.ready" class="text-vermilion-400">·</span>
            </button>
          </div>

          <p v-if="loading" class="py-6 text-center text-xs text-ink-300/60">加载中…</p>

          <div class="space-y-1.5">
            <button
              v-for="template in visibleTemplates"
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
                <span class="truncate text-sm text-cream-100">{{ template.template_name }}</span>
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

            <p v-if="!loading && !visibleTemplates.length" class="px-2 py-6 text-center text-[11px] text-ink-300/60">
              这个族还没有模板，点右上角「新建模板」
            </p>
          </div>
        </aside>

        <!-- 编辑器 -->
        <section v-if="draft" class="space-y-4">
          <div class="glass rounded-2xl p-4">
            <div class="grid gap-3 sm:grid-cols-[1.2fr_1.8fr]">
              <label class="block">
                <span class="mb-1 block text-xs text-ink-300/80">模板名称</span>
                <input v-model="draft.name" class="field" maxlength="64" :disabled="presetEditing || notReady" />
              </label>
              <label class="block">
                <span class="mb-1 block text-xs text-ink-300/80">一句话说明</span>
                <input
                  v-model="draft.description"
                  class="field"
                  maxlength="120"
                  placeholder="比如：周末长辈局，慢一点不催人"
                  :disabled="presetEditing || notReady"
                />
              </label>
            </div>

            <div class="mt-3 flex flex-wrap items-center gap-2">
              <span class="badge-rule">{{ selectedFamily?.rule_family_name || activeFamily }}</span>
              <span class="badge-family">{{ auth.currentFamilyName }}</span>
              <span
                v-if="notReady"
                class="rounded-full border border-vermilion-500/40 bg-vermilion-500/10 px-2 py-0.5 text-[10px] text-vermilion-400"
              >
                引擎未就绪
              </span>
              <span
                v-else
                class="rounded-full border border-jade-500/40 bg-jade-500/10 px-2 py-0.5 text-[10px] text-jade-400"
              >
                可开桌
              </span>
            </div>

            <div class="mt-3 flex flex-wrap items-center gap-2 rounded-xl border border-gold-400/20 bg-gold-400/[0.06] px-3 py-2">
              <span class="text-[11px] text-gold-300">当前规则</span>
              <span class="text-[11px] text-ink-300/85">{{ preview }}</span>
            </div>

            <p v-if="notReady" class="mt-3 flex items-start gap-2 rounded-lg border border-vermilion-500/35 bg-vermilion-500/10 px-3 py-2 text-[11px] leading-relaxed text-vermilion-400">
              <CircleAlert class="mt-0.5 h-3.5 w-3.5 shrink-0" />
              引擎未就绪：该规则族细则尚未通过验收，模板可以查看，但不能保存、也不能开桌。
            </p>

            <p v-else-if="presetEditing" class="mt-3 rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-[11px] text-amber-400">
              预置模板只读，点「复制为新模板」就能自由调整。
            </p>

            <p v-else-if="!canEditCurrent" class="mt-3 rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-[11px] text-amber-400">
              这套模板由 {{ currentTemplate?.owner_login_id }} 创建，只有创建者或家庭管理员能改。
            </p>
          </div>

          <fieldset :disabled="presetEditing || notReady || !canEditCurrent" class="space-y-4">
            <RuleForm :config="draft.config" :capability="capability" />
            <FanTableEditor :config="draft.config" />
          </fieldset>

          <div class="sticky bottom-4 flex flex-wrap items-center justify-end gap-2 rounded-xl border border-cream-100/10 bg-felt-950/85 px-4 py-3 backdrop-blur">
            <button
              v-if="currentId !== null && !presetEditing && canEditCurrent"
              type="button"
              class="btn-danger-ghost flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm"
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
              v-if="!presetEditing && canEditCurrent"
              type="button"
              class="btn-gold flex items-center gap-2 rounded-lg px-5 py-2 text-sm font-semibold"
              :disabled="saving || notReady"
              @click="save"
            >
              <Loader2 v-if="saving" class="h-4 w-4 animate-spin" />
              <Save v-else class="h-4 w-4" />
              {{ saving ? '保存中…' : notReady ? '引擎未就绪' : '保存规则' }}
            </button>
          </div>
        </section>

        <section v-else class="glass flex min-h-[240px] items-center justify-center rounded-2xl p-6">
          <p class="text-sm text-ink-300/70">选一套模板，或点右上角「新建模板」</p>
        </section>
      </div>
    </main>
  </div>
</template>

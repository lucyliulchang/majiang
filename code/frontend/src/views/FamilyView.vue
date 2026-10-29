<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Check, Loader2, LogIn, Plus, Sparkles, Users } from 'lucide-vue-next'

import AppHeader from '../components/AppHeader.vue'
import { api } from '../api/http'
import { useToast } from '../composables/useToast'
import { useAuthStore } from '../stores/auth'
import { useFamiliesStore } from '../stores/families'
import type { FamilyInfo, FamilyMember, RuleFamily } from '../types'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const families = useFamiliesStore()
const toast = useToast()

const ruleFamilies = ref<RuleFamily[]>([])
const memberCounts = ref<Record<string, number>>({})
const creating = ref(false)
const form = reactive({ family_name: '', family_code: '', default_rule_family_code: '' })

const ROLE_TEXT: Record<string, string> = { OWNER: '家长', ADMIN: '管理员', MEMBER: '成员' }
const ROLE_STYLE: Record<string, string> = {
  OWNER: 'border-gold-400/50 bg-gold-400/15 text-gold-300',
  ADMIN: 'border-family/50 bg-family/15 text-cream-100',
  MEMBER: 'border-cream-100/20 bg-cream-100/5 text-ink-300/85'
}

const currentCode = computed(() => auth.currentFamilyCode)
const empty = computed(() => !families.loading && auth.families.length === 0)

function ruleFamilyName(code: string | null): string {
  if (!code) return '未设置'
  return ruleFamilies.value.find((item) => item.rule_family_code === code)?.rule_family_name || code
}

async function loadMemberCount(code: string): Promise<void> {
  try {
    const members = await api.get<FamilyMember[]>(`/families/${code}/members`)
    memberCounts.value = { ...memberCounts.value, [code]: members.length }
  } catch {
    // 成员数拿不到不影响卡片可用性
  }
}

onMounted(async () => {
  try {
    const [list, ruleFamilyList] = await Promise.all([
      families.load(),
      api.get<RuleFamily[]>('/rule-families').catch(() => [] as RuleFamily[])
    ])
    ruleFamilies.value = ruleFamilyList
    form.default_rule_family_code =
      ruleFamilyList.find((item) => item.ready)?.rule_family_code ||
      auth.currentFamily?.default_rule_family_code ||
      ''
    await Promise.all(list.map((item) => loadMemberCount(item.family_code)))
  } catch (error) {
    toast.error((error as Error).message)
  }
})

async function enter(code: string): Promise<void> {
  try {
    await families.switchTo(code)
    const redirect = route.query.redirect
    if (typeof redirect === 'string' && redirect) router.push(redirect)
    else router.push({ name: 'lobby' })
  } catch (error) {
    toast.error((error as Error).message)
  }
}

/** 家庭成员管理：家长/管理员可进；普通成员也能进（只读名单 + 自助退出） */
function manageMembers(code: string): void {
  router.push({ name: 'family-members', params: { familyCode: code } })
}

function canManage(family: FamilyInfo): boolean {
  return ['OWNER', 'ADMIN'].includes(family.member_role)
}

async function submit(): Promise<void> {
  if (!form.family_name.trim()) {
    toast.warn('给家庭起个名字')
    return
  }
  if (form.family_code && !/^[a-z][a-z0-9_]{1,31}$/.test(form.family_code.trim())) {
    toast.warn('家庭编码需以小写字母开头，只含小写字母、数字与下划线')
    return
  }
  creating.value = true
  try {
    const created = await families.create(
      form.family_name,
      form.family_code,
      form.default_rule_family_code
    )
    memberCounts.value = { ...memberCounts.value, [created.family_code]: 1 }
    toast.success(`「${created.family_name}」已创建`)
    form.family_name = ''
    form.family_code = ''
    await enter(created.family_code)
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <div class="min-h-screen pb-16">
    <AppHeader />

    <main class="mx-auto max-w-[1400px] px-4 pt-24 sm:px-5">
      <div class="mb-6">
        <p class="text-[11px] tracking-[0.32em] text-gold-400/70">FAMILIES</p>
        <h1 class="mt-1 text-2xl font-semibold text-cream-100">我的家庭</h1>
        <p class="mt-1 text-sm text-ink-300/80">
          一个账号可以属于多个家庭；大厅、规则、战绩与皮肤都按当前家庭区分。
        </p>
      </div>

      <div class="grid gap-5 lg:grid-cols-[1.35fr_1fr]">
        <!-- 家庭卡片 -->
        <section class="glass rounded-2xl p-4 sm:p-5">
          <div class="mb-4 flex items-center gap-2">
            <Users class="h-4 w-4 text-gold-300" />
            <h2 class="text-sm font-medium text-cream-100">家庭列表</h2>
            <span class="text-[11px] text-ink-300/60">点「进入」切换当前家庭</span>
          </div>

          <p v-if="families.loading" class="py-10 text-center text-sm text-ink-300/60">加载中…</p>

          <!-- 空状态（05 §4.2） -->
          <div v-else-if="empty" class="flex flex-col items-center gap-3 py-12">
            <div class="flex gap-1.5 opacity-60">
              <div class="h-12 w-8 rounded-md border border-gold-400/30" />
              <div class="h-12 w-8 rounded-md border border-gold-400/30" />
              <div class="h-12 w-8 rounded-md border border-gold-400/30" />
            </div>
            <p class="text-sm text-cream-100">先创建一个家庭，再邀请家人</p>
            <p class="max-w-sm text-center text-xs leading-relaxed text-ink-300/65">
              家人由家长在「成员」里按手机号添加，不需要邀请链接；建好后就能开桌、配规则、换皮肤。
            </p>
            <a href="#create-family" class="btn-gold rounded-lg px-4 py-2 text-sm font-semibold">创建家庭</a>
          </div>

          <div v-else class="grid gap-3 sm:grid-cols-2">
            <div
              v-for="family in auth.families"
              :key="family.family_code"
              class="rounded-xl border p-3.5 transition"
              :class="
                family.family_code === currentCode
                  ? 'border-gold-400/55 bg-gold-400/[0.08]'
                  : 'border-cream-100/12 bg-cream-100/[0.03]'
              "
            >
              <div class="flex items-start justify-between gap-2">
                <div class="min-w-0">
                  <p class="flex items-center gap-1.5 truncate text-sm font-medium text-cream-100">
                    <span class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-family text-[10px] font-semibold text-felt-950">
                      {{ (family.family_name || '家').slice(0, 1) }}
                    </span>
                    {{ family.family_name }}
                  </p>
                  <p class="mt-1 truncate font-mono text-[11px] text-ink-300/60">{{ family.family_code }}</p>
                </div>
                <span
                  class="shrink-0 rounded-full border px-2 py-0.5 text-[10px]"
                  :class="ROLE_STYLE[family.member_role] || ROLE_STYLE.MEMBER"
                >
                  {{ ROLE_TEXT[family.member_role] || family.member_role || '成员' }}
                </span>
              </div>

              <dl class="mt-3 space-y-1 text-[11px] text-ink-300/70">
                <div class="flex justify-between gap-2">
                  <dt>成员</dt>
                  <dd class="text-cream-100/90">{{ memberCounts[family.family_code] ?? '—' }} 人</dd>
                </div>
                <div class="flex justify-between gap-2">
                  <dt>默认规则</dt>
                  <dd class="truncate text-cream-100/90">{{ ruleFamilyName(family.default_rule_family_code) }}</dd>
                </div>
                <div class="flex justify-between gap-2">
                  <dt>默认皮肤</dt>
                  <dd class="truncate text-cream-100/90">{{ family.default_skin_code || '经典（CSS）' }}</dd>
                </div>
                <div class="flex justify-between gap-2">
                  <dt>状态</dt>
                  <dd :class="family.status === 'ENABLED' ? 'text-jade-400' : 'text-vermilion-400'">
                    {{ family.status === 'ENABLED' ? '正常' : '已停用' }}
                  </dd>
                </div>
              </dl>

              <div class="mt-3 flex gap-1.5">
                <button
                  type="button"
                  class="flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2 text-xs font-semibold transition"
                  :class="
                    family.family_code === currentCode
                      ? 'btn-ghost'
                      : 'btn-gold'
                  "
                  :disabled="family.family_code === currentCode"
                  @click="enter(family.family_code)"
                >
                  <Check v-if="family.family_code === currentCode" class="h-3.5 w-3.5" />
                  <LogIn v-else class="h-3.5 w-3.5" />
                  {{ family.family_code === currentCode ? '当前家庭' : '进入' }}
                </button>
                <button
                  type="button"
                  class="btn-ghost flex items-center gap-1 rounded-lg px-2.5 py-2 text-xs"
                  :title="canManage(family) ? '添加/管理家庭成员' : '查看家庭成员'"
                  @click="manageMembers(family.family_code)"
                >
                  <Users class="h-3.5 w-3.5" />
                  成员
                </button>
              </div>
            </div>
          </div>
        </section>

        <!-- 创建家庭 -->
        <section id="create-family" class="glass h-fit rounded-2xl p-4 sm:p-5">
          <div class="mb-4 flex items-center gap-2">
            <Sparkles class="h-4 w-4 text-gold-300" />
            <h2 class="text-sm font-medium text-cream-100">创建家庭</h2>
          </div>

          <label class="mb-3 block">
            <span class="mb-1 block text-xs text-ink-300/80">家庭名称</span>
            <input v-model="form.family_name" class="field" maxlength="32" placeholder="比如 廉家" />
          </label>

          <label class="mb-3 block">
            <span class="mb-1 block text-xs text-ink-300/80">家庭编码（可留空自动生成）</span>
            <input
              v-model="form.family_code"
              class="field font-mono"
              maxlength="32"
              placeholder="lianjia"
            />
            <span class="mt-1 block text-[11px] text-ink-300/55">小写字母开头，可含数字与下划线</span>
          </label>

          <label class="mb-4 block">
            <span class="mb-1 block text-xs text-ink-300/80">默认规则族</span>
            <select v-model="form.default_rule_family_code" class="field">
              <option value="">暂不设置</option>
              <option v-for="family in ruleFamilies" :key="family.rule_family_code" :value="family.rule_family_code">
                {{ family.rule_family_name }}{{ family.ready ? '' : '（引擎未就绪）' }}
              </option>
            </select>
          </label>

          <button
            type="button"
            class="btn-gold flex w-full items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-semibold"
            :disabled="creating"
            @click="submit"
          >
            <Loader2 v-if="creating" class="h-4 w-4 animate-spin" />
            <Plus v-else class="h-4 w-4" />
            {{ creating ? '创建中…' : '创建并进入' }}
          </button>

          <p class="mt-3 text-[11px] leading-relaxed text-ink-300/55">
            创建者自动成为家长（owner）；家人先自行注册，再在家庭卡片的「成员」里按手机号加入，没有「申请加入」入口。
          </p>
        </section>
      </div>
    </main>
  </div>
</template>

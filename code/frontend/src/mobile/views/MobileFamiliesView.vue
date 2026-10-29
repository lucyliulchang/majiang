<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Check, Loader2, LogIn, LogOut, Plus, Users } from 'lucide-vue-next'

import DesktopOnlySheet from '../components/DesktopOnlySheet.vue'
import MobileNavBar from '../components/MobileNavBar.vue'
import MobileSheet from '../components/MobileSheet.vue'
import MobileTabBar from '../components/MobileTabBar.vue'
import { api } from '../../api/http'
import { useToast } from '../../composables/useToast'
import { useAuthStore } from '../../stores/auth'
import { useFamiliesStore } from '../../stores/families'
import type { FamilyInfo, FamilyMember, RuleFamily } from '../../types'

/**
 * 手机版「我的家庭」：只做「看 + 切 + 新建」。
 * 成员增删改（按手机号加人、改角色、移出）留在 PC 版，这里点「成员」给电脑提示。
 */
const router = useRouter()
const auth = useAuthStore()
const families = useFamiliesStore()
const toast = useToast()

const ROLE_TEXT: Record<string, string> = { OWNER: '家长', ADMIN: '管理员', MEMBER: '成员' }
const ROLE_STYLE: Record<string, string> = {
  OWNER: 'border-gold-400/50 bg-gold-400/15 text-gold-300',
  ADMIN: 'border-family/50 bg-family/15 text-cream-100',
  MEMBER: 'border-cream-100/20 bg-cream-100/5 text-ink-300/85'
}

const ruleFamilies = ref<RuleFamily[]>([])
const memberCounts = ref<Record<string, number>>({})
const sheetOpen = ref(false)
const saving = ref(false)
const pcSheet = ref(false)
const form = reactive({ family_name: '', family_code: '', default_rule_family_code: '' })

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
  if (code === currentCode.value) return
  try {
    await families.switchTo(code)
    toast.success(`已切到「${auth.currentFamilyName}」`)
  } catch (error) {
    toast.error((error as Error).message)
  }
}

function openMembers(): void {
  pcSheet.value = true
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
  saving.value = true
  try {
    const created = await families.create(form.family_name, form.family_code, form.default_rule_family_code)
    memberCounts.value = { ...memberCounts.value, [created.family_code]: 1 }
    toast.success(`「${created.family_name}」已创建`)
    form.family_name = ''
    form.family_code = ''
    sheetOpen.value = false
    await router.push({ name: 'lobby' })
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    saving.value = false
  }
}

async function logout(): Promise<void> {
  await auth.logout()
  router.replace({ name: 'login' })
}

function canManage(family: FamilyInfo): boolean {
  return ['OWNER', 'ADMIN'].includes(family.member_role)
}
</script>

<template>
  <div class="mj-app mj-tabbar-hold mj-nav-hold">
    <MobileNavBar title="我的家庭" :subtitle="`${auth.families.length} 个家庭 · 切换后大厅与战绩一起切`">
      <template #right>
        <button
          type="button"
          class="mj-press flex h-10 items-center gap-1 rounded-xl border border-cream-100/10 px-2.5 text-[12px] text-ink-300/80"
          @click="logout"
        >
          <LogOut class="h-4 w-4" />
          退出
        </button>
      </template>
    </MobileNavBar>

    <main class="px-4 pt-4">
      <p v-if="families.loading" class="py-10 text-center text-sm text-ink-300/60">加载中…</p>

      <!-- 空状态（05 §4.2） -->
      <div v-else-if="empty" class="mt-8 flex flex-col items-center gap-3 text-center">
        <div class="flex gap-1.5 opacity-60">
          <div class="h-14 w-9 rounded-md border border-gold-400/30" />
          <div class="h-14 w-9 rounded-md border border-gold-400/30" />
          <div class="h-14 w-9 rounded-md border border-gold-400/30" />
        </div>
        <p class="text-[15px] text-cream-100">先创建一个家庭，再邀请家人</p>
        <p class="max-w-[280px] text-[12px] leading-relaxed text-ink-300/65">
          家人由家长在电脑版的「成员」里按手机号添加，不需要邀请链接；建好后就能开桌、换皮肤。
        </p>
        <button
          type="button"
          class="mj-press btn-gold mt-2 flex min-h-[46px] items-center gap-2 rounded-xl px-5 text-sm font-semibold"
          @click="sheetOpen = true"
        >
          <Plus class="h-4 w-4" />
          创建家庭
        </button>
      </div>

      <div v-else class="space-y-3">
        <article
          v-for="family in auth.families"
          :key="family.family_code"
          class="mj-card p-3.5"
          :class="family.family_code === currentCode ? 'ring-1 ring-gold-400/45' : ''"
        >
          <div class="flex items-start gap-3">
            <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-family text-sm font-semibold text-felt-950">
              {{ (family.family_name || '家').slice(0, 1) }}
            </span>
            <div class="min-w-0 flex-1">
              <p class="flex items-center gap-1.5">
                <span class="truncate text-[15px] font-semibold text-cream-100">{{ family.family_name }}</span>
                <span class="shrink-0 rounded-full border px-1.5 py-0.5 text-[10px]" :class="ROLE_STYLE[family.member_role] || ROLE_STYLE.MEMBER">
                  {{ ROLE_TEXT[family.member_role] || family.member_role || '成员' }}
                </span>
              </p>
              <p class="mt-0.5 truncate font-mono text-[11px] text-ink-300/60">{{ family.family_code }}</p>
            </div>
            <span
              v-if="family.family_code === currentCode"
              class="shrink-0 rounded-full bg-gold-400/15 px-2 py-0.5 text-[10px] text-gold-300"
            >
              当前
            </span>
          </div>

          <dl class="mt-3 grid grid-cols-2 gap-2 text-[11px] text-ink-300/70">
            <div class="mj-card-flat px-2.5 py-1.5">
              <dt>成员</dt>
              <dd class="mt-0.5 text-cream-100/90">{{ memberCounts[family.family_code] ?? '—' }} 人</dd>
            </div>
            <div class="mj-card-flat px-2.5 py-1.5">
              <dt>默认规则</dt>
              <dd class="mt-0.5 truncate text-cream-100/90">{{ ruleFamilyName(family.default_rule_family_code) }}</dd>
            </div>
          </dl>

          <div class="mt-3 flex gap-2">
            <button
              type="button"
              class="mj-press flex min-h-[44px] flex-1 items-center justify-center gap-1.5 rounded-xl text-[13px] font-semibold"
              :class="family.family_code === currentCode ? 'btn-ghost' : 'btn-gold'"
              :disabled="family.family_code === currentCode"
              @click="enter(family.family_code)"
            >
              <Check v-if="family.family_code === currentCode" class="h-4 w-4" />
              <LogIn v-else class="h-4 w-4" />
              {{ family.family_code === currentCode ? '正在使用' : '切换到此家庭' }}
            </button>
            <button
              type="button"
              class="mj-press btn-ghost flex min-h-[44px] items-center gap-1 rounded-xl px-3 text-[13px]"
              @click="openMembers"
            >
              <Users class="h-4 w-4" />
              成员
            </button>
          </div>
          <p class="mt-2 text-[10px] text-ink-300/45">
            {{ canManage(family) ? '你是这个家的管理员，可在电脑版增删成员' : '成员名单与退出家庭在电脑版操作' }}
          </p>
        </article>

        <button
          type="button"
          class="mj-press flex min-h-[48px] w-full items-center justify-center gap-2 rounded-xl border border-dashed border-gold-400/35 text-[13px] text-gold-300"
          @click="sheetOpen = true"
        >
          <Plus class="h-4 w-4" />
          新建家庭
        </button>
      </div>
    </main>

    <MobileSheet
      :open="sheetOpen"
      title="创建家庭"
      subtitle="创建者自动成为家长；家人先在手机版注册，再由家长按手机号加入"
      @close="sheetOpen = false"
    >
      <div class="space-y-3.5 pt-1">
        <label class="block">
          <span class="mb-1.5 block text-[12px] text-ink-300/85">家庭名称</span>
          <input v-model="form.family_name" class="field" maxlength="32" placeholder="比如 廉家" />
        </label>
        <label class="block">
          <span class="mb-1.5 block text-[12px] text-ink-300/85">家庭编码（可留空自动生成）</span>
          <input v-model="form.family_code" class="field font-mono" maxlength="32" placeholder="lianjia" />
          <span class="mt-1 block text-[11px] text-ink-300/55">小写字母开头，可含数字与下划线</span>
        </label>
        <label class="block">
          <span class="mb-1.5 block text-[12px] text-ink-300/85">默认规则族</span>
          <select v-model="form.default_rule_family_code" class="field">
            <option value="">暂不设置</option>
            <option v-for="family in ruleFamilies" :key="family.rule_family_code" :value="family.rule_family_code">
              {{ family.rule_family_name }}{{ family.ready ? '' : '（引擎未就绪）' }}
            </option>
          </select>
        </label>
      </div>

      <template #footer>
        <button
          type="button"
          class="mj-press btn-gold flex min-h-[48px] w-full items-center justify-center gap-2 rounded-xl text-[15px] font-semibold"
          :disabled="saving"
          @click="submit"
        >
          <Loader2 v-if="saving" class="h-4 w-4 animate-spin" />
          <Plus v-else class="h-4 w-4" />
          {{ saving ? '创建中…' : '创建并进入大厅' }}
        </button>
      </template>
    </MobileSheet>

    <DesktopOnlySheet
      :open="pcSheet"
      feature="家庭成员管理"
      desc="按手机号加人、改角色、把成员移出家庭都要看整份名单，电脑上一屏就能看全。"
      @close="pcSheet = false"
    />

    <MobileTabBar />
  </div>
</template>

<script setup lang="ts">
/**
 * 家庭成员管理（04 §3 的成员端点）。
 *
 * 口径：
 *  - 加入家庭没有「申请/邀请码」：家长或管理员按手机号把已注册账号加进来；
 *  - 只有本家庭的 OWNER/ADMIN 能改成员，系统管理员的全局角色不自动获得家庭内权限；
 *  - 普通成员可查看名单，并可以自己退出（owner 不可退出，只能先转让）。
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft,
  Ban,
  CircleAlert,
  Crown,
  Loader2,
  RotateCcw,
  ShieldCheck,
  Trash2,
  UserPlus,
  Users
} from 'lucide-vue-next'

import AppHeader from '../components/AppHeader.vue'
import { api } from '../api/http'
import { useToast } from '../composables/useToast'
import { useAuthStore } from '../stores/auth'
import type { FamilyMember } from '../types'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const toast = useToast()

const PHONE_PATTERN = /^1[3-9]\d{9}$/
const ROLE_TEXT: Record<string, string> = { OWNER: '家长', ADMIN: '管理员', MEMBER: '成员' }
const ROLE_STYLE: Record<string, string> = {
  OWNER: 'border-gold-400/50 bg-gold-400/15 text-gold-300',
  ADMIN: 'border-family/50 bg-family/15 text-cream-100',
  MEMBER: 'border-cream-100/20 bg-cream-100/5 text-ink-300/85'
}
const STATUS_TEXT: Record<string, string> = { ACTIVE: '正常', DISABLED: '已停用', LEFT: '已退出' }
const ROLE_WEIGHT: Record<string, number> = { OWNER: 0, ADMIN: 1, MEMBER: 2 }
const STATUS_WEIGHT: Record<string, number> = { ACTIVE: 0, DISABLED: 1, LEFT: 2 }

type MemberAction = 'transfer' | 'remove' | 'leave'

const members = ref<FamilyMember[]>([])
const loading = ref(true)
const adding = ref(false)
const includeLeft = ref(false)
const acting = ref('')
const pending = ref<{ member: FamilyMember; action: MemberAction } | null>(null)
const addForm = reactive({ login_id: '', member_role: 'MEMBER' })

const familyCode = computed(() => String(route.params.familyCode || ''))
const family = computed(
  () => auth.families.find((item) => item.family_code === familyCode.value) ?? null
)
const myRole = computed(() => family.value?.member_role || '')
const isOwner = computed(() => myRole.value === 'OWNER')
const canManage = computed(() => ['OWNER', 'ADMIN'].includes(myRole.value))

const sortedMembers = computed(() =>
  [...members.value].sort(
    (a, b) =>
      (ROLE_WEIGHT[a.member_role] ?? 9) - (ROLE_WEIGHT[b.member_role] ?? 9) ||
      (STATUS_WEIGHT[a.member_status] ?? 9) - (STATUS_WEIGHT[b.member_status] ?? 9) ||
      (a.joined_ymdhms || '').localeCompare(b.joined_ymdhms || '')
  )
)
const activeCount = computed(
  () => members.value.filter((item) => item.member_status === 'ACTIVE').length
)
const disabledCount = computed(
  () => members.value.filter((item) => item.member_status === 'DISABLED').length
)

function displayName(member: FamilyMember): string {
  return member.nick_name || member.login_id
}

function isSelf(member: FamilyMember): boolean {
  return member.login_id === auth.loginId
}

/** `YYYYMMDDHHMMSS` → `MM-DD HH:MM`，口径与后端库时间一致 */
function formatTime(raw: string): string {
  const text = (raw || '').trim()
  if (text.length < 12) return text || '—'
  return `${text.slice(4, 6)}-${text.slice(6, 8)} ${text.slice(8, 10)}:${text.slice(10, 12)}`
}

async function load(): Promise<void> {
  if (!familyCode.value) return
  loading.value = true
  try {
    const query = includeLeft.value ? '?include_left=1' : ''
    members.value = await api.get<FamilyMember[]>(`/families/${familyCode.value}/members${query}`)
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await auth.ensureSession()
  if (!family.value) {
    toast.error('无权访问该家庭资源')
    router.replace({ name: 'families' })
    return
  }
  await load()
})

watch(includeLeft, () => void load())

async function addMember(): Promise<void> {
  const loginId = addForm.login_id.trim()
  if (!PHONE_PATTERN.test(loginId)) {
    toast.warn('请填写家人的 11 位手机号')
    return
  }
  adding.value = true
  try {
    await api.post<FamilyMember>(`/families/${familyCode.value}/members`, {
      login_id: loginId,
      member_role: addForm.member_role
    })
    toast.success(`已把 ${loginId} 加入「${family.value?.family_name || '家庭'}」`)
    addForm.login_id = ''
    await load()
  } catch (error) {
    // ACCOUNT_USER_NOT_FOUND / MEMBER_ALREADY_EXISTS 等文案由服务端给出
    toast.error((error as Error).message)
  } finally {
    adding.value = false
  }
}

async function patchMember(
  member: FamilyMember,
  patch: { member_role?: string; member_status?: string },
  text: string
): Promise<void> {
  acting.value = member.login_id
  try {
    await api.patch<FamilyMember>(
      `/families/${familyCode.value}/members/${member.login_id}`,
      patch
    )
    toast.success(text)
    pending.value = null
    // 自己的角色/状态可能被这次操作改动，回拉一次会话再刷新名单
    if (isSelf(member) || patch.member_role === 'OWNER') await auth.refresh()
    await load()
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    acting.value = ''
  }
}

async function deleteMember(member: FamilyMember): Promise<void> {
  const self = isSelf(member)
  acting.value = member.login_id
  try {
    await api.del(`/families/${familyCode.value}/members/${member.login_id}`)
    toast.success(self ? '已退出该家庭' : `已把 ${displayName(member)} 移出家庭`)
    pending.value = null
    await auth.refresh()
    if (self) {
      router.replace({ name: 'families' })
      return
    }
    await load()
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    acting.value = ''
  }
}

async function restore(member: FamilyMember): Promise<void> {
  acting.value = member.login_id
  try {
    // 已退出的成员用「重新添加」复活原行（保留 joinedYMDHMS 的更新语义）
    await api.post<FamilyMember>(`/families/${familyCode.value}/members`, {
      login_id: member.login_id,
      member_role: member.member_role === 'OWNER' ? 'MEMBER' : member.member_role
    })
    toast.success(`${displayName(member)} 已恢复为家庭成员`)
    await load()
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    acting.value = ''
  }
}

async function confirmPending(): Promise<void> {
  const target = pending.value
  if (!target) return
  if (target.action === 'transfer') {
    await patchMember(
      target.member,
      { member_role: 'OWNER' },
      `已把家长转让给 ${displayName(target.member)}`
    )
    return
  }
  await deleteMember(target.member)
}
</script>

<template>
  <div class="min-h-screen pb-16">
    <AppHeader />

    <main class="mx-auto max-w-[1100px] px-4 pt-24 sm:px-5">
      <button
        type="button"
        class="mb-4 flex items-center gap-1.5 text-xs text-ink-300/75 transition hover:text-cream-100"
        @click="router.push({ name: 'families' })"
      >
        <ArrowLeft class="h-3.5 w-3.5" />
        我的家庭
      </button>

      <div class="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div class="min-w-0">
          <p class="text-[11px] tracking-[0.32em] text-gold-400/70">MEMBERS</p>
          <h1 class="mt-1 flex items-center gap-2 text-2xl font-semibold text-cream-100">
            <Users class="h-5 w-5 text-gold-300" />
            家庭成员
          </h1>
          <p class="mt-1 text-sm text-ink-300/80">
            {{ family?.family_name || familyCode }} · <span class="font-mono text-[12px]">{{ familyCode }}</span>
            <span class="ml-2 rounded-full border px-1.5 py-0.5 text-[10px]" :class="ROLE_STYLE[myRole] || ROLE_STYLE.MEMBER">
              你是{{ ROLE_TEXT[myRole] || '成员' }}
            </span>
          </p>
        </div>
        <div class="flex flex-wrap items-center gap-1.5 text-[11px]">
          <span class="badge-family">共 {{ members.length }} 人</span>
          <span class="rounded-full border border-jade-500/40 bg-jade-500/10 px-2 py-0.5 text-jade-400">
            正常 {{ activeCount }}
          </span>
          <span v-if="disabledCount" class="rounded-full border border-vermilion-500/40 bg-vermilion-500/10 px-2 py-0.5 text-vermilion-400">
            停用 {{ disabledCount }}
          </span>
        </div>
      </div>

      <div class="grid gap-4 lg:grid-cols-[1fr_340px]">
        <!-- 成员名单 -->
        <section class="glass rounded-2xl p-4 sm:p-5">
          <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 class="text-sm font-medium text-cream-100">名单</h2>
            <label class="flex cursor-pointer items-center gap-1.5 text-[11px] text-ink-300/70">
              <input v-model="includeLeft" type="checkbox" class="h-3.5 w-3.5 accent-[#c9a063]" />
              含已退出成员
            </label>
          </div>

          <p v-if="loading" class="py-12 text-center text-sm text-ink-300/60">加载成员…</p>

          <div v-else-if="!sortedMembers.length" class="py-12 text-center text-sm text-ink-300/60">
            还没有成员，先在右侧按手机号添加家人
          </div>

          <div v-else class="divide-y divide-cream-100/10">
            <div
              v-for="member in sortedMembers"
              :key="member.login_id"
              class="flex flex-wrap items-center gap-3 py-3"
            >
              <span
                class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-felt-950"
                :style="{ backgroundColor: member.member_role === 'OWNER' ? '#C9A063' : '#7FB79B' }"
              >
                {{ displayName(member).slice(0, 1) }}
              </span>

              <div class="min-w-0 flex-1">
                <p class="flex flex-wrap items-center gap-1.5 text-sm text-cream-100">
                  <span class="truncate">{{ displayName(member) }}</span>
                  <span v-if="isSelf(member)" class="rounded bg-cream-100/10 px-1 py-0.5 text-[10px] text-ink-300/80">我</span>
                  <Crown v-if="member.member_role === 'OWNER'" class="h-3 w-3 shrink-0 text-gold-300" />
                </p>
                <p class="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-ink-300/60">
                  <span class="font-mono">{{ member.login_id }}</span>
                  <span>加入 {{ formatTime(member.joined_ymdhms) }}</span>
                </p>
              </div>

              <div class="flex shrink-0 flex-wrap items-center gap-1.5">
                <span
                  class="rounded-full border px-2 py-0.5 text-[10px]"
                  :class="ROLE_STYLE[member.member_role] || ROLE_STYLE.MEMBER"
                >
                  {{ ROLE_TEXT[member.member_role] || member.member_role }}
                </span>
                <span
                  v-if="member.member_status !== 'ACTIVE'"
                  class="rounded-full border px-2 py-0.5 text-[10px]"
                  :class="
                    member.member_status === 'DISABLED'
                      ? 'border-vermilion-500/40 bg-vermilion-500/10 text-vermilion-400'
                      : 'border-cream-100/20 bg-cream-100/5 text-ink-300/70'
                  "
                >
                  {{ STATUS_TEXT[member.member_status] || member.member_status }}
                </span>
              </div>

              <!-- 操作区 -->
              <div class="flex w-full shrink-0 flex-wrap items-center gap-1.5 sm:w-auto">
                <template v-if="canManage && member.member_role !== 'OWNER'">
                  <template v-if="member.member_status === 'ACTIVE'">
                    <button
                      type="button"
                      class="btn-ghost flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[11px]"
                      :disabled="acting === member.login_id"
                      @click="
                        patchMember(
                          member,
                          { member_role: member.member_role === 'ADMIN' ? 'MEMBER' : 'ADMIN' },
                          member.member_role === 'ADMIN'
                            ? `${displayName(member)} 已改为成员`
                            : `${displayName(member)} 已设为管理员`
                        )
                      "
                    >
                      <ShieldCheck class="h-3 w-3" />
                      {{ member.member_role === 'ADMIN' ? '设为成员' : '设为管理员' }}
                    </button>
                    <button
                      v-if="isOwner"
                      type="button"
                      class="btn-ghost flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[11px]"
                      :disabled="acting === member.login_id"
                      @click="pending = { member, action: 'transfer' }"
                    >
                      <Crown class="h-3 w-3" />
                      转让家长
                    </button>
                    <button
                      v-if="!isSelf(member)"
                      type="button"
                      class="btn-ghost flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[11px]"
                      :disabled="acting === member.login_id"
                      @click="
                        patchMember(member, { member_status: 'DISABLED' }, `${displayName(member)} 已停用`)
                      "
                    >
                      <Ban class="h-3 w-3" />
                      停用
                    </button>
                    <button
                      type="button"
                      class="btn-danger-ghost flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[11px]"
                      :disabled="acting === member.login_id"
                      @click="pending = { member, action: isSelf(member) ? 'leave' : 'remove' }"
                    >
                      <Trash2 class="h-3 w-3" />
                      {{ isSelf(member) ? '退出' : '移出' }}
                    </button>
                  </template>
                  <template v-else-if="member.member_status === 'DISABLED'">
                    <button
                      type="button"
                      class="btn-ghost flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[11px]"
                      :disabled="acting === member.login_id"
                      @click="
                        patchMember(member, { member_status: 'ACTIVE' }, `${displayName(member)} 已启用`)
                      "
                    >
                      启用
                    </button>
                    <button
                      type="button"
                      class="btn-danger-ghost flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[11px]"
                      :disabled="acting === member.login_id"
                      @click="pending = { member, action: 'remove' }"
                    >
                      <Trash2 class="h-3 w-3" />
                      移出
                    </button>
                  </template>
                </template>

                <button
                  v-if="canManage && member.member_status === 'LEFT'"
                  type="button"
                  class="btn-ghost flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[11px]"
                  :disabled="acting === member.login_id"
                  @click="restore(member)"
                >
                  <RotateCcw class="h-3 w-3" />
                  恢复
                </button>

                <!-- 普通成员：只能自己退出 -->
                <button
                  v-if="!canManage && isSelf(member) && member.member_role !== 'OWNER'"
                  type="button"
                  class="btn-danger-ghost flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[11px]"
                  :disabled="acting === member.login_id"
                  @click="pending = { member, action: 'leave' }"
                >
                  <Trash2 class="h-3 w-3" />
                  退出家庭
                </button>
              </div>
            </div>
          </div>

          <p class="mt-3 text-[11px] leading-relaxed text-ink-300/55">
            家长（owner）全局唯一，不能被停用或移出，只能先转让；移出后原记录保留为「已退出」，可以再恢复。
          </p>
        </section>

        <!-- 添加成员 / 说明 -->
        <aside class="space-y-4">
          <section v-if="canManage" class="glass h-fit rounded-2xl p-4 sm:p-5">
            <div class="mb-4 flex items-center gap-2">
              <UserPlus class="h-4 w-4 text-gold-300" />
              <h2 class="text-sm font-medium text-cream-100">添加家人</h2>
            </div>

            <label class="mb-3 block">
              <span class="mb-1 block text-xs text-ink-300/80">手机号（账号已注册）</span>
              <input
                v-model="addForm.login_id"
                class="field font-mono"
                inputmode="numeric"
                maxlength="11"
                placeholder="13xxxxxxxxx"
                @keyup.enter="addMember"
              />
            </label>

            <label class="mb-4 block">
              <span class="mb-1 block text-xs text-ink-300/80">加入角色</span>
              <select v-model="addForm.member_role" class="field">
                <option value="MEMBER">成员</option>
                <option value="ADMIN">管理员</option>
              </select>
            </label>

            <button
              type="button"
              class="btn-gold flex w-full items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-semibold"
              :disabled="adding"
              @click="addMember"
            >
              <Loader2 v-if="adding" class="h-4 w-4 animate-spin" />
              <UserPlus v-else class="h-4 w-4" />
              {{ adding ? '添加中…' : '添加成员' }}
            </button>

            <p class="mt-3 text-[11px] leading-relaxed text-ink-300/55">
              没有邀请码或申请入口：家人先自行注册，再由家长/管理员按手机号加入。添加后对方刷新页面即可看到这个家庭。
            </p>
          </section>

          <section v-else class="glass h-fit rounded-2xl p-4 sm:p-5">
            <h2 class="text-sm font-medium text-cream-100">成员管理需要管理员权限</h2>
            <p class="mt-2 text-[11px] leading-relaxed text-ink-300/65">
              你现在是普通成员，可以查看名单、自己退出家庭。添加或移出家人请让家长（owner）或管理员在「家庭成员」里操作。
            </p>
          </section>

          <section class="glass-soft rounded-2xl p-4">
            <p class="text-xs font-medium text-cream-100">角色说明</p>
            <ul class="mt-2 space-y-1.5 text-[11px] leading-relaxed text-ink-300/70">
              <li>家长：唯一，可转让、可管理全部成员与家庭设置</li>
              <li>管理员：可添加/移出成员、改角色，不能转让家长</li>
              <li>成员：可开桌、看战绩、自己退出家庭</li>
            </ul>
          </section>
        </aside>
      </div>

      <!-- 危险操作二次确认 -->
      <div
        v-if="pending"
        class="fixed inset-0 z-[70] flex items-center justify-center bg-felt-950/88 px-4 backdrop-blur-sm"
        @click.self="pending = null"
      >
        <div class="glass w-full max-w-sm rounded-2xl p-5">
          <p class="flex items-center gap-2 text-sm font-medium text-cream-100">
            <CircleAlert class="h-4 w-4 text-vermilion-400" />
            {{
              pending.action === 'transfer'
                ? '转让家长'
                : pending.action === 'leave'
                  ? '退出家庭'
                  : '移出成员'
            }}
          </p>
          <p class="mt-2 text-xs leading-relaxed text-ink-300/75">
            <template v-if="pending.action === 'transfer'">
              把「{{ family?.family_name }}」的家长转让给 {{ displayName(pending.member) }} 后，你将成为管理员，无法再收回，除非对方转让回来。
            </template>
            <template v-else-if="pending.action === 'leave'">
              你退出后不再看到这个家庭的大厅与战绩，需要家长重新添加才能回来。
            </template>
            <template v-else>
              {{ displayName(pending.member) }} 将被移出家庭，暂时无法进入大厅与牌桌；之后可以再恢复。
            </template>
          </p>
          <div class="mt-4 flex justify-end gap-2">
            <button type="button" class="btn-ghost rounded-lg px-4 py-2 text-sm" @click="pending = null">
              取消
            </button>
            <button
              type="button"
              class="btn-danger-ghost flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-semibold"
              :disabled="acting === pending.member.login_id"
              @click="confirmPending"
            >
              <Loader2 v-if="acting === pending.member.login_id" class="h-4 w-4 animate-spin" />
              {{
                pending.action === 'transfer'
                  ? '确认转让'
                  : pending.action === 'leave'
                    ? '确认退出'
                    : '确认移出'
              }}
            </button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

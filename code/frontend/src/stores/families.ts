/**
 * 家庭与成员（04 §3）。
 *
 * 列表与「当前家庭」的唯一权威在 `stores/auth.ts`（登录/`/auth/me` 与切家庭都写那里）；
 * 本 store 只做家庭域的增删改查，并把结果回写到 auth，避免两处各自维护一份名单。
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { api } from '../api/http'
import type { FamilyInfo, FamilyMember } from '../types'
import { useAuthStore } from './auth'

export const useFamiliesStore = defineStore('families', () => {
  const auth = useAuthStore()

  const members = ref<FamilyMember[]>([])
  const loading = ref(false)
  const membersLoading = ref(false)
  const saving = ref(false)

  const families = computed(() => auth.families)
  const currentFamily = computed(() => auth.currentFamily)
  const hasFamily = computed(() => Boolean(auth.currentFamilyCode))
  const isEmpty = computed(() => !loading.value && families.value.length === 0)

  async function load(): Promise<FamilyInfo[]> {
    loading.value = true
    try {
      const list = await api.get<FamilyInfo[]>('/families')
      auth.setFamilies(list, auth.currentFamilyCode)
      return list
    } finally {
      loading.value = false
    }
  }

  /** 创建家庭：`family_code` 留空由服务端按名称生成（04 §3） */
  async function create(
    familyName: string,
    familyCode = '',
    defaultRuleFamilyCode = ''
  ): Promise<FamilyInfo> {
    saving.value = true
    try {
      const created = await api.post<FamilyInfo>('/families', {
        family_name: familyName.trim(),
        family_code: familyCode.trim()
      })
      if (defaultRuleFamilyCode) {
        try {
          await api.patch<FamilyInfo>(`/families/${created.family_code}`, {
            default_rule_family_code: defaultRuleFamilyCode
          })
        } catch {
          // 默认规则族只是便捷项，失败不阻断建家庭
        }
      }
      const list = await api.get<FamilyInfo[]>('/families')
      auth.setFamilies(list, created.family_code)
      await auth.loadPref()
      return created
    } finally {
      saving.value = false
    }
  }

  /** 切换当前家庭：写 `mj_user_pref.lastFamilyID`，各页 watch currentFamilyCode 重新拉数 */
  async function switchTo(familyCode: string): Promise<void> {
    if (!familyCode || familyCode === auth.currentFamilyCode) return
    await auth.switchFamily(familyCode)
    members.value = []
  }

  async function loadMembers(includeLeft = false): Promise<FamilyMember[]> {
    const code = auth.currentFamilyCode
    if (!code) {
      members.value = []
      return []
    }
    membersLoading.value = true
    try {
      const query = includeLeft ? '?include_left=1' : ''
      members.value = await api.get<FamilyMember[]>(`/families/${code}/members${query}`)
      return members.value
    } finally {
      membersLoading.value = false
    }
  }

  async function addMember(loginId: string, memberRole = 'MEMBER'): Promise<FamilyMember> {
    const code = auth.currentFamilyCode
    if (!code) throw new Error('请先选择家庭')
    const member = await api.post<FamilyMember>(`/families/${code}/members`, {
      login_id: loginId.trim(),
      member_role: memberRole
    })
    await loadMembers()
    return member
  }

  async function updateMember(
    loginId: string,
    patch: { member_role?: string; member_status?: string }
  ): Promise<FamilyMember> {
    const code = auth.currentFamilyCode
    if (!code) throw new Error('请先选择家庭')
    const member = await api.patch<FamilyMember>(`/families/${code}/members/${loginId}`, patch)
    await loadMembers()
    return member
  }

  async function removeMember(loginId: string): Promise<void> {
    const code = auth.currentFamilyCode
    if (!code) throw new Error('请先选择家庭')
    await api.del(`/families/${code}/members/${loginId}`)
    members.value = members.value.filter((item) => item.login_id !== loginId)
  }

  return {
    members,
    loading,
    membersLoading,
    saving,
    families,
    currentFamily,
    hasFamily,
    isEmpty,
    load,
    create,
    switchTo,
    loadMembers,
    addMember,
    updateMember,
    removeMember
  }
})

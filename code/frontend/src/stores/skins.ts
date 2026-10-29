/**
 * 皮肤（04 §8、05 §6）。
 *
 * 关键约定：
 * 1. 清单一次性拉取后内存缓存，带 `If-None-Match` 协商（304 沿用缓存）；
 * 2. **切换皮肤只换 `assetMap`，不重新拉清单、不刷新牌桌**（05 §6.4）；
 * 3. 缺图不报错：`assetOf()` 返回空串，Tile 回退 CSS（05 §6.3）；
 * 4. 家庭切换后清单必须失效，否则会串数据。
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { api } from '../api/http'
import type { SkinAssetInfo, SkinInfo } from '../types'
import { useAuthStore } from './auth'
import { useToast } from '../composables/useToast'

/** 内置兜底皮肤编码：无资源，纯 CSS 渲染 */
export const CSS_CLASSIC = 'css-classic'

export const useSkinsStore = defineStore('skins', () => {
  const auth = useAuthStore()
  const toast = useToast()

  const skins = ref<SkinInfo[]>([])
  const etag = ref('')
  const loading = ref(false)
  /** 清单属于哪个家庭：与当前家庭不一致时视为未加载 */
  const loadedFamily = ref('')
  /** 当前选中的皮肤编码（CSS 兜底时为 css-classic） */
  const activeCode = ref<string>(CSS_CLASSIC)

  const enabledSkins = computed(() => skins.value.filter((item) => item.status === 'ENABLED'))
  const activeSkin = computed<SkinInfo | null>(
    () => enabledSkins.value.find((item) => item.skin_code === activeCode.value) ?? null
  )
  /** 当前生效的 tile_key → URL 映射；空对象即全部回退 CSS */
  const assetMap = computed<Record<string, string>>(
    () => activeSkin.value?.assets ?? {}
  )
  const isCssClassic = computed(() => !activeSkin.value || Object.keys(assetMap.value).length === 0)

  function assetOf(key: string): string {
    return assetMap.value[key] || ''
  }

  /** 选中皮肤：`pref.skin_code` 可见就优先用它，否则用家庭默认，再否则 CSS */
  function resolveActive(): string {
    const prefCode = auth.pref.skin_code || ''
    if (prefCode && enabledSkins.value.some((item) => item.skin_code === prefCode)) return prefCode
    const fallback = enabledSkins.value.find((item) => item.is_default)
    return fallback?.skin_code || CSS_CLASSIC
  }

  function reset(): void {
    skins.value = []
    etag.value = ''
    loadedFamily.value = ''
    activeCode.value = CSS_CLASSIC
  }

  /**
   * 拉清单。`force=true` 忽略本地缓存（新建/上传/发布后调用）。
   * `includeDisabled` 只给管理页用（后端要求家庭管理员）。
   */
  async function load(force = false, includeDisabled = false): Promise<void> {
    const familyCode = auth.currentFamilyCode
    if (!familyCode) {
      reset()
      return
    }
    const familyChanged = loadedFamily.value !== familyCode
    if (!force && !familyChanged && skins.value.length) return

    loading.value = true
    try {
      const query = new URLSearchParams({ family_code: familyCode })
      if (includeDisabled) query.set('include_disabled', '1')
      const cachedEtag = familyChanged || force ? '' : etag.value
      const result = await api.getWithMeta<SkinInfo[]>(
        `/skins?${query.toString()}`,
        includeDisabled ? '' : cachedEtag
      )
      if (result.notModified) return
      skins.value = result.data ?? []
      etag.value = result.etag
      loadedFamily.value = familyCode
      activeCode.value = resolveActive()
    } catch (error) {
      // 清单拉不到时整桌回退 CSS，不影响对局（05 §6.3）
      reset()
      if ((error as { status?: number }).status !== 403) toast.error((error as Error).message)
    } finally {
      loading.value = false
    }
  }

  /** 切到当前家庭时若还没加载过，补一次（进桌/进大厅时调用） */
  async function ensureLoaded(): Promise<void> {
    if (!auth.currentFamilyCode) return
    if (loadedFamily.value === auth.currentFamilyCode && skins.value.length) return
    await load()
  }

  /**
   * 偏好到达后校正选中项（清单可能先于 `/user/pref` 到，首屏会先落到默认皮肤）。
   * 只改本地 `activeCode`，不发请求。
   */
  function syncWithPref(): void {
    if (!loadedFamily.value) return
    activeCode.value = resolveActive()
  }

  /**
   * 皮肤切换即时生效：先改本地 `activeCode`（牌桌立刻重渲染），再异步持久化偏好。
   * 持久化失败只提示，不打断牌桌。
   */
  async function setActive(skinCode: string): Promise<void> {
    activeCode.value = skinCode || CSS_CLASSIC
    const payload = activeCode.value === CSS_CLASSIC ? '' : activeCode.value
    if ((auth.pref.skin_code || '') === payload) return
    try {
      await auth.savePref({ skin_code: payload })
    } catch (error) {
      toast.warn(`皮肤偏好没保存：${(error as Error).message}`)
    }
  }

  /** 单个资源上传（管理页）：成功后局部更新 `assets`，不重拉整表 */
  async function uploadAsset(skinCode: string, tileKey: string, file: File): Promise<SkinAssetInfo> {
    const result = await api.upload<SkinAssetInfo>(`/skins/${skinCode}/${tileKey}`, file)
    // file_id 是库内相对路径，按服务端同一规则拼 URL
    const url = `/majiangapp/${result.file_id.replace(/^\/+/, '')}`
    patchLocalAsset(skinCode, tileKey, url)
    return result
  }

  async function deleteAsset(skinCode: string, tileKey: string): Promise<void> {
    await api.del(`/skins/${skinCode}/${tileKey}`)
    patchLocalAsset(skinCode, tileKey, '')
  }

  function patchLocalAsset(skinCode: string, tileKey: string, url: string): void {
    const target = skins.value.find((item) => item.skin_code === skinCode)
    if (!target) return
    const assets = { ...target.assets }
    if (url) assets[tileKey] = url
    else delete assets[tileKey]
    target.assets = assets
    target.asset_count = Object.keys(assets).filter((key) => key !== 'preview').length
    // 清单已变，让后续协商拿到新 ETag
    etag.value = ''
  }

  /** 从服务端刷新单个皮肤（进编辑页时用；含 DISABLED） */
  async function fetchSkin(skinCode: string): Promise<SkinInfo> {
    const skin = await api.get<SkinInfo>(`/skins/${skinCode}?family_code=${encodeURIComponent(auth.currentFamilyCode || '')}`)
    const index = skins.value.findIndex((item) => item.skin_code === skinCode)
    if (index >= 0) skins.value[index] = skin
    else skins.value.push(skin)
    return skin
  }

  async function createSkin(skinName: string, skinCode = ''): Promise<SkinInfo> {
    const created = await api.post<SkinInfo>('/skins', {
      family_code: auth.currentFamilyCode || '',
      skin_code: skinCode.trim(),
      skin_name: skinName.trim()
    })
    skins.value.push(created)
    etag.value = ''
    return created
  }

  async function patchSkin(
    skinCode: string,
    patch: { skin_name?: string; status?: string; sort_order?: number; is_default?: boolean }
  ): Promise<SkinInfo> {
    const updated = await api.patch<SkinInfo>(`/skins/${skinCode}`, patch)
    const index = skins.value.findIndex((item) => item.skin_code === skinCode)
    if (index >= 0) skins.value[index] = updated
    etag.value = ''
    if (updated.is_default && updated.status === 'ENABLED') {
      // 同家庭唯一默认：其余行的 is_default 立即置 false（避免 UI 出现两个默认徽标）
      skins.value = skins.value.map((item) =>
        item.skin_code === updated.skin_code ? item : { ...item, is_default: false }
      )
    }
    return updated
  }

  async function removeSkin(skinCode: string): Promise<void> {
    await api.del(`/skins/${skinCode}`)
    skins.value = skins.value.filter((item) => item.skin_code !== skinCode)
    if (activeCode.value === skinCode) activeCode.value = resolveActive()
    etag.value = ''
  }

  return {
    skins,
    enabledSkins,
    activeSkin,
    activeCode,
    assetMap,
    isCssClassic,
    loading,
    loadedFamily,
    assetOf,
    load,
    ensureLoaded,
    syncWithPref,
    setActive,
    uploadAsset,
    deleteAsset,
    fetchSkin,
    createSkin,
    patchSkin,
    removeSkin,
    reset
  }
})

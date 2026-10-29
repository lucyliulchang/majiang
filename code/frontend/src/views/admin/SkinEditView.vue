<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Check, CircleAlert, Image, Loader2, Palette, Star, Trash2, Upload } from 'lucide-vue-next'

import AppHeader from '../../components/AppHeader.vue'
import Tile from '../../components/table/Tile.vue'
import { useToast } from '../../composables/useToast'
import { useSkinsStore } from '../../stores/skins'
import { TILE_KEYS, tileKeyName } from '../../utils/tile'
import type { SkinInfo } from '../../types'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const skins = useSkinsStore()

const skinCode = String(route.params.skinCode || '')
const skin = ref<SkinInfo | null>(null)
const loading = ref(true)
const uploadingKey = ref('')
const batchUploading = ref(false)
const confirmKey = ref('')
const publishing = ref(false)
const batchInput = ref<HTMLInputElement | null>(null)

/** 05 §6.1：34 张牌 + 牌背 = 35 个必填；preview 不是 tile_key */
const keys = [...TILE_KEYS]
const TOTAL_KEYS = keys.length

const assets = computed<Record<string, string>>(() => skin.value?.assets || {})
const uploadedCount = computed(() => keys.filter((key) => Boolean(assets.value[key])).length)
const missingKeys = computed(() => keys.filter((key) => !assets.value[key]))
const complete = computed(() => uploadedCount.value >= TOTAL_KEYS)
const isEnabled = computed(() => skin.value?.status === 'ENABLED')
const progress = computed(() => Math.round((uploadedCount.value / TOTAL_KEYS) * 100))

/** 预览样例：一手牌 + 牌河 + 牌背 */
const sampleHand = [0, 0, 2, 4, 8, 9, 11, 15, 18, 20, 24, 27, 33]
const sampleDiscard = [1, 5, 12, 19, 26, 31, 30, 7]

async function load(): Promise<void> {
  loading.value = true
  try {
    skin.value = await skins.fetchSkin(skinCode)
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function refresh(): Promise<void> {
  skin.value = await skins.fetchSkin(skinCode)
}

async function onPickFile(key: string, event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  await uploadOne(key, file)
}

async function uploadOne(key: string, file: File): Promise<void> {
  if (!skin.value) return
  uploadingKey.value = key
  try {
    await skins.uploadAsset(skinCode, key, file)
    await refresh()
    toast.success(`${key === 'preview' ? '预览图' : tileKeyName(key)} 已上传`)
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    uploadingKey.value = ''
  }
}

/** 文件名的 basename 即 tile_key（05 §6.5）：`1m.png` / `1m@2x.png` / `back.webp` */
function keyFromFileName(name: string): string {
  const base = name.replace(/\.[^.]+$/, '').toLowerCase()
  const cleaned = base.replace(/[-_]?@?\d+x?$/, '').replace(/@2x$/, '')
  return cleaned
}

async function onBatchPick(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  input.value = ''
  if (!files.length || !skin.value) return

  const allowed = new Set<string>([...keys, 'preview'])
  const matched: { key: string; file: File }[] = []
  const skipped: string[] = []
  for (const file of files) {
    const key = keyFromFileName(file.name)
    if (allowed.has(key)) matched.push({ key, file })
    else skipped.push(file.name)
  }

  if (!matched.length) {
    toast.warn('文件名需要是 1m.png、east.png、back.png 这样的 tile_key')
    return
  }

  batchUploading.value = true
  let done = 0
  try {
    for (const item of matched) {
      uploadingKey.value = item.key
      try {
        await skins.uploadAsset(skinCode, item.key, item.file)
        done += 1
      } catch (error) {
        toast.error(`${item.file.name}：${(error as Error).message}`)
      }
    }
    await refresh()
    toast.success(`批量上传完成 ${done}/${matched.length}${skipped.length ? `，跳过 ${skipped.length} 个文件名不匹配的` : ''}`)
  } finally {
    uploadingKey.value = ''
    batchUploading.value = false
  }
}

async function removeAsset(key: string): Promise<void> {
  if (confirmKey.value !== key) {
    confirmKey.value = key
    window.setTimeout(() => {
      if (confirmKey.value === key) confirmKey.value = ''
    }, 4000)
    return
  }
  confirmKey.value = ''
  uploadingKey.value = key
  try {
    await skins.deleteAsset(skinCode, key)
    await refresh()
    toast.success('已删除，这一张会回退 CSS 牌面')
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    uploadingKey.value = ''
  }
}

async function publish(): Promise<void> {
  if (!skin.value) return
  publishing.value = true
  try {
    skin.value = await skins.patchSkin(skinCode, { status: 'ENABLED' })
    toast.success('已发布，家人可以在牌桌上选到它了')
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    publishing.value = false
  }
}

async function disable(): Promise<void> {
  if (!skin.value) return
  publishing.value = true
  try {
    skin.value = await skins.patchSkin(skinCode, { status: 'DISABLED' })
    toast.success('已停用')
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    publishing.value = false
  }
}

async function setDefault(): Promise<void> {
  if (!skin.value) return
  publishing.value = true
  try {
    skin.value = await skins.patchSkin(skinCode, { is_default: true })
    toast.success('已设为家庭默认皮肤')
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    publishing.value = false
  }
}

async function applyToMyTable(): Promise<void> {
  await skins.setActive(skinCode)
  toast.success('已切换到你自己的牌桌（不刷新页面）')
}
</script>

<template>
  <div class="min-h-screen pb-16">
    <AppHeader />

    <main class="mx-auto max-w-[1400px] px-4 pt-24 sm:px-5">
      <div class="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0">
          <button
            type="button"
            class="mb-2 flex items-center gap-1 text-[11px] text-gold-300/80 transition hover:text-gold-300"
            @click="router.push({ name: 'skins' })"
          >
            <ArrowLeft class="h-3.5 w-3.5" />
            返回皮肤列表
          </button>
          <h1 class="flex flex-wrap items-center gap-2 text-xl font-semibold text-cream-100">
            <Palette class="h-5 w-5 shrink-0 text-skin" />
            {{ skin?.skin_name || skinCode }}
            <span
              v-if="skin"
              class="rounded-full border px-2 py-0.5 text-[10px]"
              :class="
                isEnabled
                  ? 'border-jade-500/40 bg-jade-500/10 text-jade-400'
                  : 'border-cream-100/20 bg-cream-100/5 text-ink-300/70'
              "
            >
              {{ isEnabled ? '已发布' : '草稿' }}
            </span>
            <span v-if="skin?.is_default" class="flex items-center gap-0.5 rounded bg-gold-400/20 px-1.5 py-0.5 text-[10px] text-gold-300">
              <Star class="h-2.5 w-2.5" />家庭默认
            </span>
          </h1>
          <p class="mt-1 truncate font-mono text-[11px] text-ink-300/60">{{ skinCode }}</p>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <label class="btn-ghost flex cursor-pointer items-center gap-1.5 rounded-lg px-3 py-2 text-xs">
            <Upload class="h-3.5 w-3.5" />
            批量上传
            <input
              ref="batchInput"
              type="file"
              class="hidden"
              multiple
              accept="image/png,image/webp"
              :disabled="batchUploading"
              @change="onBatchPick"
            />
          </label>
          <button
            v-if="isEnabled"
            type="button"
            class="btn-ghost rounded-lg px-3 py-2 text-xs"
            :disabled="publishing"
            @click="applyToMyTable"
          >
            应用到我的牌桌
          </button>
          <button
            v-if="isEnabled && !skin?.is_default"
            type="button"
            class="btn-ghost flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs"
            :disabled="publishing"
            @click="setDefault"
          >
            <Star class="h-3.5 w-3.5" />
            设为默认
          </button>
          <button
            v-if="!isEnabled"
            type="button"
            class="btn-gold flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold"
            :disabled="publishing || !complete"
            @click="publish"
          >
            <Loader2 v-if="publishing" class="h-3.5 w-3.5 animate-spin" />
            <Check v-else class="h-3.5 w-3.5" />
            {{ complete ? '发布' : `还缺 ${TOTAL_KEYS - uploadedCount} 张` }}
          </button>
          <button
            v-else
            type="button"
            class="btn-danger-ghost rounded-lg px-3 py-2 text-xs"
            :disabled="publishing"
            @click="disable"
          >
            停用
          </button>
        </div>
      </div>

      <p v-if="loading" class="glass rounded-2xl py-12 text-center text-sm text-ink-300/60">加载中…</p>

      <div v-else class="grid gap-4 xl:grid-cols-[1.6fr_1fr]">
        <!-- 35 格 -->
        <section class="glass rounded-2xl p-4">
          <div class="mb-3">
            <div class="mb-1 flex flex-wrap items-center justify-between gap-2 text-[11px]">
              <span :class="complete ? 'text-jade-400' : 'text-gold-300'">
                已上传 {{ uploadedCount }}/{{ TOTAL_KEYS }}
              </span>
              <span v-if="!complete" class="truncate text-ink-300/65">
                缺：{{ missingKeys.slice(0, 6).map(tileKeyName).join('、') }}{{ missingKeys.length > 6 ? ' …' : '' }}
              </span>
            </div>
            <div class="h-1.5 overflow-hidden rounded-full bg-cream-100/10">
              <div
                class="h-full rounded-full transition-all"
                :class="complete ? 'bg-jade-500' : 'bg-gold-400'"
                :style="{ width: `${progress}%` }"
              />
            </div>
          </div>

          <div class="grid grid-cols-4 gap-2 sm:grid-cols-6 md:grid-cols-7">
            <div v-for="key in keys" :key="key" class="min-w-0">
              <div class="asset-slot group aspect-[2/3] overflow-hidden p-1">
                <img
                  v-if="assets[key]"
                  :src="assets[key]"
                  :alt="tileKeyName(key)"
                  class="h-full w-full object-contain"
                  loading="lazy"
                />
                <template v-else>
                  <Image class="h-4 w-4 text-ink-300/40" />
                  <span class="text-[9px] text-ink-300/50">未上传</span>
                </template>

                <Loader2
                  v-if="uploadingKey === key"
                  class="absolute inset-0 m-auto h-4 w-4 animate-spin text-gold-300"
                />
              </div>

              <p class="mt-0.5 truncate text-center text-[9px] text-ink-300/60">{{ tileKeyName(key) }}</p>

              <div class="mt-0.5 flex items-center justify-center gap-1">
                <label class="cursor-pointer rounded px-1 text-[9px] text-gold-300/85 hover:text-gold-300">
                  {{ assets[key] ? '替换' : '上传' }}
                  <input
                    type="file"
                    class="hidden"
                    accept="image/png,image/webp"
                    @change="onPickFile(key, $event)"
                  />
                </label>
                <button
                  v-if="assets[key]"
                  type="button"
                  class="rounded px-1 text-[9px]"
                  :class="confirmKey === key ? 'text-vermilion-400' : 'text-ink-300/50 hover:text-vermilion-400'"
                  @click="removeAsset(key)"
                >
                  {{ confirmKey === key ? '确认删' : '删除' }}
                </button>
              </div>
            </div>
          </div>

          <!-- 预览图（不是 tile_key，不计入 35） -->
          <div class="mt-4 rounded-xl border border-cream-100/10 bg-cream-100/[0.03] p-3">
            <p class="mb-2 text-xs text-cream-100">预览图（可选，列表展示用，不计入 35 张）</p>
            <div class="flex items-center gap-3">
              <div class="flex h-[64px] w-[96px] shrink-0 items-center justify-center overflow-hidden rounded-lg border border-gold-400/25 bg-felt-950/50">
                <img
                  v-if="skin?.preview_url"
                  :src="skin.preview_url"
                  alt="皮肤预览"
                  class="h-full w-full object-contain"
                  loading="lazy"
                />
                <Image v-else class="h-4 w-4 text-ink-300/40" />
              </div>
              <div class="flex flex-wrap items-center gap-2">
                <label class="btn-ghost cursor-pointer rounded-lg px-3 py-1.5 text-[11px]">
                  {{ skin?.preview_url ? '替换预览图' : '上传预览图' }}
                  <input type="file" class="hidden" accept="image/png,image/webp" @change="onPickFile('preview', $event)" />
                </label>
                <button
                  v-if="skin?.preview_url"
                  type="button"
                  class="rounded px-2 py-1 text-[11px]"
                  :class="confirmKey === 'preview' ? 'text-vermilion-400' : 'text-ink-300/50 hover:text-vermilion-400'"
                  @click="removeAsset('preview')"
                >
                  {{ confirmKey === 'preview' ? '确认删除' : '删除' }}
                </button>
                <span class="text-[10px] text-ink-300/55">建议 480×320（3:2），≤800 KB</span>
              </div>
            </div>
          </div>

          <p class="mt-3 flex items-start gap-1.5 text-[10px] leading-relaxed text-ink-300/55">
            <CircleAlert class="mt-0.5 h-3 w-3 shrink-0" />
            规格：牌面 192×288（2:3）、PNG/WebP、单张 ≤512 KB、单套 ≤8 MB；文件名即 tile_key（1m.png、east.png、back.png）。
          </p>
        </section>

        <!-- 实时预览 -->
        <section class="glass h-fit rounded-2xl p-4">
          <p class="mb-3 flex items-center gap-1.5 text-sm font-medium text-gold-300">
            <Palette class="h-4 w-4" /> 实时预览
          </p>

          <div class="rounded-xl border border-cream-100/[0.06] bg-felt-950/30 p-3">
            <p class="mb-1.5 text-[10px] tracking-[0.2em] text-ink-300/50">手牌</p>
            <div class="flex flex-wrap gap-[3px]">
              <Tile
                v-for="(tile, index) in sampleHand"
                :key="`h-${index}`"
                :tile="tile"
                size="md"
                :skin-code="skinCode"
                :selected="index === 3"
                eager
              />
            </div>

            <p class="mb-1.5 mt-4 text-[10px] tracking-[0.2em] text-ink-300/50">牌河 · 牌背</p>
            <div class="flex flex-wrap items-end gap-[3px]">
              <Tile v-for="(tile, index) in sampleDiscard" :key="`d-${index}`" :tile="tile" size="sm" :skin-code="skinCode" :dim="index > 5" />
              <span class="mx-1 h-6 w-px bg-cream-100/15" />
              <Tile :tile="0" size="sm" face-down :skin-code="skinCode" />
              <Tile :tile="0" size="sm" face-down :skin-code="skinCode" :selected="true" />
            </div>

            <p class="mb-1.5 mt-4 text-[10px] tracking-[0.2em] text-ink-300/50">缺图回退</p>
            <div class="flex flex-wrap items-end gap-[3px]">
              <Tile :tile="5" size="sm" />
              <Tile :tile="14" size="sm" />
              <Tile :tile="31" size="sm" />
              <span class="self-center text-[10px] text-ink-300/50">← 使用当前生效皮肤</span>
            </div>
          </div>

          <p class="mt-3 text-[10px] leading-relaxed text-ink-300/60">
            预览按本皮肤的已上传资源渲染；某张没传时自动回退 CSS 牌面，不会出现空白牌。
          </p>
        </section>
      </div>
    </main>
  </div>
</template>

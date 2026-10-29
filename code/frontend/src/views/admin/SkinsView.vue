<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Check, CircleAlert, Image, Loader2, Palette, Plus, Star, Trash2, X } from 'lucide-vue-next'

import AppHeader from '../../components/AppHeader.vue'
import { useToast } from '../../composables/useToast'
import { useAuthStore } from '../../stores/auth'
import { useSkinsStore } from '../../stores/skins'
import type { SkinInfo } from '../../types'

const router = useRouter()
const toast = useToast()
const auth = useAuthStore()
const skins = useSkinsStore()

const TOTAL_KEYS = 35

const loading = ref(true)
const creating = ref(false)
const createForm = reactive({ skin_name: '', skin_code: '' })
/** 待二次确认的危险操作（05 §5：按钮文案用动词） */
const pending = ref<{ skin: SkinInfo; action: 'disable' | 'delete' } | null>(null)
const acting = ref('')

const familyCode = computed(() => auth.currentFamilyCode || '')
const list = computed(() => skins.skins)

function completeness(skin: SkinInfo): number {
  return Math.min(TOTAL_KEYS, skin.asset_count || 0)
}

function owner(skin: SkinInfo): string {
  return skin.family_code ? auth.currentFamilyName : '全局内置'
}

function isBuiltin(skin: SkinInfo): boolean {
  return !skin.family_code
}

async function load(): Promise<void> {
  if (!familyCode.value) return
  loading.value = true
  try {
    await skins.load(true, true)
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(familyCode, () => void load())

function openCreate(): void {
  createForm.skin_name = `${auth.currentFamilyName}牌面`
  createForm.skin_code = ''
  creating.value = true
}

async function submitCreate(): Promise<void> {
  if (!createForm.skin_name.trim()) {
    toast.warn('请填写皮肤名称')
    return
  }
  if (createForm.skin_code && !/^[a-z][a-z0-9_-]{1,31}$/.test(createForm.skin_code.trim())) {
    toast.warn('皮肤编码需以小写字母开头，只含小写字母、数字、下划线与连字符')
    return
  }
  acting.value = 'create'
  try {
    const created = await skins.createSkin(createForm.skin_name, createForm.skin_code)
    creating.value = false
    toast.success('皮肤已创建，接着上传 35 张牌面')
    router.push({ name: 'skin-edit', params: { skinCode: created.skin_code } })
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    acting.value = ''
  }
}

async function publish(skin: SkinInfo): Promise<void> {
  acting.value = skin.skin_code
  try {
    await skins.patchSkin(skin.skin_code, { status: 'ENABLED' })
    toast.success(`「${skin.skin_name}」已发布，全家人可用`)
  } catch (error) {
    // SKIN_ASSET_INCOMPLETE 的 detail 会列出缺失键
    toast.error((error as Error).message)
  } finally {
    acting.value = ''
  }
}

async function setDefault(skin: SkinInfo): Promise<void> {
  acting.value = skin.skin_code
  try {
    await skins.patchSkin(skin.skin_code, { is_default: true })
    toast.success(`已把「${skin.skin_name}」设为家庭默认皮肤`)
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    acting.value = ''
  }
}

async function confirmDanger(): Promise<void> {
  const target = pending.value
  if (!target) return
  acting.value = target.skin.skin_code
  try {
    if (target.action === 'disable') {
      await skins.patchSkin(target.skin.skin_code, { status: 'DISABLED' })
      toast.success('已停用，正在使用的客户端下次加载时回退')
    } else {
      await skins.removeSkin(target.skin.skin_code)
      toast.success('皮肤已删除')
    }
    pending.value = null
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    acting.value = ''
  }
}
</script>

<template>
  <div class="min-h-screen pb-16">
    <AppHeader />

    <main class="mx-auto max-w-[1400px] px-4 pt-24 sm:px-5">
      <div class="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div class="min-w-0">
          <p class="text-[11px] tracking-[0.32em] text-gold-400/70">SKINS</p>
          <h1 class="mt-1 flex items-center gap-2 text-2xl font-semibold text-cream-100">
            <Palette class="h-5 w-5 text-skin" />
            皮肤管理
          </h1>
          <p class="mt-1 text-sm text-ink-300/80">
            {{ auth.currentFamilyName }} · 34 张牌面 + 牌背共 35 张，齐了才能发布；缺一张只会让那一张回退 CSS。
          </p>
        </div>
        <button
          type="button"
          class="btn-gold flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold"
          @click="openCreate"
        >
          <Plus class="h-4 w-4" />
          新建皮肤
        </button>
      </div>

      <p v-if="loading" class="glass rounded-2xl py-12 text-center text-sm text-ink-300/60">加载皮肤…</p>

      <div v-else class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <article
          v-for="skin in list"
          :key="skin.skin_code"
          class="glass flex flex-col rounded-2xl p-4"
        >
          <div class="flex gap-3">
            <div class="flex h-[74px] w-[56px] shrink-0 items-center justify-center overflow-hidden rounded-lg border border-gold-400/25 bg-cream-100/10">
              <img
                v-if="skin.preview_url || skin.assets['1m']"
                :src="skin.preview_url || skin.assets['1m']"
                :alt="`${skin.skin_name} 预览`"
                class="h-full w-full object-contain"
                loading="lazy"
              />
              <Image v-else class="h-5 w-5 text-ink-300/50" />
            </div>

            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-1.5">
                <span class="truncate text-sm font-medium text-cream-100">{{ skin.skin_name }}</span>
                <span v-if="skin.is_default" class="flex shrink-0 items-center gap-0.5 rounded bg-gold-400/20 px-1.5 py-0.5 text-[10px] text-gold-300">
                  <Star class="h-2.5 w-2.5" />默认
                </span>
              </div>
              <p class="mt-0.5 truncate font-mono text-[11px] text-ink-300/60">{{ skin.skin_code }}</p>
              <div class="mt-1.5 flex flex-wrap items-center gap-1.5 text-[10px]">
                <span class="badge-family">{{ owner(skin) }}</span>
                <span
                  class="rounded-full border px-1.5 py-0.5"
                  :class="
                    skin.status === 'ENABLED'
                      ? 'border-jade-500/40 bg-jade-500/10 text-jade-400'
                      : 'border-cream-100/20 bg-cream-100/5 text-ink-300/70'
                  "
                >
                  {{ skin.status === 'ENABLED' ? '已发布' : '草稿' }}
                </span>
              </div>
            </div>
          </div>

          <!-- 35 张完成度 -->
          <div class="mt-3">
            <div class="mb-1 flex items-center justify-between text-[11px]">
              <span :class="completeness(skin) >= TOTAL_KEYS ? 'text-jade-400' : 'text-ink-300/70'">
                已上传 {{ completeness(skin) }}/{{ TOTAL_KEYS }}
              </span>
              <span v-if="completeness(skin) < TOTAL_KEYS" class="text-amber-400">缺 {{ TOTAL_KEYS - completeness(skin) }} 张</span>
            </div>
            <div class="h-1.5 overflow-hidden rounded-full bg-cream-100/10">
              <div
                class="h-full rounded-full transition-all"
                :class="completeness(skin) >= TOTAL_KEYS ? 'bg-jade-500' : 'bg-gold-400'"
                :style="{ width: `${(completeness(skin) / TOTAL_KEYS) * 100}%` }"
              />
            </div>
          </div>

          <div class="mt-3 flex flex-wrap items-center gap-1.5">
            <button
              type="button"
              class="btn-ghost flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[11px]"
              @click="router.push({ name: 'skin-edit', params: { skinCode: skin.skin_code } })"
            >
              管理资源
            </button>
            <button
              v-if="skin.status !== 'ENABLED'"
              type="button"
              class="btn-gold flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[11px] font-semibold"
              :disabled="acting === skin.skin_code"
              @click="publish(skin)"
            >
              <Loader2 v-if="acting === skin.skin_code" class="h-3 w-3 animate-spin" />
              <Check v-else class="h-3 w-3" />
              设为可用
            </button>
            <button
              v-else-if="!skin.is_default"
              type="button"
              class="btn-ghost flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[11px]"
              :disabled="acting === skin.skin_code"
              @click="setDefault(skin)"
            >
              <Star class="h-3 w-3" />
              设为默认
            </button>
            <button
              v-if="skin.status === 'ENABLED' && !isBuiltin(skin)"
              type="button"
              class="btn-ghost rounded-lg px-2.5 py-1.5 text-[11px]"
              @click="pending = { skin, action: 'disable' }"
            >
              停用
            </button>
            <button
              v-if="!isBuiltin(skin)"
              type="button"
              class="btn-danger-ghost flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[11px]"
              @click="pending = { skin, action: 'delete' }"
            >
              <Trash2 class="h-3 w-3" />
              删除
            </button>
          </div>
        </article>

        <div v-if="!list.length" class="glass flex flex-col items-center gap-2 rounded-2xl py-14">
          <Palette class="h-8 w-8 text-ink-300/40" />
          <p class="text-sm text-ink-300/70">这个家庭还没有自己的皮肤</p>
          <button type="button" class="btn-gold mt-1 rounded-lg px-4 py-2 text-xs font-semibold" @click="openCreate">
            新建第一套
          </button>
        </div>
      </div>

      <!-- 新建 -->
      <div
        v-if="creating"
        class="fixed inset-0 z-[70] flex items-center justify-center bg-felt-950/85 px-4 backdrop-blur-sm"
        @click.self="creating = false"
      >
        <div class="glass w-full max-w-md rounded-2xl p-5">
          <div class="mb-4 flex items-center justify-between">
            <h2 class="text-base font-semibold text-cream-100">新建皮肤</h2>
            <button type="button" class="btn-ghost rounded-lg p-1.5" @click="creating = false">
              <X class="h-4 w-4" />
            </button>
          </div>

          <label class="mb-3 block">
            <span class="mb-1 block text-xs text-ink-300/80">皮肤名称</span>
            <input v-model="createForm.skin_name" class="field" maxlength="64" placeholder="比如 廉家青玉" />
          </label>

          <label class="mb-3 block">
            <span class="mb-1 block text-xs text-ink-300/80">皮肤编码（可留空自动生成）</span>
            <input v-model="createForm.skin_code" class="field font-mono" maxlength="32" placeholder="lianjia-jade" />
          </label>

          <p class="mb-4 rounded-lg border border-cream-100/12 bg-cream-100/[0.03] px-3 py-2 text-[11px] leading-relaxed text-ink-300/70">
            归属：{{ auth.currentFamilyName }}（家庭自有皮肤，全家人可用）。新建后为「草稿」，上传齐 35 张才能发布。
          </p>

          <div class="flex justify-end gap-2">
            <button type="button" class="btn-ghost rounded-lg px-4 py-2 text-sm" @click="creating = false">取消</button>
            <button
              type="button"
              class="btn-gold flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold"
              :disabled="acting === 'create'"
              @click="submitCreate"
            >
              <Loader2 v-if="acting === 'create'" class="h-4 w-4 animate-spin" />
              创建
            </button>
          </div>
        </div>
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
            {{ pending.action === 'disable' ? '停用皮肤' : '删除皮肤' }}
          </p>
          <p class="mt-2 text-xs leading-relaxed text-ink-300/75">
            「{{ pending.skin.skin_name }}」{{
              pending.action === 'disable'
                ? '将不再出现在家人的皮肤列表；已在使用中的客户端会在下次加载时回退默认皮肤。'
                : '会被软删除，正在对局中的牌桌不受影响，但之后无法再选用。'
            }}
          </p>
          <div class="mt-4 flex justify-end gap-2">
            <button type="button" class="btn-ghost rounded-lg px-4 py-2 text-sm" @click="pending = null">取消</button>
            <button
              type="button"
              class="btn-danger-ghost flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-semibold"
              :disabled="acting === pending.skin.skin_code"
              @click="confirmDanger"
            >
              <Loader2 v-if="acting === pending.skin.skin_code" class="h-4 w-4 animate-spin" />
              {{ pending.action === 'disable' ? '停用' : '删除' }}
            </button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

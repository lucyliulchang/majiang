<script setup lang="ts">
import { computed, ref } from 'vue'
import { Plus, Trash2 } from 'lucide-vue-next'

import type { FanItem, RuleConfig } from '../types'

const props = defineProps<{ config: RuleConfig }>()

const groups = computed(() => {
  const set = new Set<string>()
  props.config.fan_table.forEach((item) => {
    if (item.exclusive_group) set.add(item.exclusive_group)
  })
  return Array.from(set)
})

const errorRow = ref<string | null>(null)

function duplicateIds(): Set<string> {
  const seen = new Set<string>()
  const dup = new Set<string>()
  props.config.fan_table.forEach((item) => {
    if (seen.has(item.id)) dup.add(item.id)
    seen.add(item.id)
  })
  return dup
}

const dupIds = computed(() => duplicateIds())

function addRow(): void {
  const base = `custom_${props.config.fan_table.length + 1}`
  const item: FanItem = {
    id: base,
    name: '新番种',
    fan: 1,
    exclusive_group: null,
    stackable: false
  }
  props.config.fan_table.push(item)
}

function removeRow(index: number): void {
  if (props.config.fan_table.length <= 1) {
    errorRow.value = '至少保留一个番种，否则这局永远胡不了'
    return
  }
  props.config.fan_table.splice(index, 1)
  errorRow.value = null
}

function validateRow(item: FanItem, index: number): string {
  if (!item.name.trim()) return '番种名称不能为空'
  if (!/^[a-z][a-z0-9_]{0,31}$/.test(item.id)) return '标识只能用小写字母、数字和下划线，且字母开头'
  if (item.fan < 0 || item.fan > 100) return '番值要在 0-100 之间'
  if (dupIds.value.has(item.id)) return '标识重复了'
  return ''
}

function rowMessage(item: FanItem, index: number): string {
  return validateRow(item, index)
}
</script>

<template>
  <section class="rounded-2xl border border-cream-100/12 bg-felt-950/35">
    <div class="flex items-center justify-between border-b border-cream-100/10 px-4 py-3">
      <div>
        <p class="text-sm font-medium text-gold-300">番种表</p>
        <p class="mt-0.5 text-[11px] text-ink-300/65">
          番种不是写死的，加一行就多一种算法。同互斥组只会取番值最高的那个。
        </p>
      </div>
      <button type="button" class="btn-ghost flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs" @click="addRow">
        <Plus class="h-3.5 w-3.5" />
        添加番种
      </button>
    </div>

    <div class="max-h-[420px] overflow-auto">
      <table class="w-full text-left text-xs">
        <thead class="sticky top-0 z-10 bg-felt-900/95 text-[11px] text-ink-300/70 backdrop-blur">
          <tr>
            <th class="px-3 py-2 font-normal">番种名</th>
            <th class="w-20 px-2 py-2 font-normal">番值</th>
            <th class="w-28 px-2 py-2 font-normal">互斥组</th>
            <th class="w-16 px-2 py-2 font-normal">可叠加</th>
            <th class="w-10 px-2 py-2"></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(item, index) in config.fan_table"
            :key="`${item.id}-${index}`"
            class="border-t border-cream-100/[0.07]"
            :class="rowMessage(item, index) ? 'bg-vermilion-500/[0.08]' : ''"
          >
            <td class="px-3 py-1.5">
              <input v-model="item.name" class="field !py-1 !text-xs" :placeholder="item.id" />
              <p v-if="rowMessage(item, index)" class="mt-1 text-[10px] text-vermilion-400">
                {{ rowMessage(item, index) }}
              </p>
            </td>
            <td class="px-2 py-1.5">
              <input v-model.number="item.fan" class="field !py-1 !text-xs" type="number" min="0" max="100" />
            </td>
            <td class="px-2 py-1.5">
              <input
                v-model="item.exclusive_group"
                class="field !py-1 !text-xs"
                list="fan-groups"
                placeholder="留空=不互斥"
              />
            </td>
            <td class="px-2 py-1.5 text-center">
              <input v-model="item.stackable" type="checkbox" class="h-3.5 w-3.5 accent-[#C9A063]" />
            </td>
            <td class="px-2 py-1.5">
              <button
                type="button"
                class="rounded p-1 text-ink-300/60 transition hover:bg-vermilion-500/15 hover:text-vermilion-400"
                aria-label="删除番种"
                @click="removeRow(index)"
              >
                <Trash2 class="h-3.5 w-3.5" />
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <datalist id="fan-groups">
      <option v-for="group in groups" :key="group" :value="group" />
    </datalist>

    <p v-if="errorRow" class="border-t border-vermilion-500/25 px-4 py-2 text-[11px] text-vermilion-400">
      {{ errorRow }}
    </p>
  </section>
</template>

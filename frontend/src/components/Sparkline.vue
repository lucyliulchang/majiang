<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    values: number[]
    width?: number
    height?: number
    stroke?: string
  }>(),
  { width: 260, height: 64, stroke: '#C9A063' }
)

const points = computed(() => {
  const values = props.values.length ? props.values : [0, 0]
  const min = Math.min(...values, 0)
  const max = Math.max(...values, 0)
  const span = max - min || 1
  const stepX = values.length > 1 ? props.width / (values.length - 1) : props.width
  return values.map((value, index) => {
    const x = index * stepX
    const y = props.height - ((value - min) / span) * (props.height - 8) - 4
    return `${x.toFixed(2)},${y.toFixed(2)}`
  })
})

const areaPath = computed(() => {
  if (!points.value.length) return ''
  return `M0,${props.height} L${points.value.join(' L')} L${props.width},${props.height} Z`
})

const zeroLine = computed(() => {
  const values = props.values.length ? props.values : [0, 0]
  const min = Math.min(...values, 0)
  const max = Math.max(...values, 0)
  const span = max - min || 1
  return props.height - ((0 - min) / span) * (props.height - 8) - 4
})
</script>

<template>
  <svg :viewBox="`0 0 ${width} ${height}`" :width="width" :height="height" class="overflow-visible">
    <defs>
      <linearGradient :id="`spark-${stroke.replace('#', '')}`" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" :stop-color="stroke" stop-opacity="0.35" />
        <stop offset="100%" :stop-color="stroke" stop-opacity="0" />
      </linearGradient>
    </defs>
    <line :x1="0" :y1="zeroLine" :x2="width" :y2="zeroLine" stroke="rgba(168,191,180,0.2)" stroke-dasharray="3 4" stroke-width="1" />
    <path :d="areaPath" :fill="`url(#spark-${stroke.replace('#', '')})`" />
    <polyline
      :points="points.join(' ')"
      fill="none"
      :stroke="stroke"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  </svg>
</template>

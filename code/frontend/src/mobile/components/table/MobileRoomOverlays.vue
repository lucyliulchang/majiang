<script setup lang="ts">
import { Loader2 } from 'lucide-vue-next'

import type { GameFinished } from '../../../stores/game'
import type { JoinRequest } from '../../../types'

/**
 * 牌桌的全屏浮层集合：进桌等待/被拒、房主审批、结束确认、整场结算、房间已关闭。
 * 抽出来只是为了让 MobileRoomView 专心做布局，别再堆六层弹窗。
 */
defineProps<{
  joinPending: boolean
  joinPendingInfo: { room_name?: string; family_name?: string; message?: string } | null
  joinDenied: string
  joinRequests: JoinRequest[]
  endConfirmOpen: boolean
  finished: GameFinished | null
  roomClosed: boolean
}>()

const emit = defineEmits<{
  exit: []
  approve: [loginId: string, allow: boolean]
  cancelEnd: []
  confirmEnd: []
  backToLobby: []
}>()
</script>

<template>
  <!-- 非本家庭成员凭码进桌：等房主在牌桌上确认（S10） -->
  <div v-if="joinPending" class="fixed inset-0 z-[75] flex items-center justify-center bg-felt-950/90 px-5">
    <div class="w-full max-w-sm rounded-2xl border border-gold-400/30 bg-felt-900/95 p-5 text-center">
      <Loader2 class="mx-auto h-6 w-6 animate-spin text-gold-300" />
      <h2 class="mt-3 text-base font-semibold text-cream-100">等房主确认进桌</h2>
      <p class="mt-2 text-[12px] leading-relaxed text-ink-300/80">
        这是「{{ joinPendingInfo?.family_name || '别人家' }}」的牌桌<span v-if="joinPendingInfo?.room_name"
          >「{{ joinPendingInfo.room_name }}」</span
        >。进桌申请已经发给房主，同意后会自动进来；房主不在牌桌上时可能等不到，可以先回大厅稍后再试。
      </p>
      <button
        type="button"
        class="mj-press btn-ghost mt-4 min-h-[44px] w-full rounded-xl text-sm"
        @click="emit('exit')"
      >
        先回大厅
      </button>
    </div>
  </div>

  <!-- 房主没同意 / 房间已关 -->
  <div v-if="joinDenied" class="fixed inset-0 z-[75] flex items-center justify-center bg-felt-950/90 px-5">
    <div class="w-full max-w-sm rounded-2xl border border-vermilion-500/35 bg-felt-900/95 p-5 text-center">
      <h2 class="text-base font-semibold text-cream-100">进不了这桌</h2>
      <p class="mt-2 text-[12px] leading-relaxed text-ink-300/80">{{ joinDenied }}</p>
      <button
        type="button"
        class="mj-press btn-gold mt-4 min-h-[44px] w-full rounded-xl text-sm font-semibold"
        @click="emit('backToLobby')"
      >
        回大厅
      </button>
    </div>
  </div>

  <!-- 房主：外家人进桌申请 -->
  <div v-if="joinRequests.length" class="fixed inset-0 z-[72] flex items-center justify-center bg-felt-950/90 px-5">
    <div class="w-full max-w-sm rounded-2xl border border-gold-400/35 bg-felt-900/95 p-5">
      <h2 class="text-base font-semibold text-cream-100">有人想进这桌</h2>
      <p class="mt-1 text-[11px] leading-relaxed text-ink-300/65">
        这几位不是本家庭成员，凭邀请码过来，得你点头才能进桌。
      </p>
      <div class="mt-3 space-y-2">
        <div
          v-for="req in joinRequests"
          :key="req.login_id"
          class="flex items-center gap-2 rounded-xl border border-cream-100/10 bg-cream-100/[0.03] px-3 py-2"
        >
          <span class="min-w-0 flex-1 truncate text-[13px] text-cream-100">{{ req.display_name }}</span>
          <button
            type="button"
            class="mj-press btn-ghost shrink-0 rounded-lg px-2.5 py-1.5 text-[11px]"
            @click="emit('approve', req.login_id, false)"
          >
            拒绝
          </button>
          <button
            type="button"
            class="mj-press btn-gold shrink-0 rounded-lg px-2.5 py-1.5 text-[11px] font-semibold"
            @click="emit('approve', req.login_id, true)"
          >
            同意进桌
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- 结束牌局二次确认 -->
  <div v-if="endConfirmOpen" class="fixed inset-0 z-[70] flex items-center justify-center bg-felt-950/90 px-5" @click.self="emit('cancelEnd')">
    <div class="w-full max-w-sm rounded-2xl border border-vermilion-500/35 bg-felt-900/95 p-5 text-center">
      <p class="text-[10px] tracking-[0.3em] text-vermilion-400/80">END GAME</p>
      <h2 class="mt-1.5 text-lg font-semibold text-cream-100">结束本场牌局？</h2>
      <p class="mt-2 text-left text-[12px] leading-relaxed text-ink-300/80">
        已经打完的局和积分都会保留；正在进行的这一局直接作废、不计分。全桌会立刻看到本场结算，这桌随即关闭。
      </p>
      <div class="mt-5 flex gap-2">
        <button type="button" class="mj-press btn-ghost flex-1 rounded-xl py-2.5 text-sm" @click="emit('cancelEnd')">
          再打一会
        </button>
        <button
          type="button"
          class="mj-press flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-vermilion-500 py-2.5 text-sm font-semibold text-cream-50"
          @click="emit('confirmEnd')"
        >
          结束牌局
        </button>
      </div>
    </div>
  </div>

  <!-- 整场结束 -->
  <div v-if="finished" class="fixed inset-0 z-[66] flex items-center justify-center bg-felt-950/90 px-5">
    <div class="max-h-[86vh] w-full max-w-md overflow-y-auto rounded-2xl border border-gold-400/30 bg-felt-900/95 p-5 text-center">
      <p class="text-[10px] tracking-[0.3em] text-gold-400/70">GAME OVER</p>
      <h2 class="mt-1.5 text-xl font-semibold text-cream-100">
        {{ finished.aborted ? '本场提前结束' : '这场打完了' }}
      </h2>
      <p v-if="finished.aborted" class="mt-1 text-[11px] text-ink-300/70">
        {{ finished.ended_by_name ? `${finished.ended_by_name} 结束了牌局` : '已结束' }} · 未打完的一局不计分
      </p>
      <div class="mt-4 space-y-1.5">
        <div
          v-for="entry in finished.scores"
          :key="entry.seat"
          class="flex items-center justify-between rounded-lg border border-cream-100/10 bg-cream-100/[0.03] px-3 py-2 text-[13px]"
        >
          <span class="text-cream-100">{{ entry.name }}</span>
          <span class="font-num font-bold" :class="entry.total >= 0 ? 'text-jade-400' : 'text-vermilion-400'">
            {{ entry.total > 0 ? '+' : '' }}{{ entry.total }}
          </span>
        </div>
      </div>
      <button
        type="button"
        class="mj-press btn-gold mt-5 min-h-[46px] w-full rounded-xl text-sm font-semibold"
        @click="emit('backToLobby')"
      >
        回到大厅
      </button>
    </div>
  </div>

  <!-- 房间已被房主关闭，但没赶上结算广播 -->
  <div v-if="roomClosed && !finished" class="fixed inset-0 z-[66] flex items-center justify-center bg-felt-950/90 px-5">
    <div class="w-full max-w-sm rounded-2xl border border-gold-400/25 bg-felt-900/95 p-5 text-center">
      <p class="text-[10px] tracking-[0.3em] text-gold-400/70">ROOM CLOSED</p>
      <h2 class="mt-1.5 text-lg font-semibold text-cream-100">这桌已经结束了</h2>
      <p class="mt-2 text-[12px] leading-relaxed text-ink-300/70">房主结束了本场牌局，回大厅可以再开一桌。</p>
      <button
        type="button"
        class="mj-press btn-gold mt-5 min-h-[46px] w-full rounded-xl text-sm font-semibold"
        @click="emit('backToLobby')"
      >
        回到大厅
      </button>
    </div>
  </div>
</template>

import { reactive } from 'vue'

export type ToastKind = 'info' | 'success' | 'error' | 'warn'

export interface ToastItem {
  id: number
  kind: ToastKind
  text: string
}

const state = reactive<{ items: ToastItem[] }>({ items: [] })
let seq = 0

function remove(id: number): void {
  const index = state.items.findIndex((item) => item.id === id)
  if (index >= 0) state.items.splice(index, 1)
}

function push(kind: ToastKind, text: string, ttl = 2800): number {
  const id = ++seq
  state.items.push({ id, kind, text })
  if (state.items.length > 4) state.items.shift()
  window.setTimeout(() => remove(id), ttl)
  return id
}

export function useToast() {
  return {
    items: state.items,
    push,
    info: (text: string, ttl?: number) => push('info', text, ttl),
    success: (text: string, ttl?: number) => push('success', text, ttl),
    error: (text: string, ttl?: number) => push('error', text, ttl ?? 3600),
    warn: (text: string, ttl?: number) => push('warn', text, ttl),
    remove
  }
}

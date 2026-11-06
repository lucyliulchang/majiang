/**
 * 视口高度锁定（手机版）。
 *
 * 背景：`.mj-dvh` 原先用 `height: 100vh; height: 100dvh` 跟随视口。地址栏收放、
 * 以及 http 页面顶部那条「不安全」提示条的出现/消失，都会触发 resize 并让 dvh
 * 变化 —— 牌桌整页重排一下，看起来就是「闪」。
 *
 * 做法：把可视高度一次性算出来写进 `--mj-vh`，由 CSS 三级链兜底使用
 * （`.mj-dvh { height:100vh; height:100dvh; height:var(--mj-vh, 100vh) }`）。
 * 之后只在这两种情况下重算：
 *   1. 横竖屏切换（orientationchange / screen.orientation.change）；
 *   2. 高度变化超过 120px（例如旋转后首次布局、浏览器工具栏彻底展开/收起）。
 * 小于阈值的变化直接忽略，地址栏与提示条的小幅收放不再引起整页抖动。
 *
 * 约束：
 * - 必须在 `createApp().mount()` 之前调用，首帧就拿到稳定高度，避免先按 100vh 排版再跳一次。
 * - 输入框聚焦期间跳过重算（软键盘会大幅压缩 visualViewport.height，跟随会把整页压扁）。
 * - 全程 try/catch 静默降级；没有 visualViewport 的内核退回 innerHeight。
 */

const VAR_NAME = '--mj-vh'
/** 小于这个高度差视为「地址栏/提示条收放」的噪声，不重算 */
const RESIZE_THRESHOLD = 120
/** resize 连续触发时的防抖窗口 */
const DEBOUNCE_MS = 250

interface VisualViewportLike {
  height: number
  addEventListener?: (type: 'resize', listener: () => void) => void
  removeEventListener?: (type: 'resize', listener: () => void) => void
}

interface ScreenOrientationLike {
  addEventListener?: (type: 'change', listener: () => void) => void
  removeEventListener?: (type: 'change', listener: () => void) => void
}

function isEditing(): boolean {
  const el = document.activeElement as HTMLElement | null
  if (!el) return false
  if (el.isContentEditable) return true
  const tag = el.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
}

/** 当前可视高度：优先 visualViewport（更贴近真实可见区域），取整剔除亚像素抖动 */
function readViewportHeight(): number {
  const vv = (window as unknown as { visualViewport?: VisualViewportLike }).visualViewport
  const raw = vv && typeof vv.height === 'number' && vv.height > 0 ? vv.height : window.innerHeight
  return raw > 0 ? Math.round(raw) : 0
}

/**
 * 安装视口高度锁定，返回卸载函数（切页/热更新时调用；不会移除已写入的变量）。
 */
export function installViewportHeight(): () => void {
  if (typeof window === 'undefined' || typeof document === 'undefined') return () => undefined

  const root = document.documentElement
  const vv = (window as unknown as { visualViewport?: VisualViewportLike }).visualViewport
  const orientation = (screen as unknown as { orientation?: ScreenOrientationLike }).orientation

  let current = 0
  let timer: ReturnType<typeof setTimeout> | null = null

  function apply(force: boolean): void {
    // 软键盘弹起时 visualViewport 会明显变矮，此时重算会把牌桌压到键盘高度
    if (!force && isEditing()) return

    let next = 0
    try {
      next = readViewportHeight()
    } catch {
      return
    }
    if (!next) return
    if (!force && current && Math.abs(next - current) < RESIZE_THRESHOLD) return

    current = next
    try {
      root.style.setProperty(VAR_NAME, `${next}px`)
    } catch {
      /* 变量写入失败时 CSS 会落到 100dvh / 100vh，不影响可用性 */
    }
  }

  function schedule(): void {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      apply(false)
    }, DEBOUNCE_MS)
  }

  function onOrientationChange(): void {
    // 旋转后布局尺寸会有一两帧才稳定，等一拍再强制重算
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      apply(true)
    }, DEBOUNCE_MS)
  }

  apply(true)

  try {
    window.addEventListener('resize', schedule)
    window.addEventListener('orientationchange', onOrientationChange)
    vv?.addEventListener?.('resize', schedule)
    orientation?.addEventListener?.('change', onOrientationChange)
  } catch {
    /* 监听挂不上就只用首帧写死的值 */
  }

  return () => {
    if (timer) clearTimeout(timer)
    try {
      window.removeEventListener('resize', schedule)
      window.removeEventListener('orientationchange', onOrientationChange)
      vv?.removeEventListener?.('resize', schedule)
      orientation?.removeEventListener?.('change', onOrientationChange)
    } catch {
      /* ignore */
    }
  }
}

import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

/** 浏览器是否支持「进入全屏 + 锁定横屏」（iOS Safari 两者都不支持，只能引导手动横屏） */
interface OrientationCapable {
  lock?: (orientation: string) => Promise<void>
  unlock?: () => void
}

interface FullscreenCapable {
  requestFullscreen?: () => Promise<void>
  webkitRequestFullscreen?: () => Promise<void>
  exitFullscreen?: () => Promise<void>
  webkitExitFullscreen?: () => Promise<void>
}

/**
 * 横竖屏状态与「进全屏 + 锁横屏」的尝试。
 *
 * 牌桌只在横屏下工作：竖屏时给一张遮罩，按一下按钮尽力切到横屏全屏；
 * 任何一步失败（iOS、非全屏域名、用户拒绝）都静默降级为「请手动把手机横过来」。
 */
export function useOrientation() {
  const landscape = ref(true)
  const fullscreen = ref(false)

  let mql: MediaQueryList | null = null

  const isTouch = typeof window !== 'undefined' && ('ontouchstart' in window || navigator.maxTouchPoints > 0)
  /** 是否支持方向锁定：iOS Safari 没有 screen.orientation.lock */
  const canLock = computed(() => Boolean((screen as unknown as { orientation?: OrientationCapable }).orientation?.lock))

  function sync(): void {
    landscape.value = mql ? mql.matches : window.innerWidth >= window.innerHeight
    fullscreen.value = Boolean(document.fullscreenElement)
  }

  onMounted(() => {
    mql = window.matchMedia('(orientation: landscape)')
    sync()
    mql.addEventListener('change', sync)
    window.addEventListener('resize', sync)
    window.addEventListener('orientationchange', sync)
    document.addEventListener('fullscreenchange', sync)
  })

  onBeforeUnmount(() => {
    mql?.removeEventListener('change', sync)
    window.removeEventListener('resize', sync)
    window.removeEventListener('orientationchange', sync)
    document.removeEventListener('fullscreenchange', sync)
  })

  /** 尽力切横屏：先全屏（部分浏览器只有全屏态才允许锁方向），再锁 landscape */
  function requestLandscape(): Promise<boolean> {
    const element = document.documentElement as FullscreenCapable
    const orientation = (screen as unknown as { orientation?: OrientationCapable }).orientation
    const steps: Promise<unknown>[] = []

    if (!document.fullscreenElement) {
      if (element.requestFullscreen) {
        steps.push(element.requestFullscreen().catch(() => undefined))
      } else if (element.webkitRequestFullscreen) {
        steps.push(Promise.resolve(element.webkitRequestFullscreen()).catch(() => undefined))
      }
    }
    if (orientation?.lock) {
      steps.push(orientation.lock('landscape').catch(() => undefined))
    }

    return Promise.all(steps).then(() => {
      sync()
      return landscape.value
    })
  }

  /** 退出全屏（离开牌桌时调用，避免整个 App 卡在全屏） */
  function exitFullscreen(): void {
    const element = document as unknown as FullscreenCapable
    if (!document.fullscreenElement) return
    Promise.resolve(element.exitFullscreen ? element.exitFullscreen() : element.webkitExitFullscreen?.()).catch(
      () => undefined
    )
  }

  return { landscape, fullscreen, isTouch, canLock, requestLandscape, exitFullscreen }
}

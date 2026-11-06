import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

/**
 * 同一套源码，两套入口：
 * - 默认构建 → index.html + base=/majiangapp/ → dist（PC 版，行为保持不变）
 * - `--mode mjmobile` → mobile.html + base=/mjmobile/ → dist-mobile（手机版）
 *
 * dev 一律 base='/'，否则 vite 的静态代理会和资源路径打架；手机端本地开发用
 * `npm run dev:mobile` 打开 /mobile.html 即可（API/WS 仍走下面的 /api、/ws 代理）。
 */
export default defineConfig(({ command, mode }) => {
  const mobile = mode === 'mjmobile'
  return {
    plugins: [vue()],
    base: command === 'build' ? (mobile ? '/mjmobile/' : '/majiangapp/') : '/',
    server: {
      host: '0.0.0.0',
      port: 5173,
      allowedHosts: true,
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true
        },
        '/ws': {
          target: 'ws://127.0.0.1:8000',
          ws: true,
          changeOrigin: true
        },
        // 前端直访图片（皮肤等）：本地由后端托管，URL 与生产 /majiangapp/ 一致
        '/majiangapp': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true
        }
      }
    },
    build: {
      outDir: mobile ? 'dist-mobile' : 'dist',
      chunkSizeWarningLimit: 900,
      /* 手机版兼容基线：Chrome 87（2020）。曾经降到 chrome78 是为了照顾家里那台
       * Android 12 华为机的预装 Chrome，v1.1.6 起不再兼容 —— 那台机的浏览器早已可升级，
       * 且 chrome87 与 PC 默认线一致，`?.` / `??` 均原生支持，产物不必再降级成三元。
       * 注意：target 只管 JS 语法，CSS 的 `dvh` 是 Chrome 108+，mobile.css 里
       * `100vh → 100dvh → var(--mj-vh, 100vh)` 三级回退必须保留，别顺手删。 */
      target: mobile ? ['chrome87'] : undefined,
      // 显式指定单入口（相对 root 的路径）：避免两个 HTML 在同一份产物里互相污染。
      // 产物按源文件名落地：PC → dist/index.html，手机 → dist-mobile/mobile.html
      // （所以 nginx 的 /mjmobile/ 要写 `index mobile.html;` 并把 SPA 回退也指向它）
      rollupOptions: {
        input: mobile ? 'mobile.html' : 'index.html'
      }
    }
  }
})

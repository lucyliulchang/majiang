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
      /* 手机版必须显式降到 chrome78：家里那台华为 Android 12 上的预装 Chrome
       * 还停在 78（2019），它不认 `?.` 可选链与 `??` 空值合并 —— 一旦产物里出现，
       * 整个模块直接 SyntaxError、Vue 挂不上，页面就只剩一张 CSS 背景。
       * esbuild 按这个 target 会把新语法降级成三元/var 写法。
       * PC 版维持 vite 默认（chrome87），不为此牺牲现代特性。 */
      target: mobile ? ['chrome78', 'safari13', 'firefox70', 'edge79'] : undefined,
      // 显式指定单入口（相对 root 的路径）：避免两个 HTML 在同一份产物里互相污染。
      // 产物按源文件名落地：PC → dist/index.html，手机 → dist-mobile/mobile.html
      // （所以 nginx 的 /mjmobile/ 要写 `index mobile.html;` 并把 SPA 回退也指向它）
      rollupOptions: {
        input: mobile ? 'mobile.html' : 'index.html'
      }
    }
  }
})

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ command }) => ({
  plugins: [vue()],
  // 生产部署在 /majiangapp/ 下（06 §8.2）：构建产物必须带前缀；dev 保持 '/'，
  // 否则 vite 的 /majiangapp 静态代理会和资源路径打架。
  base: command === 'build' ? '/majiangapp/' : '/',
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
    outDir: 'dist',
    chunkSizeWarningLimit: 900
  }
}))

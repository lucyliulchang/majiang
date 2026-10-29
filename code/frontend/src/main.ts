import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { bindAudioGestures } from './audio/audioManager'
import { initSoundPrefs } from './audio/soundPrefs'
import './styles/index.css'

// 音效：先读 localStorage（首屏即时生效），再在登录后由服务端偏好覆盖
initSoundPrefs()
// 首次用户手势解锁 AudioContext（08 §4.3），未解锁前不播放、不打断
bindAudioGestures()

createApp(App).use(createPinia()).use(router).mount('#app')

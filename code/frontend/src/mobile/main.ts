import { createApp } from 'vue'
import { createPinia } from 'pinia'

import MobileApp from './App.vue'
import router from './router'
import { bindAudioGestures } from '../audio/audioManager'
import { initSoundPrefs } from '../audio/soundPrefs'
// 主题（色板、按钮、绒面面板）与 PC 共用一份；mobile.css 只做移动端增量覆盖
import '../styles/index.css'
import './styles/mobile.css'

// 音效：先读 localStorage（首屏即时生效），再在登录后由服务端偏好覆盖
initSoundPrefs()
// 首次用户手势解锁 AudioContext（08 §4.3），未解锁前不播放、不打断
bindAudioGestures()

createApp(MobileApp).use(createPinia()).use(router).mount('#app')

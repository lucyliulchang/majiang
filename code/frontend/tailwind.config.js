/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        felt: {
          950: '#071A12',
          900: '#0A2419',
          800: '#0F3D2E',
          700: '#123A2B',
          600: '#1A5C46',
          500: '#227357'
        },
        gold: {
          50: '#FBF6EA',
          100: '#F0E4C8',
          300: '#DCC08A',
          400: '#C9A063',
          500: '#B8873F',
          600: '#96682C'
        },
        cream: {
          50: '#FFFDF7',
          100: '#F7F3E8',
          200: '#EFE7D3',
          300: '#E0D4B8'
        },
        ink: {
          900: '#141C18',
          800: '#1F2A24',
          600: '#3C4A42',
          400: '#6B7A72',
          300: '#A8BFB4'
        },
        jade: {
          500: '#2E7D5B',
          400: '#3B9E72'
        },
        vermilion: {
          500: '#C0392B',
          400: '#D9534F'
        },
        amber: {
          400: '#E8A33D'
        },
        // 05 §2.1 新增：家庭徽标与皮肤入口
        family: '#6C8EBF',
        skin: '#9B7EBD'
      },
      fontFamily: {
        sans: ['"Noto Sans SC"', '"PingFang SC"', '"Microsoft YaHei"', 'system-ui', 'sans-serif'],
        num: ['"Noto Serif SC"', 'Georgia', 'serif']
      },
      boxShadow: {
        table: '0 40px 90px -30px rgba(0, 0, 0, 0.75)',
        tile: '0 2px 0 rgba(0,0,0,0.18), 0 6px 12px -6px rgba(0,0,0,0.45)',
        gold: '0 0 0 1px rgba(201,160,99,0.45), 0 12px 30px -12px rgba(201,160,99,0.35)'
      },
      keyframes: {
        breathe: {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(201,160,99,0.55)' },
          '50%': { boxShadow: '0 0 0 8px rgba(201,160,99,0)' }
        },
        floaty: {
          '0%, 100%': { transform: 'translateY(0) rotate(var(--tilt, 0deg))' },
          '50%': { transform: 'translateY(-14px) rotate(var(--tilt, 0deg))' }
        },
        riseIn: {
          from: { opacity: '0', transform: 'translateY(14px) scale(0.97)' },
          to: { opacity: '1', transform: 'translateY(0) scale(1)' }
        },
        slideUp: {
          from: { opacity: '0', transform: 'translateY(24px)' },
          to: { opacity: '1', transform: 'translateY(0)' }
        },
        shake: {
          '0%, 100%': { transform: 'translateX(0)' },
          '25%': { transform: 'translateX(-6px)' },
          '75%': { transform: 'translateX(6px)' }
        },
        shimmer: {
          '0%': { backgroundPosition: '0% 50%' },
          '100%': { backgroundPosition: '200% 50%' }
        }
      },
      animation: {
        breathe: 'breathe 2.4s ease-in-out infinite',
        floaty: 'floaty 7s ease-in-out infinite',
        riseIn: 'riseIn 0.28s ease-out both',
        slideUp: 'slideUp 0.24s ease-out both',
        shake: 'shake 0.3s ease-in-out',
        shimmer: 'shimmer 6s linear infinite'
      }
    }
  },
  plugins: [require('tailwindcss-animate')]
}

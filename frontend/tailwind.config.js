/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      screens: { pane: '900px' },
      colors: {
        // 主色：暖金（主按钮 / 高亮文字 / 进度元素）
        gold: { DEFAULT: '#D4AF37', deep: '#C9A227', soft: '#F3E9C8' },
        // 文字层级：标题 #333 / 正文 #666 / 弱化 #999
        ink: { heading: '#333333', body: '#666666', faint: '#999999' },
        line: '#E5E5E5',
        surface: '#FFFFFF',
        warm: '#FFF8E8', // 角落暖米光
        lilac: '#F5EEFF', // 角落浅紫光
      },
      fontFamily: {
        sans: [
          'Inter',
          '"Source Han Sans SC"',
          '"思源黑体"',
          '"PingFang SC"',
          '"Microsoft YaHei"',
          'sans-serif',
        ],
        mono: ['ui-monospace', '"JetBrains Mono"', '"Fira Code"', 'monospace'],
      },
      borderRadius: { btn: '8px', card: '12px', 'card-lg': '16px' },
      boxShadow: {
        card: '0 1px 2px rgba(0,0,0,0.03)',
        'card-hover': '0 4px 16px rgba(0,0,0,0.06)',
        'gold-glow': '0 2px 10px rgba(212,175,55,0.28)',
      },
      backgroundImage: {
        // 白底 + 双角落极淡径向渐变（左下浅紫 / 右上暖米）
        'app-canvas':
          'radial-gradient(ellipse 55% 50% at 12% 88%, #F5EEFF 0%, transparent 60%),' +
          'radial-gradient(ellipse 55% 50% at 88% 12%, #FFF8E8 0%, transparent 60%)',
      },
      keyframes: {
        fadeUp: {
          from: { opacity: '0', transform: 'translateY(6px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        spin: { to: { transform: 'rotate(360deg)' } },
        pulseRec: {
          '0%,100%': { boxShadow: '0 0 0 0 rgba(242,85,85,0.45)' },
          '50%': { boxShadow: '0 0 0 5px rgba(242,85,85,0)' },
        },
      },
      animation: {
        fadeUp: 'fadeUp 0.20s ease forwards',
        spin: 'spin 0.7s linear infinite',
        pulseRec: 'pulseRec 1.2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};

import type { Config } from 'tailwindcss'
import { tailwindColors } from './src/design/tokens'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    // Replace (not extend) colours so only design tokens exist.
    colors: {
      transparent: 'transparent',
      current: 'currentColor',
      white: '#FFFFFF',
      ...tailwindColors,
    },
    extend: {
      fontFamily: {
        sans: ['"Geist Variable"', 'Geist', 'system-ui', 'sans-serif'],
        mono: ['"Geist Mono Variable"', '"Geist Mono"', 'ui-monospace', 'monospace'],
        serif: ['"Instrument Serif"', 'Georgia', 'serif'],
      },
      // Pixel-named type scale taken straight from the design.
      fontSize: {
        11: '11px',
        12: '12px',
        13: '13px',
        14: '14px',
        15: '15px',
        16: '16px',
        17: '17px',
        22: '22px',
        24: '24px',
        26: '26px',
        28: '28px',
        30: '30px',
        32: '32px',
        34: '34px',
        36: '36px',
        40: '40px',
        56: '56px',
        64: '64px',
        96: '96px',
        136: '136px',
      },
      letterSpacing: {
        caps: '0.08em',
      },
      maxWidth: {
        page: '1360px',
      },
      minHeight: {
        target: '44px',
      },
      minWidth: {
        target: '44px',
      },
    },
  },
  plugins: [],
} satisfies Config

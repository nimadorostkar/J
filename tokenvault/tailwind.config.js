/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        space: {
          900: '#060A14',
          800: '#0A0E1A',
          700: '#0D1326',
          600: '#161D2E',
          500: '#1F2937',
          400: '#2A3550',
        },
        teal: {
          300: '#5EEAD4',
          400: '#2DD4BF',
          500: '#14B8A6',
          600: '#0D9488',
        },
        gold: {
          300: '#FCD34D',
          400: '#FBBF24',
          500: '#F59E0B',
          600: '#D97706',
        },
      },
      fontFamily: {
        sans: ['Outfit', 'system-ui', 'sans-serif'],
        mono: ['Space Mono', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        'teal-glow': '0 0 24px rgba(45, 212, 191, 0.35), 0 0 4px rgba(45, 212, 191, 0.5)',
        'gold-glow': '0 0 24px rgba(251, 191, 36, 0.35), 0 0 4px rgba(251, 191, 36, 0.5)',
        'card': '0 8px 32px rgba(0, 0, 0, 0.35)',
      },
      animation: {
        'blink': 'blink 1s steps(2, start) infinite',
        'drift': 'drift 60s linear infinite',
        'drift-slow': 'drift 90s linear infinite',
        'pulse-ring': 'pulseRing 2.4s ease-out infinite',
        'spin-slow': 'spin 60s linear infinite',
        'spin-slower': 'spin 90s linear infinite reverse',
        'shimmer': 'shimmer 1.6s linear infinite',
      },
      keyframes: {
        blink: { '50%': { opacity: '0.25' } },
        drift: { from: { transform: 'translateY(0)' }, to: { transform: 'translateY(-2000px)' } },
        pulseRing: {
          '0%': { boxShadow: '0 0 0 0 rgba(45, 212, 191, 0.6)' },
          '70%': { boxShadow: '0 0 0 18px rgba(45, 212, 191, 0)' },
          '100%': { boxShadow: '0 0 0 0 rgba(45, 212, 191, 0)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-400px 0' },
          '100%': { backgroundPosition: '400px 0' },
        },
      },
    },
  },
  plugins: [],
}

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Bebas Neue"', 'Impact', 'sans-serif'],
        mono: ['"Courier Prime"', 'Courier', 'monospace'],
        sans: ['"Courier Prime"', 'Courier', 'monospace'],
      },
      colors: {
        bg: {
          base: '#F2EDE3',
          surface: '#EAE3D1',
          elevated: '#DDD5BF',
          border: '#1A1A1A',
        },
        accent: {
          green: '#1A1A1A',
          'green-dim': '#3A3A3A',
          amber: '#8C6500',
          red: '#CC0018',
          blue: '#1040C8',
          purple: '#6B18CC',
        },
        text: {
          primary: '#1A1A1A',
          secondary: '#2E2E2E',
          muted: '#7A7060',
        },
        marker: {
          red: '#CC0018',
          yellow: '#D4860A',
          blue: '#1040C8',
          purple: '#6B18CC',
        },
        // Legacy semantic palette
        compliance: '#ef4444',
        coach: '#3b82f6',
        clarity: '#eab308',
        persona: '#a855f7',
      },
      borderRadius: {
        sm: '0px',
        md: '0px',
        lg: '0px',
      },
      boxShadow: {
        glow: '3px 3px 0px #1A1A1A',
        'glow-amber': '3px 3px 0px #8C6500',
        panel: '2px 2px 0px #1A1A1A',
        brutal: '3px 3px 0px #1A1A1A',
        'brutal-sm': '2px 2px 0px #1A1A1A',
        'brutal-lg': '5px 5px 0px #1A1A1A',
        'brutal-red': '3px 3px 0px #CC0018',
        'brutal-yellow': '3px 3px 0px #8C6500',
      },
      keyframes: {
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(10px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        pulse: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.3' },
        },
        scan: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(400%)' },
        },
        blink: {
          '0%, 49%': { opacity: '1' },
          '50%, 100%': { opacity: '0' },
        },
        marquee: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(400%)' },
        },
        ticker: {
          '0%': { transform: 'translateX(0)' },
          '100%': { transform: 'translateX(-50%)' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.3s cubic-bezier(0.34, 1.3, 0.64, 1) both',
        'fade-in': 'fade-in 0.2s ease-out both',
        pulse: 'pulse 1.5s ease-in-out infinite',
        scan: 'scan 1.8s ease-in-out infinite',
        blink: 'blink 1s step-end infinite',
        marquee: 'marquee 1.8s linear infinite',
        ticker: 'ticker 32s linear infinite',
      },
    },
  },
  plugins: [],
};

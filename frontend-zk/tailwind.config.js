/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    fontFamily: {
      mono: ['"JetBrains Mono"', '"SF Mono"', '"Fira Code"', 'monospace'],
      sans: ['system-ui', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
    },
    extend: {
      colors: {
        zk: {
          bg: '#f5f5f0',
          surface: '#ffffff',
          border: '#0a0a0a',
          text: '#0a0a0a',
          muted: '#5a5a5a',
          dim: '#8a8a8a',
          accent: '#ff3b00',
          link: '#0038ff',
          danger: '#cc0000',
          success: '#006600',
          warn: '#cc7700',
        },
      },
      borderWidth: {
        '3': '3px',
      },
      fontSize: {
        'display': ['4.5rem', { lineHeight: '0.9', letterSpacing: '-0.04em' }],
        'headline': ['2rem', { lineHeight: '1.1', letterSpacing: '-0.02em' }],
        'subhead': ['1.125rem', { lineHeight: '1.3', letterSpacing: '-0.01em' }],
        'label': ['0.6875rem', { lineHeight: '1.4', letterSpacing: '0.08em' }],
      },
    },
  },
  plugins: [],
};

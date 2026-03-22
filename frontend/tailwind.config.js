/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        felt: {
          400: "#2d8f55",
          500: "#247a48",
          600: "#1e6b3e",
          700: "#1a5c36",
          800: "#144a2a",
          900: "#0f3820",
        },
        gold: {
          300: "#fcd34d",
          400: "#f6c344",
          500: "#d4a843",
          600: "#b8942e",
        },
        table: {
          rim: "#2a1f10",
          wood: "#3d2b14",
          accent: "#5c3d1a",
        },
        ndai: {
          50: "#f0f4ff",
          100: "#dbe4ff",
          200: "#bac8ff",
          300: "#91a7ff",
          400: "#748ffc",
          500: "#5c7cfa",
          600: "#4c6ef5",
          700: "#4263eb",
          800: "#3b5bdb",
          900: "#364fc7",
        },
        void: {
          50: "#e8e8f0",
          100: "#c4c4d8",
          200: "#9d9dbd",
          300: "#7575a2",
          400: "#56568e",
          500: "#3a3a7a",
          600: "#2d2d6b",
          700: "#1f1f57",
          800: "#151544",
          900: "#0c0c2e",
          950: "#06061a",
        },
      },
    },
  },
  plugins: [],
};

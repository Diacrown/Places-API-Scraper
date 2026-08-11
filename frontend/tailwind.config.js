/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0B0E12",
        surface: "#12171D",
        surface2: "#1A2029",
        border: "#262E38",
        ink: "#E7EAEE",
        "ink-dim": "#8B96A3",
        amber: "#F2A93B",
        teal: "#3ADBC3",
        red: "#F1615F",
        blue: "#5B9DF0",
      },
      fontFamily: {
        sans: ["'IBM Plex Sans'", "system-ui", "sans-serif"],
        mono: ["'IBM Plex Mono'", "ui-monospace", "monospace"],
      },
      backgroundImage: {
        "dot-grid":
          "radial-gradient(circle, #262E38 1px, transparent 1px)",
      },
      backgroundSize: {
        "dot-grid": "22px 22px",
      },
    },
  },
  plugins: [],
};

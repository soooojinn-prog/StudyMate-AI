import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        "bg-deep": "var(--bg-deep)",
        panel: "var(--panel)",
        "panel-line": "var(--panel-line)",
        ink: "var(--ink)",
        "ink-mid": "var(--ink-mid)",
        "ink-soft": "var(--ink-soft)",
        cyan: "var(--cyan)",
        "cyan-deep": "var(--cyan-deep)",
        amber: "var(--amber)",
        magenta: "var(--magenta)",
        danger: "var(--danger)",
      },
      fontFamily: {
        display: ["Fraunces", "Times New Roman", "serif"],
        body: ['"Pretendard Variable"', "Pretendard", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      backgroundImage: {
        "blueprint-grid":
          "linear-gradient(var(--grid) 1px, transparent 1px), linear-gradient(90deg, var(--grid) 1px, transparent 1px)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;

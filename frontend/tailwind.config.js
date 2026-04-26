/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#f4efe7",
        ink: "#1f2937",
        coral: "#d97757",
        moss: "#4b6355",
        brass: "#c59a35",
        cream: "#fffaf3",
        slate: "#6b7280",
      },
      fontFamily: {
        display: ["Georgia", "Cambria", "Times New Roman", "serif"],
        body: ["Trebuchet MS", "Verdana", "sans-serif"],
      },
      boxShadow: {
        card: "0 20px 50px rgba(31, 41, 55, 0.12)",
      },
      keyframes: {
        floatIn: {
          "0%": { opacity: "0", transform: "translateY(16px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        floatIn: "floatIn 500ms ease-out both",
      },
    },
  },
  plugins: [],
};

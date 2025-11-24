/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "sky-500": "#0ea5e9",
        "blue-600": "#2563eb",
        "purple-600": "#9333ea",
      },
    },
  },
  plugins: [],
};

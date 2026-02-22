/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: {
          900: "#0d1b2a",
          800: "#1e3a5f",
          700: "#2a4e7f",
        },
        gold: "#f5a623",
      },
    },
  },
  plugins: [],
};

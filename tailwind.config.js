/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html", // adjust path to your HTML/Jinja files
    "./static/**/*.js",
    "./*.html",
  ],

  corePlugins: {
    preflight: false, // This disables Tailwind's global base/reset styles
  },
  theme: {
    extend: {},
  },
  plugins: [],
};

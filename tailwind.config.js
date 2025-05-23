/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./**/*.html"],
  safelist: [
    "placeholder-[var(--goglobe-body-color)]",
    "bg-[var(--goglobe-input-color)]",
    "focus:bg-[var(--goglobe-site-bg-color)]",
    // add other dynamic classes here
  ],
  // corePlugins: {
  //   preflight: false, // This disables Tailwind's global base/reset styles
  // },
  theme: {
    extend: {},
  },
  plugins: [],
};

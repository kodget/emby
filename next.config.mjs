/** @type {import('next').NextConfig} */
const nextConfig = {
  // Browser fixtures must not compete with an open development server for its build lock.
  distDir: process.env.EMBY_BROWSER_TESTS === "uploads" ? ".next/upload-browser-tests"
    : process.env.EMBY_BROWSER_TESTS === "1" ? ".next/browser-tests" : ".next",
  typescript: {
    ignoreBuildErrors: false,
  },
  images: {
    formats: ["image/avif", "image/webp"],
  },
  experimental: {
    optimizePackageImports: [
      "@fortawesome/react-fontawesome",
      "@fortawesome/free-solid-svg-icons",
      "@fortawesome/free-regular-svg-icons",
      "lucide-react",
      "framer-motion",
      "recharts",
      "@radix-ui/react-accordion",
      "@radix-ui/react-alert-dialog",
      "@radix-ui/react-dialog",
      "@radix-ui/react-dropdown-menu",
      "@radix-ui/react-select",
      "@radix-ui/react-tabs",
      "@radix-ui/react-tooltip",
    ],
  },
};

export default nextConfig;

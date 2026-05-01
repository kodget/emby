/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    formats: ["image/avif", "image/webp"],
  },
  experimental: {
    optimizePackageImports: ["@fortawesome/react-fontawesome", "lucide-react", "framer-motion"],
  },
}

export default nextConfig

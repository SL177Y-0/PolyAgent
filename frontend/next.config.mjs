/** @type {import('next').NextConfig} */
const nextConfig = {
  // TypeScript errors should be checked during development
  typescript: {
    ignoreBuildErrors: false,
  },
  images: {
    unoptimized: true,
  },
}

export default nextConfig

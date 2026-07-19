// Server-only: canonical public origin of this deployment, for SEO metadata
// (canonical/OG URLs, robots, sitemap). Read from the container env at request
// time — callers must opt their route into dynamic rendering, mirroring the
// /env.js runtime-config approach (12-factor: never bake a domain into the
// image at build time; self-hosted deployments set their own SITE_URL).
export function getSiteUrl(): URL {
  return new URL(process.env.SITE_URL ?? "http://localhost:3000")
}

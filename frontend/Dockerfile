FROM node:25-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:25-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
# KONG_URL is read by next.config.ts at build time for server-side rewrites.
# Docker Compose passes http://kong:8000; local non-Docker dev uses the default.
ARG KONG_URL=http://localhost:8000
ENV KONG_URL=$KONG_URL
RUN npm run build

FROM node:25-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# The runtime executes `node server.js` against the Next.js standalone bundle and
# never installs anything, so the package managers shipped in the base image are
# dead weight — and the only source of CVEs in this image (CVE-2026-59873 came
# from npm's bundled node-tar, not from our dependencies; even node 24's npm
# still bundles tar 7.5.15 < 7.5.19). Deleting them removes the vulnerable code
# instead of suppressing the finding, and drops a package manager that can fetch
# and execute arbitrary code from a production runtime.
RUN rm -rf /usr/local/lib/node_modules/npm \
           /usr/local/lib/node_modules/corepack \
           /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack \
           /usr/local/bin/yarn /usr/local/bin/yarnpkg /opt/yarn-v*

COPY --from=builder --chown=node:node /app/public ./public
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static

# Git revision baked in by CD (build-arg; also stamped as OCI label
# org.opencontainers.image.revision). Used by deploy.sh post-deploy verification.
ARG GIT_SHA=dev
ENV GIT_SHA=$GIT_SHA

USER node
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"
CMD ["node", "server.js"]

FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
# KONG_URL is read by next.config.ts at build time for server-side rewrites.
# Docker Compose passes http://kong:8000; local non-Docker dev uses the default.
ARG KONG_URL=http://localhost:8000
ENV KONG_URL=$KONG_URL
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

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

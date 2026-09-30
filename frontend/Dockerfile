FROM node:22-slim AS builder
WORKDIR /app
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

FROM node:22-slim AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000 SERVER_API_URL=http://backend:8000
RUN useradd --create-home --uid 10001 repopilot
COPY --from=builder --chown=repopilot:repopilot /app/.next/standalone ./
COPY --from=builder --chown=repopilot:repopilot /app/.next/static ./.next/static
USER repopilot
EXPOSE 3000
CMD ["node", "server.js"]

FROM node:20-alpine
RUN corepack enable && corepack prepare pnpm@9 --activate
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile || pnpm install
COPY . .
EXPOSE 3000
CMD ["pnpm", "exec", "next", "dev", "--hostname", "0.0.0.0", "--port", "3000"]

FROM node:20-alpine
RUN corepack enable && corepack prepare pnpm@9 --activate
WORKDIR /app
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile || pnpm install
COPY . .
EXPOSE 3001
CMD ["pnpm", "exec", "tsx", "src/index.ts"]

# Build stage
FROM node:22-alpine AS builder

WORKDIR /app
ENV CI=true
COPY package.json pnpm-lock.yaml ./

# Force pnpm to skip the interactive native module script blocks:
RUN corepack enable && corepack pnpm config set ignore-scripts true && corepack pnpm install --no-frozen-lockfile


COPY . .
RUN corepack pnpm build

# Production stage
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 3000
#CMD ["corepack", "pnpm", "preview", "--port", "3000", "--host", "0.0.0.0"]

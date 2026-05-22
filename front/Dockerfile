# Build stage
FROM node:22-alpine AS builder

WORKDIR /app
ENV CI=true
COPY package.json pnpm-lock.yaml ./
# Habilitar corepack separado para cache de esta capa
RUN corepack enable && corepack pnpm config set ignore-scripts true

# Copiar el resto del código fuente
COPY . .
# Instalar (--no-frozen-lockfile por si el lockfile está desactualizado) y compilar
RUN corepack pnpm install --no-frozen-lockfile && corepack pnpm build

# Production stage
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80

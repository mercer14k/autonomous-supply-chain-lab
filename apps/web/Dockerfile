FROM node:22-alpine AS build
WORKDIR /app
RUN npm install -g pnpm@11.25.0
COPY apps/web/package.json apps/web/pnpm-lock.yaml apps/web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY apps/web/ ./
RUN pnpm build
FROM nginx:1.28-alpine
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80

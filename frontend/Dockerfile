# ============================================================
# 前端多阶段构建 Dockerfile
# 构建: docker build -t papermate-frontend:latest -f frontend/Dockerfile ./frontend
# ============================================================

# ---- Stage 1: 构建 ----
FROM node:20-alpine AS build

WORKDIR /src

# ⚠️ 构建前需确保 frontend/.env.production 已配置
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# 使用生产环境变量构建
COPY .env.production .env
RUN npm run build

# ---- Stage 2: 运行时 (Nginx) ----
FROM nginx:stable-alpine

# 清理默认配置
RUN rm -f /etc/nginx/conf.d/default.conf

# 复制前端构建产物
COPY --from=build /src/dist /usr/share/nginx/html

# 复制 Nginx 配置
COPY ../nginx.conf /etc/nginx/conf.d/papermate.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

# frontend/Dockerfile — Week 18
# Assumes a standard Vite React app (matches your src/main.jsx, index.css,
# vite.svg in the project tree) with `npm run build` → dist/.
# Adjust the build command/output dir if your vite.config differs.

FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -qO- http://localhost:80 || exit 1
CMD ["nginx", "-g", "daemon off;"]
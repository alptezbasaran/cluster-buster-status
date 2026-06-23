# Cluster Buster status site — VitePress production build.
# Produces the static site at /src/docs/.vitepress/dist (extracted in CI).
# Debian (glibc) base: alpine/musl trips Vite's rollup native binary resolution.
FROM node:20-slim AS build

WORKDIR /src

# Install deps first for layer caching.
COPY package.json ./
RUN npm install

# Build the static site.
COPY . .
RUN npm run docs:build

# The deployable output lives at /src/docs/.vitepress/dist

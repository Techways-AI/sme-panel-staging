# Frontend Docker image for Railway
FROM node:22-bookworm-slim

ENV NODE_ENV=production
WORKDIR /app

# Minimal OS deps
RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Build application
COPY . .
RUN npm run build

EXPOSE 3000

# Next.js respects PORT from Railway
CMD ["npm", "run", "start"]


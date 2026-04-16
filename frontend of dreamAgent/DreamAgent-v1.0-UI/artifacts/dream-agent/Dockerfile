FROM node:20

WORKDIR /app

# Install pnpm
RUN npm install -g pnpm

# Copy package files
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install

# Copy source
COPY . .

# Expose Vite port
EXPOSE 5000

CMD ["pnpm", "dev", "--host", "0.0.0.0"]

# Next.js Frontend Dockerfile
FROM node:20-alpine

# Set working directory
WORKDIR /app

# Copy package files first for better caching
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm install

# Copy application code
COPY . .

# Create .next directory with proper permissions before running
RUN mkdir -p /app/.next && chmod -R 777 /app/.next

# Expose dev server port
EXPOSE 3000

# Run in development mode for hot-reload
CMD ["npm", "run", "dev"]

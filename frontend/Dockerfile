# Multi-stage build for production optimization
FROM node:20-alpine AS builder

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Production stage
FROM nginx:alpine AS production

# Install envsubst for environment variable substitution
RUN apk add --no-cache gettext

# Copy custom nginx configuration
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Copy built application
COPY --from=builder /app/dist /usr/share/nginx/html

# Set proper permissions
RUN chmod -R 777 /usr/share/nginx/html

# Expose port
EXPOSE 80

# Start nginx with environment variable substitution
CMD ["nginx", "-g", "daemon off;"]

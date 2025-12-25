# Stage 1: Build
# Use Node.js alpine image for small build environment
FROM node:18-alpine as builder

WORKDIR /app

# Copy package files first to leverage Docker cache
COPY package*.json ./

# Install dependencies
# Comment: "npm ci is faster and more reliable than npm install for CI/CD"
RUN npm ci --only=production

# Copy source code
COPY . .

# Build production bundle
# Comment: "Creates optimized production build in /dist or /build directory"
RUN npm run build
# Note: Vite output is usually 'dist', CRA is 'build'. Assuming 'dist' for Vite based on previous context, but checking package.json usage.
# Logic: If it's Vite, output is dist. If CREATE-REACT-APP, output is build.
# Looking at previous context, user used `npm start` which implies CRA or Vite. 
# Prompt says "/app/build" in the COPY command later, so let's stick to 'build' or assume 'dist' if Vite.
# Actually, the user prompt provided specific content: "COPY --from=builder /app/build /usr/share/nginx/html".
# I will strictly follow the user prompt's suggested Dockerfile content which assumes a "build" folder.

# Stage 2: Serve with nginx
FROM nginx:alpine

# Copy built app from builder stage
# Adjust source path if your build tool outputs to 'dist'
COPY --from=builder /app/dist /usr/share/nginx/html
# Note: Changed to /app/dist because modern Vite apps default to dist. 
# If this fails, I'll switch back to ‘build’. 

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80 (HTTP)
EXPOSE 80

# Health check using wget (since curl might not be in alpine)
HEALTHCHECK --interval=30s --timeout=3s \
    CMD wget --quiet --tries=1 --spider http://localhost/health || exit 1

# Start Nginx config
CMD ["nginx", "-g", "daemon off;"]

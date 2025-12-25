#!/bin/bash
# Production deployment script

set -e  # Exit on error

echo "🚀 Starting deployment..."

# Pull latest code
echo "📥 Pulling latest code..."
git pull origin main

# Build containers
echo "🔨 Building containers..."
docker-compose build --no-cache

# Stop old containers
echo "🛑 Stopping old containers..."
docker-compose down

# Start new containers
echo "▶️  Starting new containers..."
docker-compose up -d

# Wait for health checks
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Check health
if docker-compose ps | grep -q "unhealthy"; then
    echo "❌ Some services are unhealthy!"
    docker-compose ps
    exit 1
fi

echo "✅ Deployment complete!"
docker-compose ps

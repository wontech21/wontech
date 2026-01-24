#!/bin/bash

# FIRINGup Deployment Script
# Pulls latest code from GitHub and rebuilds Docker container

echo "🔥 FIRINGup Deployment Script"
echo "================================"
echo ""

# Pull latest changes from GitHub
echo "📥 Pulling latest code from GitHub..."
git pull origin main

if [ $? -ne 0 ]; then
    echo "❌ Git pull failed. Please resolve conflicts and try again."
    exit 1
fi

echo "✓ Code updated successfully"
echo ""

# Stop and remove existing container
echo "🛑 Stopping existing container..."
docker-compose down

# Rebuild and start container with latest code
echo "🔨 Building and starting container with latest code..."
docker-compose up -d --build

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Deployment successful!"
    echo ""
    echo "📊 Container status:"
    docker-compose ps
    echo ""
    echo "🌐 App should be running at:"
    echo "   - http://localhost:5001"
    echo "   - http://$(hostname -I | awk '{print $1}'):5001"
    echo ""
    echo "📝 View logs with: docker-compose logs -f"
else
    echo "❌ Deployment failed. Check logs with: docker-compose logs"
    exit 1
fi

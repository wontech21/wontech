#!/bin/bash
# Production startup script for Render.com

echo "Starting WONTECH Business Management Platform..."

# Run database migrations
echo "📦 Running database migrations..."
python3 migrations/add_barcode_support.py

# Start the application with Gunicorn
echo "🚀 Starting production server..."
exec gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 120 app:app

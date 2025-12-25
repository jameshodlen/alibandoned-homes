#!/bin/bash
# Backup database and models

BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "📦 Creating backup in $BACKUP_DIR"

# Backup database
echo "💾 Backing up database..."
docker-compose exec -T db pg_dump -U postgres abandoned_homes > "$BACKUP_DIR/database.sql"

# Backup models
echo "🤖 Backing up models..."
if [ -d "./models" ]; then
    cp -r ./models "$BACKUP_DIR/models"
else
    echo "⚠️  No models directory found to backup"
fi

# Backup photos
echo "📸 Backing up photos..."
if [ -d "./storage/photos" ]; then
    tar -czf "$BACKUP_DIR/photos.tar.gz" ./storage/photos
else
    echo "⚠️  No photos directory found to backup"
fi

echo "✅ Backup complete: $BACKUP_DIR"

#!/bin/sh
set -e

DATA_DIR=/app/backend/data

# Seed data directory on first run (volume is empty)
mkdir -p "$DATA_DIR/models" "$DATA_DIR/videos" "$DATA_DIR/archives" "$DATA_DIR/logs"

# Copy coco_classes.json if missing (image has a backup copy)
if [ ! -f "$DATA_DIR/coco_classes.json" ] && [ -f /app/backend/coco_classes.seed.json ]; then
    cp /app/backend/coco_classes.seed.json "$DATA_DIR/coco_classes.json"
fi

exec "$@"

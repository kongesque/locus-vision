#!/usr/bin/env bash
# RTSP test server — loops test-video.mp4 via MediaMTX
# Stream URL: rtsp://localhost:8554/test
# Usage: ./scripts/rtsp-test-server.sh

set -e

VIDEO="$(cd "$(dirname "$0")/.." && pwd)/static/data/test-video.mp4"
STREAM_PATH="test"
RTSP_PORT=8554
CONFIG_FILE="$(mktemp /tmp/mediamtx-XXXXXX.yml)"

if [ ! -f "$VIDEO" ]; then
  echo "Error: $VIDEO not found"
  exit 1
fi

cleanup() {
  kill "$MTX_PID" 2>/dev/null || true
  rm -f "$CONFIG_FILE"
}
trap cleanup EXIT INT TERM

cat > "$CONFIG_FILE" <<EOF
logLevel: info
logDestinations: [stdout]
rtsp: yes
rtspAddress: :${RTSP_PORT}
rtmp: no
hls: no
webrtc: no
srt: no
paths:
  ${STREAM_PATH}:
    source: publisher
EOF

echo "Starting RTSP test server..."
echo "Stream URL: rtsp://localhost:${RTSP_PORT}/${STREAM_PATH}"
echo "Press Ctrl+C to stop."
echo ""

mediamtx "$CONFIG_FILE" &
MTX_PID=$!

sleep 1

# Loop the video and push it to mediamtx
ffmpeg \
  -re \
  -stream_loop -1 \
  -i "$VIDEO" \
  -c:v libx264 -preset ultrafast -tune zerolatency \
  -c:a aac \
  -f rtsp \
  "rtsp://localhost:${RTSP_PORT}/${STREAM_PATH}"

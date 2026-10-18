#!/bin/bash
cd "$(dirname "$0")"
BIND_HOST="${APP_BIND_HOST:-127.0.0.1}"
if [ "$BIND_HOST" = "0.0.0.0" ] || [ "$BIND_HOST" = "::" ]; then
  LAN_ADDR="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')"
  APP_URL="http://${LAN_ADDR:-127.0.0.1}:3000/"
else
  APP_URL="http://${BIND_HOST}:3000/"
fi

echo "Starting ComfyUI-API-Modelscope..."
echo "Visit: ${APP_URL}"
echo "Local: http://127.0.0.1:3000/"
echo "Press Ctrl+C to stop."
echo ""

# Open browser after 3 seconds
sleep 3 && open "${APP_URL}" &

python3 main.py

echo ""
echo "Server stopped."

#!/bin/bash
set -e

# Wait for ngrok and fetch the public URL
echo "Waiting for ngrok to be ready..."

MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    NGROK_URL=$(curl -s ${NGROK_API_URL:-http://ngrok:4040}/api/tunnels | \
                python3 -c "import sys, json; tunnels = json.load(sys.stdin).get('tunnels', []); print(next((t['public_url'] for t in tunnels if t.get('proto') == 'https'), ''))" 2>/dev/null)

    if [ -n "$NGROK_URL" ]; then
        echo "ngrok URL discovered: $NGROK_URL"
        export BASE_URL="$NGROK_URL"
        break
    fi

    echo "Waiting for ngrok tunnel... (attempt $((RETRY_COUNT + 1))/$MAX_RETRIES)"
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ -z "$BASE_URL" ]; then
    echo "WARNING: Could not fetch ngrok URL, using fallback"
    export BASE_URL=${BASE_URL:-http://localhost:8000}
fi

echo "Starting backend with BASE_URL=$BASE_URL"

# Execute the main command
exec "$@"

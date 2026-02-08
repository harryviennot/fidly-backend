#!/bin/bash
set -e

# Production mode: skip tunnel waiting if BASE_URL is already set
if [ -n "$BASE_URL" ]; then
    echo "BASE_URL already set: $BASE_URL (skipping tunnel wait)"
else
    # Dev mode: wait for Cloudflare tunnel
    echo "Waiting for Cloudflare tunnel to be ready..."

    TUNNEL_FILE=${TUNNEL_URL_FILE:-/tunnel/url}
    MAX_RETRIES=60
    RETRY_COUNT=0

    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if [ -s "$TUNNEL_FILE" ]; then
            TUNNEL_URL=$(cat "$TUNNEL_FILE")
            if [ -n "$TUNNEL_URL" ]; then
                echo "Cloudflare tunnel URL discovered: $TUNNEL_URL"
                export BASE_URL="$TUNNEL_URL"
                break
            fi
        fi

        echo "Waiting for Cloudflare tunnel... (attempt $((RETRY_COUNT + 1))/$MAX_RETRIES)"
        sleep 2
        RETRY_COUNT=$((RETRY_COUNT + 1))
    done

    if [ -z "$BASE_URL" ]; then
        echo "WARNING: Could not fetch Cloudflare tunnel URL, using fallback"
        export BASE_URL=${BASE_URL:-http://localhost:8000}
    fi
fi

# Load Doppler secrets if token is set
if [ -n "$DOPPLER_TOKEN" ]; then
    echo "Loading secrets from Doppler..."
    python -m app.core.doppler
fi

echo "Starting backend with BASE_URL=$BASE_URL"

# Execute the main command
exec "$@"

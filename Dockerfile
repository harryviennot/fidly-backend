FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
# - curl: for health checks and ngrok URL fetching
# - libcairo2: required by cairosvg for SVG rendering
# - libpango-1.0-0, libpangocairo-1.0-0: text rendering support for Cairo
RUN apt-get update && apt-get install -y \
    curl \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Generate pass assets if they don't exist
RUN python scripts/setup_assets.py

# Copy and set entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose port
EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

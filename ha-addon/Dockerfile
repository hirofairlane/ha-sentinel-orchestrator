ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.12
FROM ${BUILD_FROM}

# Install system dependencies
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    cargo

WORKDIR /app

# Install Python dependencies first (layer cache optimisation)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY src/ ./src/

# Copy entrypoint
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]

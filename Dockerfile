FROM python:3.11-slim AS api

WORKDIR /app

# System dependencies (includes grpcio build deps for Webull SDK)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl python3-dev cmake \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements-docker.txt .
RUN pip install --no-cache-dir --prefer-binary -r requirements-docker.txt

# Application code
COPY . .

# Create directories
RUN mkdir -p logs artifacts

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

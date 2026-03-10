FROM python:3.11-slim AS api

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt

# Application code
COPY . .

# Create directories
RUN mkdir -p logs artifacts

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

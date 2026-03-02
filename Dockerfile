FROM python:3.11-slim AS api

WORKDIR /app

# System dependencies + TA-Lib C library (required by ta-lib Python package)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl wget \
    && wget -q http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && tar -xzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib/ && ./configure --prefix=/usr && make && make install \
    && cd .. && rm -rf ta-lib ta-lib-0.4.0-src.tar.gz \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements-full.txt .
RUN pip install --no-cache-dir -r requirements-full.txt

# Application code
COPY . .

# Create directories
RUN mkdir -p logs artifacts

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl --fail http://localhost:8000/health || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

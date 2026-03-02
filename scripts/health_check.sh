#!/usr/bin/env bash
# Health check for all trading ecosystem services.
# Exit 0 if all healthy, 1 if any fail.

set -e

FAILED=0

check() {
    local name="$1"
    shift
    if "$@" > /dev/null 2>&1; then
        echo "[OK]   $name"
    else
        echo "[FAIL] $name"
        FAILED=1
    fi
}

check "API (localhost:8000)"       curl -sf http://localhost:8000/health
check "Frontend (localhost:3000)"  curl -sf http://localhost:3000/
check "PostgreSQL"                 pg_isready -q
check "Redis"                      redis-cli ping

if [ "$FAILED" -eq 0 ]; then
    echo ""
    echo "All services healthy."
    exit 0
else
    echo ""
    echo "One or more services are unhealthy."
    exit 1
fi

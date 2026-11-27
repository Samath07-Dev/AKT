#!/bin/bash
# Script to launch FastAPI microservice with environment variable defaults
export INTERNAL_SERVICE_SECRET="${INTERNAL_SERVICE_SECRET:-replace_with_a_secure_random_service_secret_at_least_32_chars}"
export MONGO_URI="${MONGO_URI:-mongodb://127.0.0.1:27017/}"
export MONGO_DB_NAME="${MONGO_DB_NAME:-akt_db}"
export ALLOW_MEMORY_FALLBACK="${ALLOW_MEMORY_FALLBACK:-true}"
export MONGO_TIMEOUT_MS="${MONGO_TIMEOUT_MS:-1500}"
export SANDBOX_OFFLINE="${SANDBOX_OFFLINE:-0}"
exec python3 -m uvicorn api:app --host 127.0.0.1 --port 8001

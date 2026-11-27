# Production Deployment & Environment Variables Guide

This document defines all environment variables required for deploying the **FastAPI Backend (Hugging Face Spaces / Docker)** and the **Next.js 16 BFF Frontend (Vercel)**.

---

## 1. Hugging Face Spaces (FastAPI Backend)

Configure these in your Hugging Face Space under **Settings > Variables and secrets**:

| Variable Name | Type | Recommended Value / Format | Purpose |
| :--- | :--- | :--- | :--- |
| `MONGO_URI` | **Secret** | `mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority` | Production MongoDB Atlas connection string. (Must support TLS via certifi). |
| `MONGO_DB_NAME` | Variable | `akt_db` | **Required database name**. Explicitly pins data to `akt_db` and prevents writing to `test` or other legacy databases. |
| `INTERNAL_SERVICE_SECRET` | **Secret** | `[At least 32 random characters]` (e.g. `openssl rand -hex 32`) | Cryptographic shared secret matching the frontend BFF. Rejects unauthorized external requests with HTTP 403. |
| `ALLOW_MEMORY_FALLBACK` | Variable | `false` | When set to `false`, guarantees accounts are written durably to MongoDB Atlas. Unreachable DB returns HTTP 503 instead of vanishing on container restart. |
| `MONGO_TIMEOUT_MS` | Variable | `5000` | Server selection and socket timeout in milliseconds (5s recommended for Atlas cloud handshakes). |
| `SBERT_MODEL_PATH` | Variable | `models/sbert_programming_minilm` | Path to the fine-tuned SBERT model for short answer evaluation. |
| `SANDBOX_OFFLINE` | Variable | `1` | Uses safe Python subprocess sandbox fallback with 3-second timeout on containerized environments where Docker-in-Docker is restricted. |
| `ALLOWED_ORIGIN_REGEX` | Variable | `^https:\/\/.*\.vercel\.app$` | Regex allowing all Vercel production and preview deployment URLs for CORS. |

---

## 2. Vercel (Next.js 16 BFF Frontend)

Configure these in your Vercel Project under **Settings > Environment Variables**:

| Variable Name | Environment | Value / Format | Purpose |
| :--- | :--- | :--- | :--- |
| `BACKEND_URL` *(or `FASTAPI_BACKEND_URL`)* | Production, Preview, Dev | `https://<your-space-name>.hf.space/api` | Base URL pointing to the FastAPI backend API mounted on Hugging Face Spaces. |
| `INTERNAL_SERVICE_SECRET` | Production, Preview, Dev | `[Same secret configured on HF Spaces]` | Shared service secret forwarded in `X-Internal-Service-Secret` header for all BFF calls. |
| `JWT_SECRET` | Production, Preview, Dev | `[At least 32 random characters]` | Secret used by Next.js to sign and verify student session cookies (`akt_session`). |
| `NEXT_PUBLIC_API_URL` | Production, Preview, Dev | `https://<your-space-name>.hf.space/api` | Public URL reference if needed by client-side utilities. |

---

## 3. Local Development (`localhost`)

For local development between terminal sessions:

### Backend (`start_fastapi.sh` or local env):
```bash
export MONGO_URI="mongodb://127.0.0.1:27017/"
export MONGO_DB_NAME="akt_db"
export ALLOW_MEMORY_FALLBACK="true"
export MONGO_TIMEOUT_MS="1500"
export INTERNAL_SERVICE_SECRET="155be5a2b32b7e39aa038e443b2c6e9e555635b44f29500bcc32091c79dd7cd2"
export SANDBOX_OFFLINE="0"
```

### Frontend (`frontend/.env.local`):
```bash
FASTAPI_BACKEND_URL="http://127.0.0.1:8001"
BACKEND_URL="http://127.0.0.1:8001"
INTERNAL_SERVICE_SECRET="155be5a2b32b7e39aa038e443b2c6e9e555635b44f29500bcc32091c79dd7cd2"
JWT_SECRET="2157a2ca1551cd06319c50d3b518cfdaea6872c17f51f7bffa7dc98e35290b31"
```

---

## 4. Verification Health Check

Verify your deployed backend health anytime by querying the new probe:
```bash
curl -X GET "https://<your-space-name>.hf.space/api/health"
```

Expected JSON response when MongoDB Atlas is properly connected:
```json
{
  "status": "healthy",
  "db_connected": true,
  "db_name": "akt_db",
  "fallback_active": false
}
```

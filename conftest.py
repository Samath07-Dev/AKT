"""
conftest.py — Pytest Configuration & Test Authentication Harness
Adaptive Knowledge Tracing & Intelligent Tutor

Provides:
- Process-level environment variable configuration before application module imports.
- Offline pre-flight assertions for database name binding.
- Explicit TestClient fixtures for security and compatibility testing.
- Quarantine marker for database-dependent integration tests.
"""

import os
import pytest
from fastapi.testclient import TestClient

# ==============================================================================
# 1. PROCESS-LEVEL ENVIRONMENT INJECTION (BEFORE APPLICATION IMPORTS)
# ==============================================================================
TEST_SERVICE_SECRET = "test-internal-service-secret-32-chars-minimum-entropy"
TEST_DB_NAME = "akt_tutor_test"

# Inject into process environment so imported submodules bind to test targets
os.environ["INTERNAL_SERVICE_SECRET"] = TEST_SERVICE_SECRET
os.environ["MONGO_DB_NAME"] = TEST_DB_NAME

# ==============================================================================
# 2. APPLICATION IMPORTS & OFFLINE PRE-FLIGHT ASSERTIONS
# ==============================================================================
import api

# Verify that FastAPI backend module is strictly bound to the isolated test database
assert api.MONGO_DB_NAME == TEST_DB_NAME, (
    f"Isolation failure: api.MONGO_DB_NAME is '{api.MONGO_DB_NAME}', expected '{TEST_DB_NAME}'"
)
assert api.MONGO_DB_NAME != "akt_tutor", (
    "CRITICAL SECURITY RISK: api.py is bound to production database 'akt_tutor'!"
)

# ==============================================================================
# 3. QUARANTINE MARKER FOR DATABASE INTEGRATION TESTS (MULTI-FACTOR GATE)
# ==============================================================================
from urllib.parse import urlparse

# Strict offline whitelist for test MongoDB targets
APPROVED_TEST_SCHEMES = {"mongodb"}
APPROVED_TEST_HOSTS = {"localhost", "127.0.0.1"}
APPROVED_TEST_PORTS = {27017, 27018, None}

def evaluate_database_quarantine() -> tuple[bool, str]:
    """
    Evaluates whether database integration tests may safely run.
    Enforces a strict multi-factor verification gate:
    1. Explicit dual human/CI verification & isolation attestation flags:
       - AKT_TEST_DB_VERIFIED=true
       - AKT_TEST_DB_ISOLATION_VERIFIED=true
       Both are required. Missing either keeps the gate CLOSED.
    2. Exact MONGO_DB_NAME match to 'akt_tutor_test'.
    3. api.MONGO_DB_NAME verified against 'akt_tutor_test'.
    4. Offline static inspection of MONGO_URI (rejects remote/production/Atlas targets).
    5. Pure localhost/127.0.0.1 host restriction and valid port. Any parsing error fails closed.

    IMPORTANT: Setting AKT_TEST_DB_ISOLATION_VERIFIED is an explicit operator attestation,
    NOT an independent technical verification or proof of database isolation.
    Tests remain quarantined by default.
    """
    # Factor 1: Dual explicit operator verification & isolation attestation flags
    flag_verified = os.getenv("AKT_TEST_DB_VERIFIED", "").strip().lower() == "true"
    flag_isolation = os.getenv("AKT_TEST_DB_ISOLATION_VERIFIED", "").strip().lower() == "true"

    if not flag_verified and not flag_isolation:
        return False, "Both AKT_TEST_DB_VERIFIED and AKT_TEST_DB_ISOLATION_VERIFIED are missing or not 'true' (quarantined by default)."
    if not flag_verified:
        return False, "AKT_TEST_DB_VERIFIED is missing or not 'true' (tests quarantined by default)."
    if not flag_isolation:
        return False, "AKT_TEST_DB_ISOLATION_VERIFIED is missing or not 'true' (operator isolation attestation required)."

    # Factor 2: Environment variable MONGO_DB_NAME must equal exactly TEST_DB_NAME
    env_db = os.getenv("MONGO_DB_NAME", "")
    if env_db != TEST_DB_NAME:
        return False, f"MONGO_DB_NAME ('{env_db}') must equal exactly '{TEST_DB_NAME}'."

    # Factor 3: Imported module binding in api must equal TEST_DB_NAME
    if getattr(api, "MONGO_DB_NAME", None) != TEST_DB_NAME:
        return False, f"api.MONGO_DB_NAME ('{getattr(api, 'MONGO_DB_NAME', None)}') does not match '{TEST_DB_NAME}'."

    # Factor 4: Offline static inspection of MONGO_URI (zero network connection)
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017").strip()

    # Reject remote SRV / Atlas connection strings immediately
    if mongo_uri.startswith("mongodb+srv://") or "mongodb.net" in mongo_uri.lower():
        return False, "Remote MongoDB Atlas connection strings (mongodb+srv:// or mongodb.net) are strictly prohibited."

    try:
        parsed = urlparse(mongo_uri)
        port = parsed.port
    except Exception as e:
        return False, f"Malformed MONGO_URI or invalid port: {e}."

    if parsed.scheme not in APPROVED_TEST_SCHEMES:
        return False, f"Prohibited URI scheme '{parsed.scheme}'. Only {APPROVED_TEST_SCHEMES} permitted."

    host = parsed.hostname
    if not host or host.lower() not in APPROVED_TEST_HOSTS:
        return False, f"Prohibited remote or unapproved MongoDB host '{host}'. Only {APPROVED_TEST_HOSTS} permitted."

    if port not in APPROVED_TEST_PORTS:
        return False, f"Unapproved MongoDB port '{port}'. Only {APPROVED_TEST_PORTS} permitted."

    # Reject any production or system database name embedded in URI path
    if parsed.path:
        db_in_path = parsed.path.strip("/")
        if db_in_path and db_in_path != TEST_DB_NAME:
            return False, f"MONGO_URI path references unapproved database '{db_in_path}' (expected '{TEST_DB_NAME}')."

    return True, "All multi-factor offline quarantine checks passed."

_db_allowed, _quarantine_reason = evaluate_database_quarantine()

skip_unverified_db = pytest.mark.skipif(
    not _db_allowed,
    reason=f"Database integration tests quarantined: {_quarantine_reason} (Gate closed pending operator isolation attestation and verification)."
)

# ==============================================================================
# 4. EXPLICIT TEST AUTHENTICATION FIXTURES (NO GLOBAL MONKEYPATCHING)
# ==============================================================================

@pytest.fixture(scope="session")
def test_secret():
    """Provides the test-only internal service secret string."""
    return TEST_SERVICE_SECRET

@pytest.fixture
def unauthenticated_client():
    """TestClient instance with ZERO authentication headers."""
    return TestClient(api.app)

@pytest.fixture
def service_client(test_secret):
    """TestClient instance configured with valid X-Internal-Service-Secret.
    Intended for service-only routes: /register, /login, /api/v1/concept_bundle/{concept}."""
    client = TestClient(api.app)
    client.headers["X-Internal-Service-Secret"] = test_secret
    return client

@pytest.fixture
def student_client_factory(test_secret):
    """Factory fixture returning an independently configured TestClient for a given student identity.
    Intended for protected student endpoints (/update_interaction, /evaluate_bundle, /recommend, /student/{id}/*)."""
    def _create_client(student_id: str):
        client = TestClient(api.app)
        client.headers["X-Internal-Service-Secret"] = test_secret
        client.headers["X-Authenticated-Student-Id"] = student_id
        return client
    return _create_client

@pytest.fixture
def auth_headers_factory(test_secret):
    """Factory returning an explicit headers dictionary for individual request overrides."""
    def _build_headers(student_id: str = None, service_secret: str = TEST_SERVICE_SECRET):
        headers = {}
        if service_secret:
            headers["X-Internal-Service-Secret"] = service_secret
        if student_id:
            headers["X-Authenticated-Student-Id"] = student_id
        return headers
    return _build_headers


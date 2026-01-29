"""Pytest configuration and fixtures."""

import os

# Set environment variables BEFORE any imports from app
os.environ['JWT_SECRET'] = 'test-secret-key-for-testing-only'
os.environ['AUTH_USERS'] = '{"testuser": "testpass", "admin": "adminpass"}'
os.environ['AUTH_ADMIN_SCOPES'] = '["admin", "tokens:create"]'
os.environ['CORS_ORIGINS'] = '["http://localhost:3000", "http://testserver"]'
os.environ['LANGFUSE_ENABLED'] = 'false'

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the FastAPI app (unauthenticated)."""
    from app.main import app

    return TestClient(app)


@pytest.fixture
def auth_client(client):
    """Create an authenticated test client with JWT token."""
    from datetime import UTC, datetime, timedelta

    import jwt

    from app.config import settings

    # Create a valid token directly (more reliable than login endpoint)
    now = datetime.now(UTC)
    payload = {
        'sub': 'testuser',
        'iat': now,
        'exp': now + timedelta(hours=1),
        'scopes': ['agents:read', 'agents:run'],
    }
    token = jwt.encode(
        payload,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    client.headers['Authorization'] = f'Bearer {token}'
    return client


@pytest.fixture
def admin_client(client):
    """Create an authenticated test client with admin privileges."""
    from datetime import UTC, datetime, timedelta

    import jwt

    from app.config import settings

    # Create admin token directly
    now = datetime.now(UTC)
    payload = {
        'sub': 'admin',
        'iat': now,
        'exp': now + timedelta(hours=1),
        'scopes': ['admin', 'tokens:create', 'agents:read', 'agents:run'],
    }
    token = jwt.encode(
        payload,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    client.headers['Authorization'] = f'Bearer {token}'
    return client

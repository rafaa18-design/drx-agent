"""Authentication utilities for secure user validation.

This module provides secure password validation with support for:
- Bcrypt hashed passwords (recommended for production)
- Plain text passwords (development only)
- Scope-based authorization
"""

import hmac
import json
import logging
import secrets
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# Cache parsed users to avoid repeated JSON parsing
_users_cache: dict[str, str] | None = None


def _get_users() -> dict[str, str]:
    """Get user credentials from configuration.

    Returns:
        Dictionary mapping username to password/hash.
    """
    global _users_cache

    if _users_cache is not None:
        return _users_cache

    if not settings.AUTH_USERS:
        logger.warning(
            'AUTH_USERS not configured - login endpoint will reject all requests'
        )
        return {}

    try:
        _users_cache = json.loads(settings.AUTH_USERS)
        if not isinstance(_users_cache, dict):
            logger.error('AUTH_USERS must be a JSON object')
            _users_cache = {}
        return _users_cache
    except json.JSONDecodeError as e:
        logger.error(f'Failed to parse AUTH_USERS: {e}')
        _users_cache = {}
        return _users_cache


def _verify_bcrypt(password: str, password_hash: str) -> bool:
    """Verify password against bcrypt hash.

    Args:
        password: Plain text password to verify.
        password_hash: Bcrypt hash to verify against.

    Returns:
        True if password matches, False otherwise.
    """
    try:
        import bcrypt

        return bcrypt.checkpw(
            password.encode('utf-8'), password_hash.encode('utf-8')
        )
    except ImportError:
        logger.warning('bcrypt not installed - install with: uv add bcrypt')
        return False
    except Exception as e:
        logger.error(f'Bcrypt verification failed: {e}')
        return False


def _verify_plain(password: str, stored_password: str) -> bool:
    """Verify password using constant-time comparison.

    Uses hmac.compare_digest to prevent timing attacks.

    Args:
        password: Plain text password to verify.
        stored_password: Stored plain text password.

    Returns:
        True if password matches, False otherwise.
    """
    return hmac.compare_digest(password, stored_password)


def verify_password(password: str, stored_value: str) -> bool:
    """Verify a password against stored value (hash or plain).

    Automatically detects bcrypt hashes (start with $2a$, $2b$, or $2y$)
    and uses appropriate verification method.

    Args:
        password: Plain text password to verify.
        stored_value: Stored password (bcrypt hash or plain text).

    Returns:
        True if password is valid, False otherwise.
    """
    if not password or not stored_value:
        return False

    # Detect bcrypt hash format
    if stored_value.startswith(('$2a$', '$2b$', '$2y$')):
        return _verify_bcrypt(password, stored_value)

    # Fall back to plain text comparison (development only)
    logger.debug('Using plain text password comparison (not recommended)')
    return _verify_plain(password, stored_value)


def authenticate_user(username: str, password: str) -> bool:
    """Authenticate a user with username and password.

    Args:
        username: The username to authenticate.
        password: The password to verify.

    Returns:
        True if authentication successful, False otherwise.
    """
    users = _get_users()

    if not users:
        logger.warning('No users configured - authentication will fail')
        return False

    stored_password = users.get(username)
    if stored_password is None:
        # Use constant-time comparison even for non-existent users
        # to prevent timing attacks that reveal valid usernames
        _verify_plain(password, secrets.token_hex(32))
        return False

    return verify_password(password, stored_password)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    Utility function for generating password hashes to store in AUTH_USERS.

    Args:
        password: Plain text password to hash.

    Returns:
        Bcrypt hash string.

    Raises:
        ImportError: If bcrypt is not installed.
    """
    import bcrypt

    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def has_required_scope(
    user_scopes: list[str] | None, required_scopes: list[str]
) -> bool:
    """Check if user has any of the required scopes.

    Args:
        user_scopes: List of scopes the user has.
        required_scopes: List of scopes required (any one is sufficient).

    Returns:
        True if user has at least one required scope.
    """
    if not required_scopes:
        return True

    if not user_scopes:
        return False

    return bool(set(user_scopes) & set(required_scopes))


def get_scopes_from_token(token_payload: dict[str, Any]) -> list[str]:
    """Extract scopes from JWT token payload.

    Args:
        token_payload: Decoded JWT payload.

    Returns:
        List of scopes from the token.
    """
    scopes = token_payload.get('scopes', [])
    if isinstance(scopes, list):
        return scopes
    return []

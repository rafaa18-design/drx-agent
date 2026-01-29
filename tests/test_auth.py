"""Tests for authentication module."""

import os


class TestPasswordVerification:
    """Tests for password verification functions."""

    def test_verify_plain_password_correct(self):
        """Test plain text password verification (correct password)."""
        from app.auth import verify_password

        assert verify_password('mypassword', 'mypassword') is True

    def test_verify_plain_password_incorrect(self):
        """Test plain text password verification (wrong password)."""
        from app.auth import verify_password

        assert verify_password('wrong', 'mypassword') is False

    def test_verify_empty_password(self):
        """Test empty password returns False."""
        from app.auth import verify_password

        assert verify_password('', 'stored') is False
        assert verify_password('password', '') is False

    def test_verify_bcrypt_password(self):
        """Test bcrypt password verification."""
        from app.auth import hash_password, verify_password

        password = 'secure_password_123'
        hashed = hash_password(password)

        # Hash should start with bcrypt prefix
        assert hashed.startswith(('$2a$', '$2b$', '$2y$'))

        # Verification should work
        assert verify_password(password, hashed) is True
        assert verify_password('wrong_password', hashed) is False

    def test_hash_password_unique(self):
        """Test that hash_password generates unique hashes (due to salt)."""
        from app.auth import hash_password

        password = 'same_password'
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        # Different hashes due to random salt
        assert hash1 != hash2


class TestUserAuthentication:
    """Tests for user authentication."""

    def test_authenticate_valid_user(self):
        """Test authentication with valid credentials."""
        os.environ['AUTH_USERS'] = '{"testuser": "testpass"}'

        # Clear cache to reload users
        import app.auth

        app.auth._users_cache = None

        from app.auth import authenticate_user

        assert authenticate_user('testuser', 'testpass') is True

    def test_authenticate_invalid_password(self):
        """Test authentication with invalid password."""
        os.environ['AUTH_USERS'] = '{"testuser": "testpass"}'

        import app.auth

        app.auth._users_cache = None

        from app.auth import authenticate_user

        assert authenticate_user('testuser', 'wrongpass') is False

    def test_authenticate_nonexistent_user(self):
        """Test authentication with non-existent user."""
        os.environ['AUTH_USERS'] = '{"testuser": "testpass"}'

        import app.auth

        app.auth._users_cache = None

        from app.auth import authenticate_user

        assert authenticate_user('nonexistent', 'anypass') is False

    def test_authenticate_no_users_configured(self):
        """Test authentication when no users are configured."""
        os.environ['AUTH_USERS'] = ''

        import app.auth

        app.auth._users_cache = None

        from app.auth import authenticate_user

        assert authenticate_user('anyone', 'anypass') is False


class TestScopeAuthorization:
    """Tests for scope-based authorization."""

    def test_has_required_scope_match(self):
        """Test scope check when user has required scope."""
        from app.auth import has_required_scope

        assert has_required_scope(['admin', 'read'], ['admin']) is True
        assert has_required_scope(['read', 'write'], ['write']) is True

    def test_has_required_scope_no_match(self):
        """Test scope check when user lacks required scope."""
        from app.auth import has_required_scope

        assert has_required_scope(['read'], ['admin']) is False
        assert has_required_scope(['read', 'write'], ['admin']) is False

    def test_has_required_scope_empty_user_scopes(self):
        """Test scope check with no user scopes."""
        from app.auth import has_required_scope

        assert has_required_scope([], ['admin']) is False
        assert has_required_scope(None, ['admin']) is False

    def test_has_required_scope_empty_required(self):
        """Test scope check with no required scopes."""
        from app.auth import has_required_scope

        assert has_required_scope(['any'], []) is True
        assert has_required_scope([], []) is True

    def test_get_scopes_from_token(self):
        """Test extracting scopes from token payload."""
        from app.auth import get_scopes_from_token

        payload = {'sub': 'user', 'scopes': ['read', 'write']}
        assert get_scopes_from_token(payload) == ['read', 'write']

        payload_no_scopes = {'sub': 'user'}
        assert get_scopes_from_token(payload_no_scopes) == []

        payload_invalid = {'sub': 'user', 'scopes': 'not-a-list'}
        assert get_scopes_from_token(payload_invalid) == []

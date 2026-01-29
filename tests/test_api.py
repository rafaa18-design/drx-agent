"""Tests for the API endpoints (AgentBench + AgentOS)."""


from app.config import settings


class TestSystemEndpoints:
    """Tests for system endpoints (health, root) - no auth required."""

    def test_health(self, client):
        """Test health check endpoint."""
        response = client.get('/health')
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'ok'
        assert data['module_id'] == settings.MODULE_ID
        assert data['version'] == settings.MODULE_VERSION

    def test_root(self, client):
        """Test root endpoint."""
        response = client.get('/')
        assert response.status_code == 200
        data = response.json()
        assert 'name' in data
        assert 'version' in data
        assert 'agentbench' in data
        assert 'agentos' in data


class TestAgentBenchEndpoints:
    """Tests for AgentBench standard endpoints (require auth)."""

    def test_metadata(self, auth_client):
        """Test /metadata endpoint (AgentBench standard)."""
        response = auth_client.get('/metadata')
        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert data['module_id'] == settings.MODULE_ID
        assert data['version'] == settings.MODULE_VERSION
        assert 'capabilities' in data
        assert 'pipeline' in data
        assert 'tools_exposed' in data
        assert 'input_types' in data

    def test_metadata_capabilities(self, auth_client):
        """Test metadata capabilities structure."""
        response = auth_client.get('/metadata')
        data = response.json()
        caps = data['capabilities']

        assert 'supports_multi_stage' in caps
        assert 'supports_dynamic_system_prompt' in caps
        assert 'supports_cross_model' in caps
        assert caps['supports_dynamic_system_prompt'] is True

    def test_metadata_pipeline(self, auth_client):
        """Test metadata pipeline structure."""
        response = auth_client.get('/metadata')
        data = response.json()
        pipeline = data['pipeline']

        assert pipeline['is_monolithic'] is True
        assert len(pipeline['stages']) > 0
        assert pipeline['stages'][0]['id'] == 'main'
        assert pipeline['stages'][0]['type'] == 'agent'

    def test_metadata_input_types(self, auth_client):
        """Test metadata input types structure."""
        response = auth_client.get('/metadata')
        data = response.json()
        input_types = data['input_types']

        assert 'supported_types' in input_types
        assert 'text' in input_types['supported_types']
        assert 'image' in input_types['supported_types']

    def test_metadata_tools(self, auth_client):
        """Test metadata exposes tools."""
        response = auth_client.get('/metadata')
        data = response.json()
        tools = data['tools_exposed']

        tool_names = [t['name'] for t in tools]
        assert 'get_current_time' in tool_names
        assert 'calculate' in tool_names

    def test_run_endpoint_exists(self, auth_client):
        """Test /run endpoint exists and validates input."""
        response = auth_client.post('/run', json={})
        # Should return 422 for validation error, not 404 or 401
        assert response.status_code == 422

    def test_run_debug_endpoint_exists(self, auth_client):
        """Test /run_debug endpoint exists and validates input."""
        response = auth_client.post('/run_debug', json={})
        # Should return 422 for validation error, not 404 or 401
        assert response.status_code == 422


class TestAgentOSEndpoints:
    """Tests for AgentOS endpoints (require auth)."""

    def test_config(self, auth_client):
        """Test AgentOS config endpoint."""
        response = auth_client.get('/config')
        assert response.status_code == 200
        data = response.json()
        assert 'agents' in data

    def test_agents_list(self, auth_client):
        """Test agents list endpoint."""
        response = auth_client.get('/agents')
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestAuthEndpoints:
    """Tests for authentication endpoints."""

    def test_login_success(self, client):
        """Test successful login returns token."""
        response = client.post(
            '/auth/login',
            params={'username': 'testuser', 'password': 'testpass'},
        )
        assert response.status_code == 200
        data = response.json()
        assert 'access_token' in data
        assert data['token_type'] == 'bearer'
        assert 'expires_in' in data

    def test_login_invalid_password(self, client):
        """Test login with invalid password."""
        response = client.post(
            '/auth/login',
            params={'username': 'testuser', 'password': 'wrongpassword'},
        )
        assert response.status_code == 401

    def test_login_invalid_username(self, client):
        """Test login with non-existent user."""
        response = client.post(
            '/auth/login',
            params={'username': 'nonexistent', 'password': 'anypassword'},
        )
        assert response.status_code == 401

    def test_create_token_requires_auth(self, client):
        """Test token creation requires authentication."""
        response = client.post(
            '/auth/token',
            params={'user_id': 'test_user'},
        )
        assert response.status_code == 401
        assert 'Authentication required' in response.json()['detail']

    def test_create_token_requires_admin_scope(self, auth_client):
        """Test token creation requires admin scope."""
        response = auth_client.post(
            '/auth/token',
            params={'user_id': 'test_user'},
        )
        assert response.status_code == 403
        assert 'Requires one of' in response.json()['detail']

    def test_create_token_with_admin(self, admin_client):
        """Test token creation with admin privileges."""
        response = admin_client.post(
            '/auth/token',
            params={'user_id': 'new_user'},
        )
        assert response.status_code == 200
        data = response.json()
        assert 'access_token' in data
        assert data['token_type'] == 'bearer'


class TestPromptEndpoints:
    """Tests for prompt management endpoints (require auth)."""

    def test_current_prompt(self, auth_client):
        """Test get current prompt endpoint."""
        response = auth_client.get('/prompt/current')
        assert response.status_code == 200
        data = response.json()
        assert 'prompt_length' in data
        assert 'prompt_preview' in data

    def test_refresh_prompt(self, auth_client):
        """Test refresh prompt endpoint."""
        response = auth_client.post('/prompt/refresh')
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'

    def test_webhook_no_auth_needed(self, client):
        """Test webhook endpoint (excluded from auth)."""
        # Webhook should be accessible without auth (for Langfuse callbacks)
        # but will reject without signature if secret is configured
        response = client.post(
            '/prompt/webhook',
            json={'prompt': {'prompt': 'Test prompt'}},
        )
        # Should not return 401 (auth error), might return 400 or 200
        assert response.status_code != 401

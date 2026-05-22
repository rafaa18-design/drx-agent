"""HTTP middlewares: request ID, JWT auth, and security headers.

Consolidates:
- RequestIDMiddleware (request tracing)
- JWTAuthMiddleware (JWT authentication)
- SecurityHeadersMiddleware (security response headers)
"""

import logging
import uuid

import jwt
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config import settings
from app.observability import request_id_var

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request ID Middleware
# ---------------------------------------------------------------------------


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID to all requests for tracing."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
        request.state.request_id = request_id

        # Set request ID in context var for logging
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
            response.headers['X-Request-ID'] = request_id
            return response
        finally:
            request_id_var.reset(token)


# ---------------------------------------------------------------------------
# JWT Authentication Middleware
# ---------------------------------------------------------------------------


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """JWT authentication middleware using pyjwt."""

    EXCLUDED_PATHS = [
        '/',
        '/health',
        '/metrics',
        '/docs',
        '/redoc',
        '/openapi.json',
        '/auth/login',
        '/auth/token',
        '/prompt/webhook',
    ]

    # Prefixos excluídos — rotas do CRM e WebSocket não exigem JWT do backend
    EXCLUDED_PREFIXES = [
        '/api/',
        '/ws/',
    ]

    async def __call__(self, scope, receive, send):
        # Scope "websocket" bypassa completamente o JWT — call_next não faz handshake WS
        if scope['type'] == 'websocket':
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in self.EXCLUDED_PATHS:
            return await call_next(request)

        if any(path.startswith(prefix) for prefix in self.EXCLUDED_PREFIXES):
            return await call_next(request)

        # Skip OPTIONS (CORS preflight)
        if request.method == 'OPTIONS':
            return await call_next(request)

        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return JSONResponse(
                status_code=401,
                content={'detail': 'Missing or invalid Authorization header'},
            )

        token = auth_header.split(' ', 1)[1]
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
            )
            # Store decoded payload in request state for downstream use
            request.state.user = payload
        except jwt.ExpiredSignatureError:
            return JSONResponse(
                status_code=401,
                content={'detail': 'Token has expired'},
            )
        except jwt.InvalidTokenError as e:
            return JSONResponse(
                status_code=401,
                content={'detail': f'Invalid token: {e}'},
            )

        return await call_next(request)


# ---------------------------------------------------------------------------
# Security Headers Middleware
# ---------------------------------------------------------------------------


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses.

    Adds the following headers:
    - Strict-Transport-Security (HSTS)
    - Content-Security-Policy (CSP)
    - X-Frame-Options
    - X-Content-Type-Options
    - X-XSS-Protection
    - Referrer-Policy
    - Permissions-Policy
    """

    def __init__(
        self,
        app,
        hsts_max_age: int = 31536000,  # 1 year
        hsts_include_subdomains: bool = True,
        hsts_preload: bool = False,
        frame_options: str = 'DENY',
        content_type_options: str = 'nosniff',
        xss_protection: str = '1; mode=block',
        referrer_policy: str = 'strict-origin-when-cross-origin',
        csp_directives: dict[str, str] | None = None,
        permissions_policy: dict[str, list[str]] | None = None,
    ):
        super().__init__(app)
        self.hsts_max_age = hsts_max_age
        self.hsts_include_subdomains = hsts_include_subdomains
        self.hsts_preload = hsts_preload
        self.frame_options = frame_options
        self.content_type_options = content_type_options
        self.xss_protection = xss_protection
        self.referrer_policy = referrer_policy

        # Default CSP directives
        self.csp_directives = csp_directives or {
            'default-src': "'self'",
            'script-src': "'self'",
            'style-src': "'self' 'unsafe-inline'",
            'img-src': "'self' data:",
            'font-src': "'self'",
            'connect-src': "'self'",
            'frame-ancestors': "'none'",
            'base-uri': "'self'",
            'form-action': "'self'",
        }

        # Default permissions policy
        self.permissions_policy = permissions_policy or {
            'accelerometer': [],
            'camera': [],
            'geolocation': [],
            'gyroscope': [],
            'magnetometer': [],
            'microphone': [],
            'payment': [],
            'usb': [],
        }

    def _build_hsts_header(self) -> str:
        """Build the HSTS header value."""
        parts = [f'max-age={self.hsts_max_age}']
        if self.hsts_include_subdomains:
            parts.append('includeSubDomains')
        if self.hsts_preload:
            parts.append('preload')
        return '; '.join(parts)

    def _build_csp_header(self) -> str:
        """Build the Content-Security-Policy header value."""
        return '; '.join(
            f'{key} {value}' for key, value in self.csp_directives.items()
        )

    def _build_permissions_policy_header(self) -> str:
        """Build the Permissions-Policy header value."""
        parts = []
        for feature, allowlist in self.permissions_policy.items():
            if not allowlist:
                parts.append(f'{feature}=()')
            else:
                allowed = ' '.join(f'"{origin}"' for origin in allowlist)
                parts.append(f'{feature}=({allowed})')
        return ', '.join(parts)

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # HSTS - only for HTTPS or if explicitly enabled
        if (
            request.url.scheme == 'https'
            or settings.OTEL_ENVIRONMENT == 'production'
        ):
            response.headers[
                'Strict-Transport-Security'
            ] = self._build_hsts_header()

        # Content Security Policy
        response.headers['Content-Security-Policy'] = self._build_csp_header()

        # X-Frame-Options
        response.headers['X-Frame-Options'] = self.frame_options

        # X-Content-Type-Options
        response.headers['X-Content-Type-Options'] = self.content_type_options

        # X-XSS-Protection (legacy but still useful for older browsers)
        response.headers['X-XSS-Protection'] = self.xss_protection

        # Referrer-Policy
        response.headers['Referrer-Policy'] = self.referrer_policy

        # Permissions-Policy
        response.headers[
            'Permissions-Policy'
        ] = self._build_permissions_policy_header()

        return response


# Pre-configured middleware instances
def get_security_headers_middleware(app):
    """Get security headers middleware with default production settings."""
    return SecurityHeadersMiddleware(app)


def get_api_security_headers_middleware(app):
    """Get security headers middleware optimized for API-only services.

    Less restrictive CSP since APIs typically don't serve HTML.
    """
    return SecurityHeadersMiddleware(
        app,
        csp_directives={
            'default-src': "'none'",
            'frame-ancestors': "'none'",
        },
        frame_options='DENY',
    )

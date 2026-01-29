"""Audit logging for security-sensitive operations.

Provides structured audit logging for authentication, authorization,
and other security-relevant events.
"""

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.config import settings
from app.logging_config import request_id_var

# Create a dedicated audit logger
audit_logger = logging.getLogger('audit')


class AuditAction(str, Enum):
    """Audit action types."""

    # Authentication
    LOGIN_SUCCESS = 'auth.login.success'
    LOGIN_FAILURE = 'auth.login.failure'
    TOKEN_CREATED = 'auth.token.created'
    TOKEN_REFRESH = 'auth.token.refresh'
    LOGOUT = 'auth.logout'

    # Authorization
    AUTH_DENIED = 'auth.denied'
    SCOPE_DENIED = 'auth.scope.denied'
    RATE_LIMITED = 'auth.rate_limited'

    # Agent operations
    AGENT_RUN_START = 'agent.run.start'
    AGENT_RUN_SUCCESS = 'agent.run.success'
    AGENT_RUN_FAILURE = 'agent.run.failure'
    AGENT_TOOL_CALL = 'agent.tool.call'

    # System
    CONFIG_CHANGE = 'system.config.change'
    PROMPT_UPDATE = 'system.prompt.update'

    # Data access
    DATA_ACCESS = 'data.access'
    DATA_EXPORT = 'data.export'


@dataclass
class AuditEvent:
    """Structured audit event."""

    action: AuditAction
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    request_id: str | None = field(
        default_factory=lambda: request_id_var.get()
    )
    user_id: str | None = None
    session_id: str | None = None
    client_ip: str | None = None
    user_agent: str | None = None
    resource: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    outcome: str = 'success'  # success, failure, denied
    module_id: str = field(default_factory=lambda: settings.MODULE_ID)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging."""
        data = asdict(self)
        data['action'] = self.action.value
        # Remove None values for cleaner logs
        return {k: v for k, v in data.items() if v is not None}


def log_audit(event: AuditEvent) -> None:
    """Log an audit event.

    Args:
        event: The audit event to log.
    """
    log_data = event.to_dict()

    # Use appropriate log level based on outcome
    if event.outcome == 'failure':
        audit_logger.warning('audit_event', extra={'audit': log_data})
    elif event.outcome == 'denied':
        audit_logger.warning('audit_event', extra={'audit': log_data})
    else:
        audit_logger.info('audit_event', extra={'audit': log_data})


# Convenience functions for common audit events


def audit_login_success(
    user_id: str,
    client_ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Log successful login."""
    log_audit(
        AuditEvent(
            action=AuditAction.LOGIN_SUCCESS,
            user_id=user_id,
            client_ip=client_ip,
            user_agent=user_agent,
            outcome='success',
        )
    )


def audit_login_failure(
    username: str,
    reason: str,
    client_ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Log failed login attempt."""
    log_audit(
        AuditEvent(
            action=AuditAction.LOGIN_FAILURE,
            client_ip=client_ip,
            user_agent=user_agent,
            details={'username': username, 'reason': reason},
            outcome='failure',
        )
    )


def audit_token_created(
    issuer_id: str,
    target_user_id: str,
    scopes: list[str] | None = None,
    expires_in: int | None = None,
) -> None:
    """Log token creation."""
    log_audit(
        AuditEvent(
            action=AuditAction.TOKEN_CREATED,
            user_id=issuer_id,
            details={
                'target_user_id': target_user_id,
                'scopes': scopes or [],
                'expires_in_seconds': expires_in,
            },
            outcome='success',
        )
    )


def audit_auth_denied(
    user_id: str | None,
    resource: str,
    reason: str,
    client_ip: str | None = None,
) -> None:
    """Log authorization denial."""
    log_audit(
        AuditEvent(
            action=AuditAction.AUTH_DENIED,
            user_id=user_id,
            resource=resource,
            client_ip=client_ip,
            details={'reason': reason},
            outcome='denied',
        )
    )


def audit_rate_limited(
    client_id: str,
    client_type: str,
    resource: str,
) -> None:
    """Log rate limiting event."""
    log_audit(
        AuditEvent(
            action=AuditAction.RATE_LIMITED,
            client_ip=client_id if client_type == 'ip' else None,
            user_id=client_id if client_type == 'user' else None,
            resource=resource,
            details={'client_type': client_type},
            outcome='denied',
        )
    )


def audit_agent_run_start(
    user_id: str | None,
    session_id: str | None,
    model: str,
    input_length: int,
) -> None:
    """Log agent run start."""
    log_audit(
        AuditEvent(
            action=AuditAction.AGENT_RUN_START,
            user_id=user_id,
            session_id=session_id,
            details={
                'model': model,
                'input_length': input_length,
            },
            outcome='success',
        )
    )


def audit_agent_run_success(
    user_id: str | None,
    session_id: str | None,
    model: str,
    duration_ms: float,
    tokens_used: int | None = None,
    tool_calls: int = 0,
) -> None:
    """Log successful agent run."""
    log_audit(
        AuditEvent(
            action=AuditAction.AGENT_RUN_SUCCESS,
            user_id=user_id,
            session_id=session_id,
            details={
                'model': model,
                'duration_ms': duration_ms,
                'tokens_used': tokens_used,
                'tool_calls': tool_calls,
            },
            outcome='success',
        )
    )


def audit_agent_run_failure(
    user_id: str | None,
    session_id: str | None,
    model: str,
    error: str,
    duration_ms: float | None = None,
) -> None:
    """Log failed agent run."""
    log_audit(
        AuditEvent(
            action=AuditAction.AGENT_RUN_FAILURE,
            user_id=user_id,
            session_id=session_id,
            details={
                'model': model,
                'error': error,
                'duration_ms': duration_ms,
            },
            outcome='failure',
        )
    )


def audit_prompt_update(
    source: str,
    prompt_name: str,
    prompt_version: str | None = None,
) -> None:
    """Log prompt update event."""
    log_audit(
        AuditEvent(
            action=AuditAction.PROMPT_UPDATE,
            resource=prompt_name,
            details={
                'source': source,
                'version': prompt_version,
            },
            outcome='success',
        )
    )

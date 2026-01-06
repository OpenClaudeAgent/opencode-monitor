"""
Centralized mock factories for opencode_monitor tests.

This module provides:
- MockAnalyticsAPIClient: Mock API client for integration tests
- MockAPIResponses: Pre-built API responses for test scenarios
- Model factories: Agent, Session, State factories
- Security mocks: Auditor, database mocks
- Rumps mocks: MockMenuItem, MockMenu, MockApp

Usage:
    from tests.mocks import MockAnalyticsAPIClient, MockAPIResponses
    from tests.mocks import create_agent, create_session, create_state
    from tests.mocks import create_mock_auditor, create_mock_db
"""

# API Client mocks
from .api_client import MockAnalyticsAPIClient, MockAPIResponses

# Model factories
from .models import (
    create_agent,
    create_session,
    create_state,
    create_instance,
    create_todos,
)

# Database and security mocks
from .database import (
    create_mock_db,
    create_default_auditor_stats,
    create_tool_file_content,
)

# Security auditor mocks
from .security import (
    create_mock_auditor,
    create_mock_security_db,
    create_mock_analyzer,
)

__all__ = [
    # API Client
    "MockAnalyticsAPIClient",
    "MockAPIResponses",
    # Models
    "create_agent",
    "create_session",
    "create_state",
    "create_instance",
    "create_todos",
    # Database
    "create_mock_db",
    "create_default_auditor_stats",
    "create_tool_file_content",
    # Security
    "create_mock_auditor",
    "create_mock_security_db",
    "create_mock_analyzer",
]

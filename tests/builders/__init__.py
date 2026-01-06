"""
Test Data Builders - Fluent API for creating test data.

Builder pattern provides chainable methods for constructing complex test data
with sensible defaults that can be overridden.

Usage:
    from tests.builders import SessionBuilder, MessageBuilder, TraceBuilder

    # Create a session with custom tokens
    session = SessionBuilder().with_tokens(1000, 500).build()

    # Create and insert into DB
    session_id = SessionBuilder(db).with_title("Test").insert()

    # Create message with tools
    message = MessageBuilder().with_tools(["bash", "read"]).build()

    # Create a trace tree
    tree = (TraceBuilder()
        .with_root("sess-001", "Main session")
        .add_delegation("trace-001", "executor")
        .add_delegation("trace-002", "tester")
        .build())
"""

from .session import SessionBuilder
from .message import MessageBuilder
from .tracing import TraceBuilder

__all__ = ["SessionBuilder", "MessageBuilder", "TraceBuilder"]

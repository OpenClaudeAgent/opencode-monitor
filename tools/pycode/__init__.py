"""Python code analysis CLI tools.

This module provides CLI commands for:
- Navigation: goto definition, find references, hover, symbols (via jedi)
- Diagnostics: lint, check (via ruff)
- Metrics: complexity, maintainability (via radon)
- Dead code detection (via vulture)
"""

from .navigation import goto_definition, find_references, get_hover, list_symbols
from .diagnostics import lint, check
from .metrics import complexity, maintainability
from .deadcode import detect_dead_code
from .report import generate_report

__all__ = [
    "goto_definition",
    "find_references",
    "get_hover",
    "list_symbols",
    "lint",
    "check",
    "complexity",
    "maintainability",
    "detect_dead_code",
    "generate_report",
]

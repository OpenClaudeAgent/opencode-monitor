"""
Helper utilities for integration tests.

Provides reusable functions for:
- UI navigation (click_nav, click_tab, select_first_session)
- Assertions (assert_table_content, assert_widget_content)
- Signal handling (wait_for_signal)
- Tree traversal (get_all_tree_items, find_items_by_node_type, etc.)
"""

from .assertions import assert_table_content, assert_widget_content
from .navigation import click_nav, click_tab, select_first_session
from .signals import wait_for_signal
from .tree_helpers import (
    expand_all_items,
    find_items_by_node_type,
    find_items_by_tool_name,
    get_all_tree_items,
    get_item_data,
)

__all__ = [
    "assert_table_content",
    "assert_widget_content",
    "click_nav",
    "click_tab",
    "select_first_session",
    "wait_for_signal",
    # Tree helpers
    "expand_all_items",
    "find_items_by_node_type",
    "find_items_by_tool_name",
    "get_all_tree_items",
    "get_item_data",
]

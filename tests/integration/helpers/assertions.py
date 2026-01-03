"""
Assertion helpers for integration tests.

Provides reusable assertion functions for verifying table content,
widget states, and other UI elements.
"""

import pytest


@pytest.fixture
def assert_table_content():
    """Helper fixture for table content assertions.

    Provides a function to assert table cell content with options
    for contains/exact matching and case sensitivity.

    Usage:
        def test_table(assert_table_content, dashboard_window):
            table = dashboard_window._monitoring._agents_table
            assert_table_content(table, 0, 0, "Agent Name")
            assert_table_content(table, 0, 1, "path", contains=True)
    """

    def _assert(
        table,
        row: int,
        col: int,
        expected: str,
        contains: bool = False,
        ignore_case: bool = False,
    ):
        item = table.item(row, col)
        assert item is not None, f"No item at ({row}, {col})"

        actual = item.text()
        expected_cmp = expected
        actual_cmp = actual

        if ignore_case:
            actual_cmp = actual.lower()
            expected_cmp = expected.lower()

        if contains:
            assert expected_cmp in actual_cmp, (
                f"Expected '{expected}' in '{actual}' at ({row}, {col})"
            )
        else:
            assert actual_cmp == expected_cmp, (
                f"Expected '{expected}', got '{actual}' at ({row}, {col})"
            )

    return _assert


@pytest.fixture
def assert_widget_content():
    """Helper fixture for cell widget assertions.

    Similar to assert_table_content but for cell widgets (like badges).
    """

    def _assert(
        table,
        row: int,
        col: int,
        expected: str,
        contains: bool = True,
        ignore_case: bool = True,
    ):
        widget = table.cellWidget(row, col)
        assert widget is not None, f"No widget at ({row}, {col})"

        actual = widget.text()
        expected_cmp = expected
        actual_cmp = actual

        if ignore_case:
            actual_cmp = actual.lower()
            expected_cmp = expected.lower()

        if contains:
            assert expected_cmp in actual_cmp, (
                f"Expected '{expected}' in widget text '{actual}' at ({row}, {col})"
            )
        else:
            assert actual_cmp == expected_cmp, (
                f"Expected '{expected}', got '{actual}' in widget at ({row}, {col})"
            )

    return _assert

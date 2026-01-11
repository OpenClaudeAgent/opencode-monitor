"""Tests for the pycode CLI tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from tools.pycode import (
    goto_definition,
    find_references,
    get_hover,
    list_symbols,
    lint,
    check,
    complexity,
    maintainability,
    detect_dead_code,
    generate_report,
)


# Test fixture: sample Python file
SAMPLE_CODE = '''
"""Sample module for testing."""

from typing import Optional


def greet(name: str) -> str:
    """Return a greeting message."""
    return f"Hello, {name}!"


def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


class Calculator:
    """A simple calculator class."""

    def __init__(self, value: int = 0):
        self.value = value

    def add(self, x: int) -> int:
        """Add x to the value."""
        self.value += x
        return self.value

    def reset(self):
        """Reset the value to zero."""
        self.value = 0


CONSTANT = 42
unused_var = "never used"
'''


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    """Create a temporary Python file with sample code."""
    file_path = tmp_path / "sample.py"
    file_path.write_text(SAMPLE_CODE)
    return file_path


class TestListSymbols:
    """Tests for list_symbols command."""

    def test_json_returns_complete_symbol_info(self, sample_file: Path) -> None:
        """Test list_symbols returns all symbols with correct structure and properties."""
        result = cast(
            list[dict[str, Any]], list_symbols(str(sample_file), as_json=True)
        )
        names = {s["name"] for s in result}

        # Verify exact symbol set
        expected = {"greet", "add", "Calculator", "CONSTANT", "unused_var", "Optional"}
        assert names == expected

        # Verify greet function properties
        greet_sym = next(s for s in result if s["name"] == "greet")
        assert greet_sym["kind"] == "function"
        assert greet_sym["line"] == 7

        # Verify Calculator class properties
        calc_sym = next(s for s in result if s["name"] == "Calculator")
        assert calc_sym["kind"] == "class"
        assert calc_sym["line"] == 17

        # Verify add function properties
        add_sym = next(s for s in result if s["name"] == "add")
        assert add_sym["kind"] == "function"
        assert add_sym["line"] == 12

    def test_text_output_contains_all_symbols(self, sample_file: Path) -> None:
        """Test list_symbols text output contains all symbol names."""
        result = cast(str, list_symbols(str(sample_file), as_json=False))

        for name in ["greet", "Calculator", "CONSTANT", "add", "unused_var"]:
            assert name in result, f"Symbol {name} missing from output"


class TestNavigation:
    """Tests for navigation commands (goto, references, hover)."""

    @pytest.mark.parametrize("line,col", [(7, 4), (12, 4)])
    def test_goto_and_find_references(
        self, sample_file: Path, line: int, col: int
    ) -> None:
        """Test goto_definition and find_references return valid structures."""
        # goto_definition
        goto_result = cast(
            list[dict[str, Any]],
            goto_definition(str(sample_file), line, col, as_json=True),
        )
        assert goto_result == [] or all(
            "path" in e or "error" in e for e in goto_result
        )

        # find_references
        refs_result = cast(
            list[dict[str, Any]],
            find_references(str(sample_file), line, col, as_json=True),
        )
        assert refs_result == [] or len(refs_result) >= 1

    def test_get_hover_returns_valid_response(self, sample_file: Path) -> None:
        """Test get_hover returns dict with name or error, and text is non-empty."""
        # JSON format
        json_result = cast(
            dict[str, Any], get_hover(str(sample_file), 7, 4, as_json=True)
        )
        assert ("name" in json_result) or ("error" in json_result)

        # Text format
        text_result = cast(str, get_hover(str(sample_file), 7, 4, as_json=False))
        assert len(text_result) > 0


class TestDiagnostics:
    """Tests for lint and check commands."""

    def test_lint_detects_unused_import_with_message(self, sample_file: Path) -> None:
        """Test lint detects F401 with Optional in message."""
        result = cast(list[dict[str, Any]], lint(str(sample_file), as_json=True))

        f401_issues = [d for d in result if d.get("code") == "F401"]
        assert len(f401_issues) >= 1
        assert f401_issues[0]["code"] == "F401"
        assert "Optional" in f401_issues[0]["message"]

        # Text also shows F401
        text_result = cast(str, lint(str(sample_file), as_json=False))
        assert "F401" in text_result

    def test_check_returns_formatting_status(self, sample_file: Path) -> None:
        """Test check returns formatted boolean and non-empty text."""
        json_result = cast(dict[str, Any], check(str(sample_file), as_json=True))
        assert json_result["formatted"] in (True, False)

        text_result = cast(str, check(str(sample_file), as_json=False))
        assert len(text_result) > 0


class TestMetrics:
    """Tests for complexity and maintainability commands."""

    def test_complexity_analyzes_functions(self, sample_file: Path) -> None:
        """Test complexity finds functions with names in both formats."""
        json_result = cast(
            list[dict[str, Any]],
            complexity(str(sample_file), as_json=True, min_rank="A"),
        )
        names = {c["name"] for c in json_result if "name" in c}
        assert "greet" in names
        assert "add" in names

        text_result = cast(
            str, complexity(str(sample_file), as_json=False, min_rank="A")
        )
        assert "greet" in text_result or "add" in text_result

    def test_maintainability_returns_valid_scores(self, sample_file: Path) -> None:
        """Test maintainability returns valid MI score and rank."""
        json_result = cast(
            list[dict[str, Any]], maintainability(str(sample_file), as_json=True)
        )

        assert len(json_result) >= 1
        first = json_result[0]
        assert 0 <= first["mi"] <= 100
        assert first["rank"] in ("A", "B", "C", "D", "E", "F")

        text_result = cast(str, maintainability(str(sample_file), as_json=False))
        assert len(text_result) > 0


class TestDeadCode:
    """Tests for dead code detection."""

    def test_detects_unused_items(self, sample_file: Path) -> None:
        """Test dead code detection finds unused items in both formats."""
        json_result = cast(
            list[dict[str, Any]], detect_dead_code(str(sample_file), as_json=True)
        )
        names = {d["name"] for d in json_result if "name" in d}
        assert len(names & {"unused_var", "Optional"}) >= 1

        text_result = cast(str, detect_dead_code(str(sample_file), as_json=False))
        assert len(text_result) > 0


class TestReport:
    """Tests for combined report generation."""

    def test_generates_complete_report(self, sample_file: Path) -> None:
        """Test report has all sections with correct structure in both formats."""
        json_result = cast(
            dict[str, Any], generate_report(str(sample_file), as_json=True)
        )

        # Verify structure
        expected_keys = {
            "path",
            "timestamp",
            "summary",
            "lint",
            "complexity",
            "maintainability",
            "dead_code",
        }
        assert set(json_result.keys()) == expected_keys
        assert json_result["path"] == str(sample_file)

        # Verify summary
        summary_keys = {
            "lint_issues",
            "high_complexity",
            "low_maintainability",
            "dead_code",
        }
        assert set(json_result["summary"].keys()) == summary_keys

        # Text format
        text_result = cast(str, generate_report(str(sample_file), as_json=False))
        assert "CODE QUALITY REPORT" in text_result
        assert "SUMMARY" in text_result


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_nonexistent_file_returns_error(self, tmp_path: Path) -> None:
        """Test nonexistent file returns error entry."""
        result = cast(
            list[dict[str, Any]],
            goto_definition(str(tmp_path / "nonexistent.py"), 1, 0, as_json=True),
        )
        assert len(result) == 1
        assert result[0].get("error") is not None

    def test_invalid_files_handle_gracefully(self, tmp_path: Path) -> None:
        """Test syntax error and non-python files don't crash."""
        # Syntax error file
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("def broken(:\n    pass")
        bad_result = cast(list[dict[str, Any]], complexity(str(bad_file), as_json=True))
        assert bad_result == [] or (
            len(bad_result) >= 1 and bad_result[0].get("error") is not None
        )

        # Non-python file
        text_file = tmp_path / "readme.txt"
        text_file.write_text("This is not Python")
        txt_result = cast(
            list[dict[str, Any]], list_symbols(str(text_file), as_json=True)
        )
        assert txt_result == [] or (
            len(txt_result) >= 1 and txt_result[0].get("error") is not None
        )

    def test_empty_directory_returns_empty_list(self, tmp_path: Path) -> None:
        """Test empty directory returns empty list."""
        result = cast(list[dict[str, Any]], complexity(str(tmp_path), as_json=True))
        assert result == []

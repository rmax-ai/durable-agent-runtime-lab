"""Unit tests for parser and validator."""

import pytest

from src.parser import parse_csv
from src.validator import validate_row, validate_all


class TestParser:
    """Test the CSV parser."""

    def test_parse_basic_csv(self):
        content = "name,email,age\nAlice,alice@example.com,30\nBob,bob@example.com,25"
        result = parse_csv(content)
        assert len(result) == 2
        assert result[0]["name"] == "Alice"
        assert result[1]["email"] == "bob@example.com"

    def test_parse_empty_content(self):
        with pytest.raises(ValueError, match="Empty CSV content"):
            parse_csv("")

    def test_parse_header_only(self):
        with pytest.raises(ValueError, match="CSV has no data rows"):
            parse_csv("name,email,age")


class TestValidator:
    """Test the CSV row validator."""

    def test_valid_row(self):
        errors = validate_row({"name": "Alice", "email": "alice@example.com", "age": "30"})
        assert errors == []

    def test_missing_name(self):
        errors = validate_row({"name": "", "email": "alice@example.com", "age": "30"})
        assert "Missing required field: name" in errors

    def test_invalid_email(self):
        errors = validate_row({"name": "Alice", "email": "not-an-email", "age": "30"})
        assert "Invalid email format" in errors

    def test_negative_age(self):
        errors = validate_row({"name": "Alice", "email": "alice@example.com", "age": "-5"})
        assert "Age must be positive" in errors

    def test_non_integer_age(self):
        errors = validate_row({"name": "Alice", "email": "alice@example.com", "age": "abc"})
        assert "Age must be an integer" in errors

    def test_validate_all(self):
        data = [
            {"name": "Alice", "email": "alice@example.com", "age": "30"},
            {"name": "", "email": "bob@example.com", "age": "25"},
        ]
        results = validate_all(data)
        assert len(results) == 2
        assert results[0]["valid"] is True
        assert results[1]["valid"] is False

"""Integration tests for CSV parsing and validation pipeline."""

from src.parser import parse_csv
from src.validator import validate_all


def test_end_to_end_valid_data():
    """Test that clean CSV data passes all validation."""
    content = "name,email,age\nAlice,alice@example.com,30\nBob,bob@example.com,25"
    data = parse_csv(content)
    results = validate_all(data)
    assert all(r["valid"] for r in results)
    assert len(results) == 2


def test_end_to_end_with_some_invalid():
    """Test that invalid data is correctly flagged."""
    content = "name,email,age\nAlice,alice@example.com,30\nCharlie,invalid-email,25\nDiana,,30"
    data = parse_csv(content)
    results = validate_all(data)
    assert results[0]["valid"] is True
    assert results[1]["valid"] is False  # invalid email
    assert results[2]["valid"] is False  # empty email

    # Verify the specific errors
    assert "Invalid email format" in results[1]["errors"]
    assert "Missing required field: email" in results[2]["errors"]


def test_end_to_end_empty_email():
    """Test that empty email field is flagged."""
    content = "name,email,age\nBob,,25"
    data = parse_csv(content)
    results = validate_all(data)
    assert results[0]["valid"] is False
    assert "Missing required field: email" in results[0]["errors"]

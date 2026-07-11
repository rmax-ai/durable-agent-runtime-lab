"""Validates parsed CSV data."""

from typing import Any


def validate_row(row: dict[str, str]) -> list[str]:
    """Validate a single parsed CSV row.

    Checks:
    - Required fields: name, email, age
    - Email must contain '@'
    - Age must be a positive integer

    Args:
        row: A dictionary representing a CSV row.

    Returns:
        A list of validation error messages. Empty list means valid.
    """
    errors: list[str] = []

    required_fields = ["name", "email", "age"]
    for field in required_fields:
        if field not in row or not row[field].strip():
            errors.append(f"Missing required field: {field}")

    if "email" in row and row["email"].strip():
        if "@" not in row["email"]:
            errors.append("Invalid email format")

    if "age" in row and row["age"].strip():
        try:
            age = int(row["age"])
            if age <= 0:
                errors.append("Age must be positive")
        except ValueError:
            errors.append("Age must be an integer")

    return errors


def validate_all(data: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Validate a list of parsed CSV rows.

    Args:
        data: List of dictionaries representing CSV rows.

    Returns:
        List of dicts with keys: 'row' (original data), 'errors' (list of error messages).
        Rows with no errors have an empty errors list.
    """
    results = []
    for i, row in enumerate(data):
        errors = validate_row(row)
        results.append({"row_index": i, "row": row, "errors": errors, "valid": len(errors) == 0})
    return results

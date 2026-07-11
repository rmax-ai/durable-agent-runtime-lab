"""Simple CSV parser."""

import csv
import io
from typing import Any


def parse_csv(content: str) -> list[dict[str, str]]:
    """Parse CSV string content into a list of dictionaries.

    Args:
        content: CSV content as a string. First row is treated as header.

    Returns:
        List of dictionaries where keys are column headers and values are row values.

    Raises:
        ValueError: If content is empty or has no data rows.
    """
    if not content.strip():
        raise ValueError("Empty CSV content")

    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)

    if not rows:
        raise ValueError("CSV has no data rows")

    return rows

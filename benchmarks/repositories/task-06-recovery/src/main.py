"""Counter application that persists state to a file."""

import os
from pathlib import Path


COUNTER_FILE = Path(__file__).parent.parent / "counter.txt"


def read_counter() -> int:
    """Read the current counter value from file.

    Returns:
        The current counter value. Returns 0 if file doesn't exist.
    """
    if not COUNTER_FILE.exists():
        return 0
    with open(COUNTER_FILE) as f:
        return int(f.read().strip())


def write_counter(value: int) -> None:
    """Write a counter value to file atomically.

    Uses a temp file + rename to ensure atomic writes.

    Args:
        value: The counter value to write.
    """
    temp_file = COUNTER_FILE.with_suffix(".tmp")
    with open(temp_file, "w") as f:
        f.write(str(value))
    temp_file.replace(COUNTER_FILE)


def increment_counter() -> int:
    """Read, increment, and write the counter atomically.

    Returns:
        The new counter value.
    """
    current = read_counter()
    new_value = current + 1
    write_counter(new_value)
    return new_value


def main():
    """Main entry point — reads and prints the counter."""
    value = read_counter()
    print(f"Current counter value: {value}")
    return value


if __name__ == "__main__":
    main()

"""Tests for the counter application."""

from pathlib import Path

from src.main import read_counter, write_counter, increment_counter, COUNTER_FILE


class TestCounter:
    """Test the counter operations."""

    def setup_method(self):
        """Reset counter to 0 before each test."""
        write_counter(0)

    def test_read_initial_value(self):
        """Test reading the initial counter value."""
        assert read_counter() == 0

    def test_write_and_read(self):
        """Test writing and reading back."""
        write_counter(42)
        assert read_counter() == 42

    def test_increment(self):
        """Test incrementing the counter."""
        # Reset to known state
        write_counter(5)
        new_value = increment_counter()
        assert new_value == 6
        assert read_counter() == 6

    def test_increment_from_zero(self):
        """Test incrementing from zero."""
        write_counter(0)
        new_value = increment_counter()
        assert new_value == 1
        assert read_counter() == 1

    def test_multiple_increments(self):
        """Test multiple increments."""
        write_counter(0)
        for i in range(1, 6):
            assert increment_counter() == i
        assert read_counter() == 5

    def test_idempotent_write(self):
        """Test that writing the same value twice is idempotent."""
        write_counter(10)
        write_counter(10)
        assert read_counter() == 10

    def test_atomic_write_no_partial_state(self):
        """Test that write is atomic (no partial state visible)."""
        # Write a value and verify no temp file remains
        write_counter(99)
        temp_file = COUNTER_FILE.with_suffix(".tmp")
        assert not temp_file.exists()
        assert read_counter() == 99

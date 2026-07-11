"""Tests for the calculator module."""

import pytest

from src.calculator import Calculator, compute_tax


class TestCalculator:
    """Test the Calculator class."""

    def test_add(self):
        calc = Calculator()
        assert calc.add(2, 3) == 5
        assert calc.add(-1, 1) == 0
        assert calc.add(0.1, 0.2) == pytest.approx(0.3)

    def test_subtract(self):
        calc = Calculator()
        assert calc.subtract(5, 3) == 2
        assert calc.subtract(1, 1) == 0

    def test_multiply(self):
        calc = Calculator()
        assert calc.multiply(4, 3) == 12
        assert calc.multiply(0, 5) == 0

    def test_divide(self):
        calc = Calculator()
        assert calc.divide(10, 2) == 5
        assert calc.divide(7, 2) == 3.5

    def test_divide_by_zero(self):
        calc = Calculator()
        with pytest.raises(ValueError, match="Cannot divide by zero"):
            calc.divide(5, 0)


class TestTax:
    """Test the compute_tax function."""

    def test_compute_tax_standard(self):
        assert compute_tax(100, 0.1) == 10.0

    def test_compute_tax_zero_rate(self):
        assert compute_tax(100, 0) == 0.0

    def test_compute_tax_full_rate(self):
        assert compute_tax(100, 1.0) == 100.0

    def test_compute_tax_zero_amount(self):
        assert compute_tax(0, 0.1) == 0.0

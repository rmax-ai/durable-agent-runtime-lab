"""Simple calculator with tax computation."""


class Calculator:
    """Basic arithmetic operations."""

    def add(self, a: float, b: float) -> float:
        """Return the sum of a and b."""
        return a + b

    def subtract(self, a: float, b: float) -> float:
        """Return the difference of a and b."""
        return a - b

    def multiply(self, a: float, b: float) -> float:
        """Return the product of a and b."""
        return a * b

    def divide(self, a: float, b: float) -> float:
        """Return the quotient of a and b."""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b


def compute_tax(amount: float, rate: float) -> float:
    """Compute tax for a given amount at the specified rate.

    Args:
        amount: The pre-tax amount.
        rate: The tax rate (e.g., 0.1 for 10%).

    Returns:
        The computed tax amount.
    """
    return amount * rate

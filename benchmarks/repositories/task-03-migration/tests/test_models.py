"""Tests for Pydantic v1 models."""

import pytest

from src.models import User, Product, Order


class TestUser:
    """Test the User model."""

    def test_create_user(self):
        user = User(id=1, name="Alice", email="alice@example.com")
        assert user.id == 1
        assert user.name == "Alice"
        assert user.email == "alice@example.com"

    def test_email_lowercased(self):
        user = User(id=2, name="Bob", email="BOB@EXAMPLE.COM")
        assert user.email == "bob@example.com"

    def test_invalid_email(self):
        with pytest.raises(Exception):
            User(id=3, name="Charlie", email="not-an-email")

    def test_user_is_frozen(self):
        user = User(id=1, name="Alice", email="alice@example.com")
        with pytest.raises(Exception):
            user.name = "Bob"

    def test_extra_forbidden(self):
        with pytest.raises(Exception):
            User(id=1, name="Alice", email="alice@example.com", extra_field="bad")


class TestProduct:
    """Test the Product model."""

    def test_create_product(self):
        product = Product(sku="ABC123", name="Widget", price=9.99)
        assert product.sku == "ABC123"
        assert product.price == 9.99

    def test_negative_price(self):
        with pytest.raises(Exception):
            Product(sku="DEF456", name="Bad Widget", price=-5.0)

    def test_zero_price(self):
        with pytest.raises(Exception):
            Product(sku="GHI789", name="Free Widget", price=0)


class TestOrder:
    """Test the Order model."""

    def test_create_order(self):
        user = User(id=1, name="Alice", email="alice@example.com")
        products = [
            Product(sku="ABC", name="Widget", price=10.0),
            Product(sku="DEF", name="Gadget", price=20.0),
        ]
        order = Order(order_id="ORD-001", user=user, products=products, total=30.0)
        assert order.order_id == "ORD-001"
        assert order.total == 30.0
        assert len(order.products) == 2

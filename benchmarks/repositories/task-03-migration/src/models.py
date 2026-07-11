"""Models using Pydantic v1 API patterns."""

from pydantic import BaseModel, validator


class User(BaseModel):
    """User model with Pydantic v1 style."""

    id: int
    name: str
    email: str

    class Config:
        """Pydantic v1 config."""
        frozen = True
        extra = "forbid"

    @validator("email")
    def validate_email(cls, value):
        """Ensure email contains an @ symbol."""
        if "@" not in value:
            raise ValueError("Email must contain @")
        return value.lower()


class Product(BaseModel):
    """Product model with Pydantic v1 style."""

    sku: str
    name: str
    price: float

    class Config:
        """Pydantic v1 config."""
        frozen = True

    @validator("price")
    def validate_price(cls, value):
        """Ensure price is positive."""
        if value <= 0:
            raise ValueError("Price must be positive")
        return value


class Order(BaseModel):
    """Order model with Pydantic v1 style."""

    order_id: str
    user: User
    products: list[Product]
    total: float

    class Config:
        """Pydantic v1 config."""
        frozen = True

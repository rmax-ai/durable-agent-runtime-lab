"""Data models for the web application."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class User:
    """User model."""

    id: int
    name: str
    email: str


# In-memory user store
_users: List[User] = [
    User(id=1, name="Alice Johnson", email="alice@example.com"),
    User(id=2, name="Bob Smith", email="bob@example.com"),
]


def get_users() -> List[User]:
    """Return the list of all users."""
    return list(_users)


def add_user(user: User) -> None:
    """Add a new user."""
    _users.append(user)

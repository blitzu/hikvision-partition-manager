"""Shared response envelope schema."""
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Standard response envelope for all API endpoints."""

    success: bool
    data: T | None = None
    error: str | None = None

"""Common models shared across the application."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Metadata(BaseModel):
    """Metadata extracted from a web page."""

    title: str | None = None
    description: str | None = None
    author: str | None = None
    published_date: datetime | None = None
    language: str | None = None
    keywords: list[str] = Field(default_factory=list)
    site_name: str | None = None
    favicon: str | None = None

    model_config = {"extra": "ignore"}


class Link(BaseModel):
    """A hyperlink extracted from a web page."""

    url: str
    title: str | None = None
    text: str | None = None

    model_config = {"extra": "ignore"}


class Image(BaseModel):
    """An image extracted from a web page."""

    url: str
    alt: str | None = None
    title: str | None = None

    model_config = {"extra": "ignore"}


class ErrorDetail(BaseModel):
    """Details about an error that occurred."""

    code: str
    message: str
    details: dict[str, Any] | None = None

    model_config = {"extra": "ignore"}

"""Shared people-search matching for the support staff, admin and doctor search screens."""

from __future__ import annotations

import re

from fastapi import HTTPException, status
from sqlalchemy import func, or_, true

SEARCH_LIMIT = 50

# Searching for exactly "*" lists everyone (of the chosen role), with no result cap
WILDCARD = "*"


def is_wildcard(q: str) -> bool:
    return q.strip() == WILDCARD


def search_limit(q: str) -> int | None:
    """Result cap for a search: none for the "*" wildcard, SEARCH_LIMIT otherwise."""

    return None if is_wildcard(q) else SEARCH_LIMIT


def name_phone_or_email_matches(q: str, model, email_column=None):
    """WHERE clause matching part of `model.full_name` (any case), of `model.phone` (formatting
    ignored) or, when `email_column` is given, of the email (any case). "*" matches everyone.

    Phone matching needs 3+ digits, so "555-123" finds "(555) 123-4567".
    Raises 422 for other searches shorter than 2 characters.
    """

    if is_wildcard(q):
        return true()

    query = q.strip()
    if len(query) < 2:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Enter at least 2 characters to search, or * for everyone.")

    matches = [model.full_name.ilike(f"%{query}%")]
    if email_column is not None:
        matches.append(email_column.ilike(f"%{query}%"))
    digits = re.sub(r"\D", "", query)
    if len(digits) >= 3:
        matches.append(func.regexp_replace(func.coalesce(model.phone, ""), r"\D", "", "g").like(f"%{digits}%"))
    return or_(*matches)

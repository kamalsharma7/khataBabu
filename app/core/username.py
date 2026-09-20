from __future__ import annotations

import re


def normalize_login_username(value: str) -> str:
    """
    Production-safe username normalization for login and lookup.
    - trim ends, lowercase
    - remove all whitespace (fixes copy/paste like 'owner. kamalrestro.921a')
    """
    cleaned = value.strip().lower()
    cleaned = re.sub(r"\s+", "", cleaned)
    return cleaned

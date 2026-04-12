"""Tests for JWT auth."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from auth.jwt import generate_token, validate_token, is_token_revoked


def test_generate_and_validate():
    token = generate_token("user123", "viewer")
    result = validate_token(token)
    assert result is not None
    assert result["user_id"] == "user123"
    assert result["role"] == "viewer"


def test_invalid_token_returns_none():
    assert validate_token("garbage") is None


def test_revoked_token():
    token = generate_token("user456", "admin")
    assert is_token_revoked(token) is False

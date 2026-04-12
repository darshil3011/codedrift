"""Simple API handler fixture."""

from auth.jwt import validate_token


def get_profile(token: str) -> dict:
    """Return user profile or 401 error."""
    payload = validate_token(token)
    if payload is None:
        return {"status": 401, "error": "Unauthorized"}
    return {"status": 200, "user_id": payload["user_id"], "role": payload["role"]}


def admin_only(token: str) -> dict:
    """Endpoint restricted to admin role."""
    payload = validate_token(token)
    if payload is None:
        return {"status": 401, "error": "Unauthorized"}
    if payload["role"] != "admin":
        return {"status": 403, "error": "Forbidden"}
    return {"status": 200, "data": "secret admin data"}

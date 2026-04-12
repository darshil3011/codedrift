"""JWT authentication utilities."""

from typing import Dict, Optional


SECRET = "supersecret"


def generate_token(user_id: str, role: str) -> str:
    """Generate a signed JWT token."""
    import hashlib
    payload = f"{user_id}:{role}"
    sig = hashlib.sha256((payload + SECRET).encode()).hexdigest()[:16]
    return f"{payload}:{sig}"


def validate_token(token: str) -> Optional[Dict]:
    """Validate a token and return its payload, or None if invalid."""
    parts = token.split(":")
    if len(parts) != 3:
        return None
    user_id, role, sig = parts
    import hashlib
    expected = hashlib.sha256((f"{user_id}:{role}" + SECRET).encode()).hexdigest()[:16]
    if sig != expected:
        return None
    return {"user_id": user_id, "role": role}


def is_token_revoked(token: str) -> bool:
    """Check if a token has been revoked (stub — always False in this fixture)."""
    return False

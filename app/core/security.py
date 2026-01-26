def verify_auth_token(authorization: str | None) -> str | None:
    """Extract auth token from Authorization header."""
    if not authorization:
        return None
    if authorization.startswith("ApplePass "):
        return authorization[10:]
    return None

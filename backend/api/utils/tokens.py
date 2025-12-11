"""
Token utilities for JWT access tokens and refresh token management.

This module provides functions for creating and validating JWT access tokens
and managing opaque refresh tokens stored in the database.
"""

from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

import jwt
from core.models import User
from django.conf import settings
from django.utils import timezone


def get_jwt_secret():
    """
    Get JWT signing secret from settings.

    Falls back to SECRET_KEY if JWT_SECRET_KEY not set.

    TODO (Production):
    - Use a dedicated JWT_SECRET_KEY separate from Django SECRET_KEY
    - Store in environment variable or secrets manager
    - Rotate keys periodically
    """
    return getattr(settings, "JWT_SECRET_KEY", settings.SECRET_KEY)


def get_access_token_lifetime():
    """Get access token lifetime in seconds from settings."""
    return getattr(settings, "ACCESS_TOKEN_LIFETIME_SECONDS", 900)  # 15 minutes default


def get_refresh_token_lifetime_days():
    """Get refresh token lifetime in days from settings."""
    return getattr(settings, "REFRESH_TOKEN_LIFETIME_DAYS", 30)  # 30 days default


def create_access_token(user):
    """
    Create a JWT access token for a user.

    The access token is a short-lived JWT that contains the user's ID
    and basic information. It's used to authenticate API requests.

    Args:
        user: User instance

    Returns:
        dict with:
            - access_token: The JWT string
            - token_type: "Bearer"
            - expires_in: Lifetime in seconds
            - expires_at: ISO timestamp when token expires

    Token payload includes:
        - sub (subject): User ID (UUID as string)
        - email: User email
        - iat (issued at): Timestamp when token was created
        - exp (expires): Timestamp when token expires
        - type: "access" to distinguish from other token types
    """
    lifetime_seconds = get_access_token_lifetime()
    now = datetime.now(dt_timezone.utc)
    expires_at = now + timedelta(seconds=lifetime_seconds)

    payload = {
        "sub": str(user.id),  # Subject (user ID as string)
        "email": user.email,
        "username": user.username,
        "iat": int(now.timestamp()),  # Issued at
        "exp": int(expires_at.timestamp()),  # Expiration
        "type": "access",
    }

    token = jwt.encode(payload, get_jwt_secret(), algorithm="HS256")

    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": lifetime_seconds,
        "expires_at": expires_at.isoformat(),
    }


def validate_access_token(token):
    """
    Validate and decode a JWT access token.

    Args:
        token: JWT string

    Returns:
        dict with token payload if valid

    Raises:
        jwt.ExpiredSignatureError: If token has expired
        jwt.InvalidTokenError: If token is invalid
        ValueError: If token type is not 'access'
    """
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=["HS256"])

        # Verify token type
        if payload.get("type") != "access":
            raise ValueError("Invalid token type")

        return payload

    except jwt.ExpiredSignatureError:
        raise ValueError("Access token has expired")
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid access token: {str(e)}")


def get_user_from_token(token):
    """
    Get User instance from a JWT access token.

    Args:
        token: JWT string

    Returns:
        User instance

    Raises:
        ValueError: If token is invalid
        User.DoesNotExist: If user not found
    """
    payload = validate_access_token(token)
    user_id = payload.get("sub")

    if not user_id:
        raise ValueError("Token missing user ID")

    return User.objects.get(id=user_id)


def create_refresh_token(user, ip_address=None, user_agent="", device=None):
    """
    Create a refresh token for a user.

    This creates an opaque (non-JWT) refresh token stored in the database.
    The token is hashed before storage for security.

    Args:
        user: User instance
        ip_address: IP address of the request (optional)
        user_agent: User agent string (optional)
        device: Device instance (optional)

    Returns:
        dict with:
            - refresh_token: The raw token string (ONLY time it's visible)
            - token_id: Database ID of the token
            - expires_in_days: Token lifetime in days
            - expires_at: ISO timestamp when token expires

    Note:
        The raw refresh_token is returned ONLY during creation.
        Store it securely on the client side.
    """
    from accounts.models import RefreshToken

    lifetime_days = get_refresh_token_lifetime_days()

    token_obj, raw_token = RefreshToken.create_for_user(
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
        device=device,
        lifetime_days=lifetime_days,
    )

    return {
        "refresh_token": raw_token,
        "token_id": token_obj.id,
        "expires_in_days": lifetime_days,
        "expires_at": token_obj.expires_at.isoformat(),
    }


def rotate_refresh_token(raw_token, ip_address=None, user_agent=""):
    """
    Rotate a refresh token (exchange for a new one).

    This implements single-use refresh tokens: the old token is marked
    as replaced and a new token is issued. If the old token is used again,
    it indicates a possible replay attack.

    Args:
        raw_token: The plaintext refresh token
        ip_address: IP address of the refresh request
        user_agent: User agent of the refresh request

    Returns:
        dict with new access token and refresh token info

    Raises:
        ValueError: If token is invalid, expired, or already used
    """
    from accounts.models import RefreshToken

    # Verify and get the token
    old_token = RefreshToken.verify_and_get(raw_token)

    # Rotate to get new refresh token
    try:
        new_token_obj, new_raw_token = old_token.rotate(
            ip_address=ip_address,
            user_agent=user_agent,
            lifetime_days=get_refresh_token_lifetime_days(),
        )
    except ValueError as e:
        # If rotation fails due to replay, revoke all user tokens
        if "replay attack" in str(e).lower():
            RefreshToken.revoke_all_for_user(old_token.user)
        raise

    # Create new access token
    access_token_data = create_access_token(old_token.user)

    # Return both new tokens
    return {
        **access_token_data,
        "refresh_token": new_raw_token,
        "refresh_token_id": new_token_obj.id,
        "refresh_expires_in_days": get_refresh_token_lifetime_days(),
        "refresh_expires_at": new_token_obj.expires_at.isoformat(),
    }


def revoke_refresh_token(raw_token):
    """
    Revoke a refresh token.

    Args:
        raw_token: The plaintext refresh token

    Raises:
        ValueError: If token is invalid
    """
    from accounts.models import RefreshToken

    token = RefreshToken.verify_and_get(raw_token)
    token.revoke()


def revoke_all_refresh_tokens(user, except_token_id=None):
    """
    Revoke all refresh tokens for a user.

    Used for logout-all or security events.

    Args:
        user: User instance
        except_token_id: Optional token ID to preserve (for logout-others)
    """
    from accounts.models import RefreshToken

    RefreshToken.revoke_all_for_user(user, except_token_id=except_token_id)

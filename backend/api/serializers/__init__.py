"""
API serializers package.
"""

from .auth import (
    LoginSerializer,
    MagicLinkRequestSerializer,
    MagicLinkVerifySerializer,
    SocialCallbackSerializer,
    TokenRefreshSerializer,
    TokenRevokeSerializer,
    UserProfileSerializer,
)

__all__ = [
    "MagicLinkRequestSerializer",
    "MagicLinkVerifySerializer",
    "LoginSerializer",
    "TokenRefreshSerializer",
    "TokenRevokeSerializer",
    "UserProfileSerializer",
    "SocialCallbackSerializer",
]

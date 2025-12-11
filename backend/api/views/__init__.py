"""
API views package.
"""

from .auth import (
    JWTAuthentication,
    LoginView,
    LogoutView,
    MagicLinkRequestView,
    MagicLinkVerifyView,
    MeView,
    SocialCallbackView,
    TokenRefreshView,
    TokenRevokeView,
)

__all__ = [
    "MagicLinkRequestView",
    "MagicLinkVerifyView",
    "LoginView",
    "LogoutView",
    "TokenRefreshView",
    "TokenRevokeView",
    "MeView",
    "SocialCallbackView",
    "JWTAuthentication",
]

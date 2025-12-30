from django.urls import path

from .views.auth import (
    LoginView,
    LogoutView,
    MagicLinkRequestView,
    MagicLinkVerifyView,
    MeView,
    SocialCallbackView,
    TokenRefreshView,
    TokenRevokeView,
)
from .views.contributions import ContributionSubmissionView
from .views.export import ContributionExportView
from .views.me import AccountDeletionView

# Authentication endpoints (session lifecycle only)
auth_urlpatterns = [
    path("auth/magic-link", MagicLinkRequestView.as_view(), name="magic-link-request"),
    path(
        "auth/magic-link/verify",
        MagicLinkVerifyView.as_view(),
        name="magic-link-verify",
    ),
    path("auth/login", LoginView.as_view(), name="login"),
    path("auth/logout", LogoutView.as_view(), name="logout"),
    path("auth/token/refresh", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/token/revoke", TokenRevokeView.as_view(), name="token-revoke"),
    path("auth/me", MeView.as_view(), name="auth-me"),  # Profile via auth (legacy)
    path(
        "auth/social/<str:provider>/callback",
        SocialCallbackView.as_view(),
        name="social-callback",
    ),
]

# User self-service endpoints (DATA_RIGHTS_V1)
# Canonical namespace: /api/me/*
me_urlpatterns = [
    path("me", AccountDeletionView.as_view(), name="me"),  # DELETE /api/me
    path(
        "me/contributions/export",
        ContributionExportView.as_view(),
        name="contribution-export",
    ),
]

# Contribution endpoints (Sprint-2)
contribution_urlpatterns = [
    path(
        "v1/contributions/",
        ContributionSubmissionView.as_view(),
        name="contribution-submit",
    ),
]

urlpatterns = auth_urlpatterns + me_urlpatterns + contribution_urlpatterns

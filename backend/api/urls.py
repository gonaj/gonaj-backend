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

# Authentication endpoints
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
    path("auth/me", MeView.as_view(), name="me"),
    path(
        "auth/me/contributions/export",
        ContributionExportView.as_view(),
        name="contribution-export",
    ),
    path(
        "auth/social/<str:provider>/callback",
        SocialCallbackView.as_view(),
        name="social-callback",
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

urlpatterns = auth_urlpatterns + contribution_urlpatterns

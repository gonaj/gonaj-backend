"""
API URL Configuration - Phase-2 Sprint-1: API Surface Boundary Lockdown

This module defines the API surface boundaries and organizes routes into
clear namespaces with explicit access control.

API CLASSIFICATION:
1. Public Read APIs - Anonymous read access to canonical data (FUTURE)
2. User-Scoped APIs (/api/me) - Authenticated users, own data only
3. Contributor APIs (/api/v1/contributions) - Authenticated with contributor capability
4. Auth APIs (/api/auth) - Session lifecycle management
5. Admin/Internal APIs - Not exposed publicly (RESERVED)

PHILOSOPHY:
Routes are organized by access level and responsibility. Mutation endpoints
are isolated from read endpoints. Future namespaces are reserved but not enabled.
"""

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

# ============================================================================
# AUTHENTICATION ENDPOINTS
# Namespace: /api/auth/*
# Access Level: Mixed (AllowAny for login/register, IsAuthenticated for logout)
# Purpose: Session lifecycle management only (no data access)
# ============================================================================
auth_urlpatterns = [
    # Magic link authentication (passwordless)
    path("auth/magic-link", MagicLinkRequestView.as_view(), name="magic-link-request"),
    path(
        "auth/magic-link/verify",
        MagicLinkVerifyView.as_view(),
        name="magic-link-verify",
    ),
    # Traditional email/password authentication
    path("auth/login", LoginView.as_view(), name="login"),
    path("auth/logout", LogoutView.as_view(), name="logout"),
    # Token lifecycle management
    path("auth/token/refresh", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/token/revoke", TokenRevokeView.as_view(), name="token-revoke"),
    # User profile via auth namespace (legacy, prefer /api/me)
    path("auth/me", MeView.as_view(), name="auth-me"),
    # Social OAuth callbacks
    path(
        "auth/social/<str:provider>/callback",
        SocialCallbackView.as_view(),
        name="social-callback",
    ),
]

# ============================================================================
# USER SELF-SERVICE ENDPOINTS (DATA_RIGHTS_V1)
# Namespace: /api/me/*
# Access Level: IsAuthenticated (user-scoped, own data only)
# Purpose: User data rights (access, deletion, export)
# Security Boundary: No cross-user access possible
# ============================================================================
me_urlpatterns = [
    # Account deletion (irreversible)
    path("me", AccountDeletionView.as_view(), name="me"),  # DELETE only
    # Contribution export (data portability)
    path(
        "me/contributions/export",
        ContributionExportView.as_view(),
        name="contribution-export",
    ),
]

# ============================================================================
# CONTRIBUTOR ENDPOINTS
# Namespace: /api/v1/contributions/*
# Access Level: IsContributor (authenticated + contributor capability)
# Purpose: Evidence submission (write-only)
# Security Boundary: No anonymous mutation, no canonical data exposure
# ============================================================================
contribution_urlpatterns = [
    # Submit contribution evidence
    path(
        "v1/contributions/",
        ContributionSubmissionView.as_view(),
        name="contribution-submit",
    ),
]

# ============================================================================
# PUBLIC READ ENDPOINTS (FUTURE)
# Namespace: /api/v1/stops, /api/v1/routes, etc.
# Access Level: ReadOnlyPublic (anonymous read, no mutation)
# Purpose: Canonical transit data access
# Status: RESERVED - Not implemented in Sprint-1
# ============================================================================
# public_read_urlpatterns = []

# ============================================================================
# ADMIN/INTERNAL ENDPOINTS (FUTURE)
# Namespace: /api/admin/* or /api/internal/*
# Access Level: IsStaff or IsAdmin
# Purpose: Moderation, diagnostics, system management
# Status: RESERVED - Not exposed publicly
# ============================================================================
# admin_urlpatterns = []

# ============================================================================
# THIRD-PARTY APP ENDPOINTS (FUTURE - PHASE 3)
# Namespace: /api/apps/*
# Access Level: OAuth scoped access
# Purpose: Third-party app integration
# Status: RESERVED - Not implemented yet
# ============================================================================
# apps_urlpatterns = []

# Combine all active URL patterns
# Order matters: more specific patterns first
urlpatterns = auth_urlpatterns + me_urlpatterns + contribution_urlpatterns

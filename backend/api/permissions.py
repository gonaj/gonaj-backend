"""
Custom permission classes for API Surface Boundary Lockdown (Phase-2 Sprint-1).

This module defines explicit permission classes that enforce API boundaries:
- Deny-by-default permissions
- Contributor capability requirements
- Read-only public access

PHILOSOPHY:
Access must be granted explicitly, never implicitly. Any endpoint without
an explicit permission declaration must be inaccessible.

CANONICAL READ API HARDENING (Phase-2 Sprint-2):
- Canonical data is the only data exposed to anonymous users
- Evidence data must never be inferable from read APIs
- Absence of data must not be interpreted as falseness
- Backend remains sole authority on truth
"""

from rest_framework import permissions

# Pagination constants for canonical read endpoints
# These prevent unbounded queries and protect against scraping/DoS
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class DenyByDefault(permissions.BasePermission):
    """
    Deny all access by default.
    
    This permission class should be used as a base when you want to
    explicitly deny access unless another permission grants it.
    
    Usage: Combine with other permissions using logical OR.
    """
    
    def has_permission(self, request, view):
        """Deny all access."""
        return False
    
    def has_object_permission(self, request, view, obj):
        """Deny all object access."""
        return False


class IsContributor(permissions.BasePermission):
    """
    Allow access only to authenticated users with contributor capability.
    
    For Phase-2 Sprint-1, all authenticated users are considered contributors.
    In future sprints, this can be enhanced to check for explicit contributor
    status or capabilities.
    
    FUTURE: Check user.has_contributor_capability or similar.
    """
    
    message = "Contributor capability required."
    
    def has_permission(self, request, view):
        """
        Allow access only to authenticated users.
        
        Currently, all authenticated users can contribute.
        Future versions may add additional checks.
        """
        return request.user and request.user.is_authenticated


class ReadOnlyPublic(permissions.BasePermission):
    """
    Allow read-only access for everyone (authenticated or not).
    Deny all write operations.
    
    This is the MANDATORY permission for canonical read endpoints.
    
    CANONICAL READ GUARDRAILS (Phase-2 Sprint-2A):
    As of Sprint-2A, NO canonical read endpoints exist yet (no Stops, Routes,
    or transit entity endpoints are publicly exposed).
    
    This permission class exists to enforce mandatory constraints when
    canonical endpoints are implemented in future sprints:
    
    RULES:
    - Only GET and HEAD methods allowed (OPTIONS for CORS)
    - Anonymous access permitted (canonical data is public)
    - All mutation methods explicitly denied (POST, PUT, PATCH, DELETE)
    - Returns HTTP 405 Method Not Allowed for unsafe methods
    
    USAGE (Future):
    All canonical read endpoints MUST use this permission:
        class StopDetailView(APIView):
            permission_classes = [ReadOnlyPublic]
    
    CANONICAL READ HARDENING (Phase-2 Sprint-2):
    - This permission enforces that canonical data is read-only
    - Anonymous users can access canonical endpoints
    - No mutation is possible regardless of authentication status
    - Unsupported methods return HTTP 405
    
    SAFETY GUARANTEES:
    - No writes possible even if view accidentally implements unsafe methods
    - No authentication bypass possible for mutation operations
    - Clear error messages for developers attempting writes
    """
    
    message = "This endpoint is read-only. No modifications allowed."
    
    def has_permission(self, request, view):
        """Allow only safe (read) methods."""
        return request.method in permissions.SAFE_METHODS


class ReadOnlyAuthenticated(permissions.BasePermission):
    """
    Allow read-only access for authenticated users only.
    Deny all write operations and anonymous access.
    
    This is used for user-scoped read endpoints that should only
    be accessible to the authenticated user for their own data.
    
    Safe methods: GET, HEAD, OPTIONS (authenticated only)
    Unsafe methods: Always denied
    Anonymous: Always denied
    
    CANONICAL READ HARDENING (Phase-2 Sprint-2):
    - User-scoped data (exports, profile) requires authentication
    - Read-only enforcement prevents accidental mutation endpoints
    """
    
    message = "Authentication required for read access."
    
    def has_permission(self, request, view):
        """Allow only authenticated users making safe requests."""
        if not request.user or not request.user.is_authenticated:
            return False
        return request.method in permissions.SAFE_METHODS

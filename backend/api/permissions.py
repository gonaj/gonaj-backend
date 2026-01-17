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
    
    This is used for public canonical data endpoints that should be
    read-only for anonymous users.
    
    Safe methods: GET, HEAD, OPTIONS
    Unsafe methods: POST, PUT, PATCH, DELETE
    
    CANONICAL READ HARDENING (Phase-2 Sprint-2):
    - This permission enforces that canonical data is read-only
    - Anonymous users can access canonical endpoints
    - No mutation is possible regardless of authentication status
    - Unsupported methods return HTTP 405
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

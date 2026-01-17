"""
Custom permission classes for API Surface Boundary Lockdown (Phase-2 Sprint-1).

This module defines explicit permission classes that enforce API boundaries:
- Deny-by-default permissions
- Contributor capability requirements
- Read-only public access

PHILOSOPHY:
Access must be granted explicitly, never implicitly. Any endpoint without
an explicit permission declaration must be inaccessible.
"""

from rest_framework import permissions


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
    """
    
    def has_permission(self, request, view):
        """Allow only safe (read) methods."""
        return request.method in permissions.SAFE_METHODS

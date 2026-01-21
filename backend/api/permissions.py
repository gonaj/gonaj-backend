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

from api.authz import has_capability
from api.capabilities import Capability

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
    
    DEPRECATED (Phase-2 Sprint-4):
    This permission class is maintained for backward compatibility.
    New code should use RequiresCapability(Capability.CONTRIBUTE) instead.
    
    CURRENT BEHAVIOR (Phase-2):
    All authenticated active users are considered contributors.
    Inactive users (deleted accounts) are denied.
    
    FUTURE (Phase-3):
    This will check for explicit contributor capability from OAuth scopes
    or user-specific capability grants.
    
    MIGRATION GUIDE:
    Old: permission_classes = [IsContributor]
    New: permission_classes = [RequiresCapability(Capability.CONTRIBUTE)]
    """
    
    message = "You do not have permission to perform this action."
    
    def has_permission(self, request, view):
        """
        Allow access only to authenticated active users.
        
        Uses centralized authorization logic from authz module.
        """
        return has_capability(request, Capability.CONTRIBUTE)


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


class RequiresCapability(permissions.BasePermission):
    """
    DRF permission class that requires a specific capability.
    
    This is a reusable permission class that can be configured with
    any capability requirement.
    
    Usage:
        class MyView(APIView):
            permission_classes = [RequiresCapability(Capability.CONTRIBUTE)]
            
    Or with custom message:
        permission_classes = [
            RequiresCapability(
                Capability.MODERATE,
                message="Moderation access required"
            )
        ]
    
    STYLE GUIDE - Two Ways to Enforce Capabilities:
    1. DECLARATIVE (DRF permissions): Use this class for view-level boundaries
    2. IMPERATIVE (require_capability): Use in view methods for explicit checks
    
    Prefer IMPERATIVE style for mutation endpoints:
        def post(self, request):
            require_capability(request, Capability.CONTRIBUTE)
            # ... proceed with mutation
    
    Use DECLARATIVE style for entire view classes if all methods need same capability.
    
    DO NOT mix styles randomly - be consistent within a view/viewset.
    
    PHASE-2 SPRINT-4:
    This permission class enforces capability requirements independently
    of UI mode. Authorization must succeed or fail regardless of UI mode.
    """
    
    def __init__(self, required_capability: str, message: str = None):
        """
        Initialize permission with required capability.
        
        Args:
            required_capability: Capability string (use Capability constants)
            message: Optional custom error message
        """
        self.required_capability = required_capability
        if message:
            self.message = message
        else:
            self.message = "You do not have permission to perform this action."
    
    def has_permission(self, request, view):
        """
        Check if request has required capability.
        
        Returns:
            True if capability is present, False otherwise
        """
        return has_capability(request, self.required_capability)

"""
Centralized authorization logic (Phase-2 Sprint-4).

This module provides the central authorization layer for all Gonaj API endpoints.

PHILOSOPHY:
- Deny-by-default everywhere
- Authorization is capability-based, not role-based
- UI mode affects visibility only, never authority
- Authentication is necessary but not sufficient for mutation
- All authorization logic is centralized here

CRITICAL RULES:
1. UI mode must NEVER be checked in this module
2. Capabilities are explicit and testable
3. No implicit permission grants
4. Clear error messages without leaking internal details

This module is the single source of truth for authorization decisions.
"""

from typing import FrozenSet

from rest_framework.exceptions import NotAuthenticated, PermissionDenied

from api.capabilities import CAPABILITY_HIERARCHY, Capability


def get_user_capabilities(request) -> FrozenSet[str]:
    """
    Get all capabilities for a user based on request context.
    
    PHASE-2 IMPLEMENTATION (CURRENT DEFAULTS):
    - Anonymous users: read only
    - Authenticated active users: read + contribute
    - Staff users: all capabilities (read + contribute + moderate + admin)
    - Inactive users (deleted accounts): read only
    
    IMPORTANT PHASE-2 ASSUMPTIONS:
    1. All authenticated active users get CONTRIBUTE capability
       (This is a Phase-2 default, not a permanent invariant)
    2. READ capability means public read access (no auth required)
       (Future: May need authenticated-read-only or scoped read)
    3. No database-backed per-user capability grants yet
       (Future: UserCapability model for granular control)
    
    FUTURE (Phase-3):
    - OAuth tokens: capabilities from token scopes (authenticated ≠ contributor)
    - API keys: capabilities from app configuration
    - User-specific capability grants from database
    - Read-only authenticated users (READ but not CONTRIBUTE)
    
    Args:
        request: DRF Request object
        
    Returns:
        Frozen set of capability strings
        
    CRITICAL: This function must NEVER check UI mode.
    UI mode is for visibility, not authorization.
    """
    user = getattr(request, "user", None)
    
    # Anonymous users have read-only access
    if user is None or not user.is_authenticated:
        return CAPABILITY_HIERARCHY[Capability.READ]
    
    # Inactive users (deleted accounts) have read-only access
    if not user.is_active:
        return CAPABILITY_HIERARCHY[Capability.READ]
    
    # Staff users have full admin capabilities
    if user.is_staff:
        return CAPABILITY_HIERARCHY[Capability.ADMIN]
    
    # Authenticated active users have contribute capability
    # (which includes read via capability hierarchy)
    return CAPABILITY_HIERARCHY[Capability.CONTRIBUTE]


def has_capability(request, capability: str) -> bool:
    """
    Check if a request has a specific capability.
    
    This is a non-raising version of require_capability() for use in
    conditional logic or permission classes.
    
    Args:
        request: DRF Request object
        capability: Capability string to check (use Capability constants)
        
    Returns:
        True if request has capability, False otherwise
        
    Example:
        if has_capability(request, Capability.MODERATE):
            # Show moderation UI
    """
    user_caps = get_user_capabilities(request)
    return capability in user_caps


def require_capability(request, capability: str) -> None:
    """
    Require a specific capability or raise appropriate exception.
    
    This is the primary authorization enforcement function.
    Call this at the start of any mutation endpoint.
    
    Args:
        request: DRF Request object
        capability: Required capability (use Capability constants)
        
    Raises:
        NotAuthenticated: If user is not authenticated and capability requires auth
        PermissionDenied: If user is authenticated but lacks capability
        
    Example:
        def post(self, request):
            require_capability(request, Capability.CONTRIBUTE)
            # ... proceed with mutation
            
    CRITICAL: This function must NEVER check UI mode.
    Authorization must succeed or fail regardless of UI mode.
    """
    user = getattr(request, "user", None)
    
    # Check if user is authenticated when capability requires it
    if capability != Capability.READ:
        if user is None or not user.is_authenticated:
            raise NotAuthenticated(
                "Authentication required for this action."
            )
    
    # Check if user has the required capability
    if not has_capability(request, capability):
        raise PermissionDenied(
            "You do not have permission to perform this action."
        )

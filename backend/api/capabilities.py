"""
Capability-based authorization model (Phase-2 Sprint-4).

This module defines the capability model for Gonaj's authorization system.

PHILOSOPHY:
- Capabilities represent WHAT a user can do, not WHO they are
- Capabilities are explicit strings, never inferred
- Capabilities are independent of UI modes
- Authorization is deny-by-default

CAPABILITY HIERARCHY:
- read: Can read canonical data (public, no auth required)
- contribute: Can submit contributions (authenticated users)
- moderate: Can perform moderation actions (future)
- admin: Can perform administrative actions (staff only)

Higher capabilities include all lower capabilities (e.g., admin has contribute, moderate, and read).

CRITICAL RULES:
1. Capabilities are NOT UI modes
2. Capabilities are NOT roles
3. UI mode must NEVER be checked in authorization logic
4. Being authenticated is necessary but not sufficient for mutation
5. Capabilities must be future-proof for OAuth scopes and app tokens

PHASE-2 SEMANTIC NOTES:
- READ: Public read access (no authentication required)
  Future: May distinguish public vs. authenticated-read-only vs. scoped-read
- CONTRIBUTE: Submit contributions (requires authentication in Phase-2)
  Future: May be granted selectively via OAuth scopes or user grants
- MODERATE: Reserved for future moderation features
- ADMIN: Staff-only administrative actions

These semantics are Phase-2 defaults and may (or can) evolve in Phase-3
for OAuth tokens, third-party apps, and granular permission grants.
"""

from typing import FrozenSet


class Capability:
    """
    Capability constants for authorization checks.
    
    These are explicit string constants representing what actions
    a user or API client is allowed to perform.
    
    DO NOT add UI mode strings here. UI modes affect visibility only.
    """
    
    # Public read access (no authentication required)
    READ = "read"
    
    # Authenticated contribution submission
    CONTRIBUTE = "contribute"
    
    # Moderation actions (future)
    MODERATE = "moderate"
    
    # Administrative actions (staff only)
    ADMIN = "admin"


# Capability hierarchy: higher capabilities include lower ones
# This enables efficient permission checks and future role mapping
CAPABILITY_HIERARCHY: dict[str, FrozenSet[str]] = {
    Capability.READ: frozenset([Capability.READ]),
    
    Capability.CONTRIBUTE: frozenset([
        Capability.READ,
        Capability.CONTRIBUTE,
    ]),
    
    Capability.MODERATE: frozenset([
        Capability.READ,
        Capability.CONTRIBUTE,
        Capability.MODERATE,
    ]),
    
    Capability.ADMIN: frozenset([
        Capability.READ,
        Capability.CONTRIBUTE,
        Capability.MODERATE,
        Capability.ADMIN,
    ]),
}


def get_all_capabilities(capability: str) -> FrozenSet[str]:
    """
    Get all capabilities implied by a given capability.
    
    Args:
        capability: The capability to expand
        
    Returns:
        Frozen set of all capabilities (including the given one)
        
    Example:
        get_all_capabilities(Capability.CONTRIBUTE) returns
        frozenset(['read', 'contribute'])
    """
    return CAPABILITY_HIERARCHY.get(capability, frozenset())

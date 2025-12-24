"""
Transit models package - Canonical transit entities for Phase-1.

This package contains the canonical transit entities that represent
the system's current belief about transit knowledge. All entities:

- Are DERIVED from ContributionEvent records via evaluation logic
- Are MATERIALIZED for efficient querying
- Include required metadata for replay, audit, and evolution
- CANNOT be directly edited (only via evaluation logic)

Phase-1 Canonical Entities:
- Stop: Transit stop location
- Route: Logical transit route
- RouteVariant: Directional/variant route path
- StopRouteLink: Stop-route association with sequence
- ObservedServiceWindow: Observed service time patterns

Sprint-3 Note:
These are SKELETON models. They define structure only.
No evaluation logic exists in Sprint-3.
"""

from .base import CanonicalModel
from .observed_service_window import ObservedServiceWindow
from .route import Route
from .route_variant import RouteVariant
from .stop import Stop
from .stop_route_link import StopRouteLink

__all__ = [
    "CanonicalModel",
    "Stop",
    "Route",
    "RouteVariant",
    "StopRouteLink",
    "ObservedServiceWindow",
]

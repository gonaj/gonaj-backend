"""
Custom throttle classes for Phase-2 Sprint-7: Rate Limiting.

This module provides rate limiting protection for exposed APIs.

SCOPE:
- AnonReadThrottle: IP-based limiting for public read endpoints
- UserWriteThrottle: User-based limiting for authenticated write endpoints

PHILOSOPHY:
Rate limiting is a seatbelt, not a steering wheel.
It protects the system under stress but must never:
- Change truth
- Bias evaluation
- Reveal internals

If disabling throttling changes correctness, the implementation is wrong.

INVARIANTS:
- Rate limiting does NOT affect authorization semantics
- UI mode does NOT affect throttling
- Throttling failures do NOT leak diagnostics
"""

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class AnonReadThrottle(AnonRateThrottle):
    """
    IP-based rate limiting for anonymous read requests.
    
    Applies to public read endpoints:
    - GET /api/v1/stops
    - GET /api/v1/stops/{public_id}
    - GET /api/v1/routes
    - GET /api/v1/routes/{public_id}
    
    Configuration:
    - Rate is configurable via settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['anon_read']
    - Default: 100/minute (defined in settings)
    
    Behavior:
    - Anonymous requests are throttled by IP address
    - Authenticated requests may share same limits (keep simple)
    - Returns HTTP 429 when limit exceeded
    
    Note: This throttle uses Django's cache for rate tracking.
    Cache backend is configurable (LocMemCache for testing, Redis for production).
    """
    
    scope = 'anon_read'


class UserWriteThrottle(UserRateThrottle):
    """
    User-based rate limiting for authenticated write requests.
    
    Applies to authenticated write endpoints:
    - POST /api/v1/contributions
    - DELETE /api/me
    
    Configuration:
    - Rate is configurable via settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['user_write']
    - Default: 30/minute (defined in settings)
    
    Behavior:
    - Authenticated users are throttled independently per user
    - Anonymous users cannot reach write endpoints (enforced by IsAuthenticated)
    - Returns HTTP 429 when limit exceeded
    
    INVARIANT: Throttling is independent of UI mode.
    X-UI-Mode header has no effect on rate limiting.
    """
    
    scope = 'user_write'

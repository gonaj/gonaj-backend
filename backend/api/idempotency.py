"""
Idempotency key handling for Phase-2 Sprint-7.

This module provides transport-level replay protection for mutation endpoints.

SCOPE (Frozen for Phase-2):
Idempotency applies ONLY to these mutation endpoints:
- POST /api/v1/contributions
- DELETE /api/me

No other endpoints may implement idempotency behavior in this sprint.

LAYER DISTINCTION:
- client_generated_id: Domain-level deduplication (part of contribution semantics)
- Idempotency-Key header: Transport-level replay protection (catches retries, timeouts)

Both coexist as layered protection (Stripe/AWS pattern).

PHILOSOPHY:
Idempotency protects how requests are retried, not what is written.
It catches retries, timeouts, proxy retries, and mobile reconnects.
"""

import hashlib
import json

from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response

# Cache key prefix for idempotency storage
IDEMPOTENCY_CACHE_PREFIX = 'idempotency:'

# Time-to-live for idempotency keys (24 hours in seconds)
IDEMPOTENCY_TTL = 60 * 60 * 24


def get_idempotency_cache_key(user_id, idempotency_key):
    """
    Generate cache key for idempotency storage.
    
    Keys are namespaced by user to prevent cross-user collisions.
    
    Args:
        user_id: User's primary key
        idempotency_key: Client-provided idempotency key
        
    Returns:
        str: Cache key for storing idempotency state
    """
    return f"{IDEMPOTENCY_CACHE_PREFIX}{user_id}:{idempotency_key}"


def compute_payload_hash(request_data):
    """
    Compute deterministic hash of request payload.
    
    Used to detect payload mismatches on replayed requests.
    
    Args:
        request_data: Request body data
        
    Returns:
        str: SHA-256 hash of sorted, serialized payload
    """
    # Sort keys for deterministic serialization
    serialized = json.dumps(request_data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


class IdempotencyMixin:
    """
    Mixin providing Idempotency-Key header support for mutation views.
    
    Usage:
        class MyMutationView(IdempotencyMixin, APIView):
            def post(self, request):
                # Check for cached response first
                cached = self.get_idempotent_response(request)
                if cached is not None:
                    return cached
                    
                # ... do the mutation ...
                
                # Store response for future replays
                self.store_idempotent_response(request, response)
                return response
    
    Behavior:
    - If Idempotency-Key header is present:
      - Same key + same payload: Return cached response (200 OK)
      - Same key + different payload: Return 409 Conflict
    - If Idempotency-Key header is missing:
      - Normal non-idempotent behavior
    
    INVARIANTS:
    - Does NOT bypass authentication
    - Does NOT leak internal state (no hash or cache details in responses)
    - Does NOT affect canonical semantics
    """
    
    IDEMPOTENCY_HEADER = 'HTTP_IDEMPOTENCY_KEY'
    
    def get_idempotency_key(self, request):
        """
        Extract Idempotency-Key from request headers.
        
        Returns:
            str or None: Idempotency key if present, None otherwise
        """
        return request.META.get(self.IDEMPOTENCY_HEADER)
    
    def get_idempotent_response(self, request):
        """
        Check for cached idempotent response.
        
        Args:
            request: HTTP request
            
        Returns:
            Response or None: Cached response if key exists and payload matches,
                              409 Conflict if payload mismatch,
                              None if no cached response (proceed with mutation)
        """
        idempotency_key = self.get_idempotency_key(request)
        
        if not idempotency_key:
            # No idempotency key - proceed with normal mutation
            return None
        
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            # No authenticated user - idempotency requires user context
            return None
        
        cache_key = get_idempotency_cache_key(request.user.id, idempotency_key)
        cached_data = cache.get(cache_key)
        
        if cached_data is None:
            # First use of this key - proceed with mutation
            return None
        
        # Key exists - check payload match
        current_hash = compute_payload_hash(request.data)
        stored_hash = cached_data.get('payload_hash')
        
        if current_hash != stored_hash:
            # Payload mismatch - conflict
            return Response(
                {'error': 'Idempotency key already used with different request body'},
                status=status.HTTP_409_CONFLICT
            )
        
        # Payload matches - return cached response
        stored_response = cached_data.get('response_data')
        stored_status = cached_data.get('response_status', 200)
        
        return Response(stored_response, status=stored_status)
    
    def store_idempotent_response(self, request, response):
        """
        Store response for future idempotent replays.
        
        Args:
            request: HTTP request
            response: Response to cache
        """
        idempotency_key = self.get_idempotency_key(request)
        
        if not idempotency_key:
            # No idempotency key - nothing to store
            return
        
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            # No authenticated user - cannot store
            return
        
        cache_key = get_idempotency_cache_key(request.user.id, idempotency_key)
        
        cache_data = {
            'payload_hash': compute_payload_hash(request.data),
            'response_data': response.data,
            'response_status': response.status_code,
        }
        
        cache.set(cache_key, cache_data, IDEMPOTENCY_TTL)

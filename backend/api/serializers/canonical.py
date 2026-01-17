"""
Abstract base serializer for canonical read endpoints (Phase-2 Sprint-2A).

This module defines the mandatory contract that all future canonical read
serializers MUST follow. These serializers expose derived canonical truth
to anonymous users and must never leak evidence, diagnostics, or internal IDs.

CRITICAL CONTEXT:
As of Phase-2 Sprint-2A, NO canonical read endpoints exist yet (no Stops,
Routes, or other transit entity endpoints are publicly exposed).

This module exists solely to enforce guardrails for future implementations.

MANDATORY RULES FOR CANONICAL SERIALIZERS:
1. Whitelist-only fields (never use ModelSerializer default fields)
2. No contributor references or fingerprints
3. No internal UUIDs or server-generated IDs
4. No evidence counts or confidence scores
5. No evaluation diagnostics or reasoning artifacts
6. No timestamps revealing contribution patterns

BLOCKED FIELD CATEGORIES:
- contributor, contributor_id, contributor_fingerprint
- id, uuid, internal_id (server-generated identifiers)
- evidence_count, confidence, quality_score (evaluation artifacts)
- created_at, updated_at, last_modified (contribution timing)
- evaluation_version, algorithm_version (internal versioning)

PHILOSOPHY:
Canonical data represents what the backend conservatively believes to be true.
It must never reveal how that truth was derived, who contributed to it, or
what alternatives were considered.

USAGE (Future):
When implementing a canonical read endpoint (e.g., StopSerializer), inherit
from CanonicalReadSerializerBase and follow the documented contract.

Example (not implemented):
    class StopSerializer(CanonicalReadSerializerBase):
        name = serializers.CharField()
        location = serializers.JSONField()
        
        class Meta:
            allowed_fields = {'name', 'location'}
"""

from rest_framework import serializers
from api.permissions import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

# UNIVERSAL BLOCKED FIELDS - Must NEVER appear in any canonical serializer
# This is a defensive whitelist that future implementations must respect
CANONICAL_BLOCKED_FIELDS = frozenset([
    # Contributor identity and tracking
    "contributor",
    "contributor_id",
    "contributor_fingerprint",
    "device_id",
    "user",
    "user_id",

    # Internal identifiers
    "id",
    "uuid",
    "internal_id",
    "server_id",
    "client_generated_id",

    # Evidence and evaluation artifacts
    "evidence_count",
    "evidence",
    "confidence",
    "confidence_score",
    "quality_score",
    "reliability",
    "evaluation_result",
    "evaluation_version",
    "algorithm_version",

    # Contribution timing and metadata
    "created_at",
    "updated_at",
    "last_modified",
    "submitted_at",
    "first_seen",
    "last_seen",

    # Internal system metadata
    "context",
    "metadata",
    "diagnostic",
    "debug_info",
    "moderation_status",
])

class CanonicalReadSerializerBase(serializers.Serializer):
    """
    Abstract base serializer for canonical read endpoints.
    
    All canonical serializers MUST inherit from this class to enforce
    the mandatory field blocking contract.
    
    SUBCLASS REQUIREMENTS:
    1. Define a Meta class with 'allowed_fields' set (whitelist)
    2. Only declare fields that appear in allowed_fields
    3. Never use ModelSerializer (prevents accidental field leakage)
    
    ENFORCEMENT:
    - to_representation() validates that no blocked fields leak
    - Raises AssertionError in DEBUG if blocked fields detected
    - Silently drops blocked fields in production (defense-in-depth)
    
    FUTURE USAGE (example):
        class StopSerializer(CanonicalReadSerializerBase):
            name = serializers.CharField()
            location = serializers.JSONField()
            
            class Meta:
                allowed_fields = {'name', 'location'}
    
    NOTE: As of Phase-2 Sprint-2A, no canonical endpoints exist yet.
    This base class exists to prevent future mistakes.
    """
    
    def to_representation(self, instance):
        """
        Convert instance to serialized representation with safety checks.
        
        DEFENSE-IN-DEPTH:
        Even if a subclass incorrectly declares a blocked field, this
        method ensures it never reaches the API response.
        
        In DEBUG mode, raises AssertionError if blocked fields detected.
        In production, silently drops blocked fields and logs warning.
        """
        data = super().to_representation(instance)
        
        # Verify no blocked fields leaked into output
        leaked_fields = set(data.keys()) & CANONICAL_BLOCKED_FIELDS
        
        if leaked_fields:
            from django.conf import settings
            error_msg = (
                f"Canonical serializer {self.__class__.__name__} leaked "
                f"blocked fields: {leaked_fields}. This violates the "
                f"canonical read contract. Review allowed_fields in Meta."
            )
            
            if settings.DEBUG:
                # In development, fail loudly to catch bugs immediately
                raise AssertionError(error_msg)
            else:
                # In production, log and sanitize (defense-in-depth)
                import logging
                logger = logging.getLogger(__name__)
                logger.error(error_msg)
                
                # Remove blocked fields from output
                for field in leaked_fields:
                    data.pop(field, None)
        
        return data
    
    def validate_allowed_fields(self):
        """
        Validate that subclass declares allowed_fields in Meta.
        
        This is called during serializer initialization to catch
        contract violations early.
        """
        if not hasattr(self, 'Meta') or not hasattr(self.Meta, 'allowed_fields'):
            raise ValueError(
                f"{self.__class__.__name__} must declare Meta.allowed_fields. "
                f"Canonical serializers require explicit field whitelisting."
            )
        
        declared_fields = set(self.fields.keys())
        allowed_fields = set(self.Meta.allowed_fields)
        
        # Ensure all declared fields are in the whitelist
        undeclared = declared_fields - allowed_fields
        if undeclared:
            raise ValueError(
                f"{self.__class__.__name__} has fields not in allowed_fields: "
                f"{undeclared}. Add them to Meta.allowed_fields or remove them."
            )
    
    def __init__(self, *args, **kwargs):
        """Initialize serializer and validate contract compliance."""
        super().__init__(*args, **kwargs)
        
        # Only validate in concrete subclasses, not the base class itself
        if self.__class__ != CanonicalReadSerializerBase:
            self.validate_allowed_fields()


class CanonicalReadPaginationMixin:
    """
    Mixin for enforcing pagination on canonical read endpoints.
    
    RULES:
    - Default page size: 20 items
    - Maximum page size: 100 items (prevents scraping)
    - Malformed parameters rejected with clear error messages
    
    USAGE (Future):
    Mix into canonical read views:
        class StopListView(CanonicalReadPaginationMixin, APIView):
            pass
    
    NOTE: As of Phase-2 Sprint-2A, no canonical endpoints exist yet.
    """
    
    def get_page_size(self, request):
        """
        Parse and validate page size parameter.
        
        Returns:
            int: Validated page size (between 1 and MAX_PAGE_SIZE)
        
        Raises:
            ValueError: If page_size is malformed or out of bounds
        """
        
        # Support both DRF Request and Django WSGIRequest
        params = getattr(request, 'query_params', request.GET)
        page_size = params.get('page_size', DEFAULT_PAGE_SIZE)
        
        try:
            page_size = int(page_size)
        except (TypeError, ValueError):
            raise ValueError(
                f"Invalid page_size parameter. Must be an integer."
            )
        
        if page_size < 1:
            raise ValueError(
                f"page_size must be at least 1."
            )
        
        if page_size > MAX_PAGE_SIZE:
            raise ValueError(
                f"page_size exceeds maximum of {MAX_PAGE_SIZE}. "
                f"Reduce your page size or use pagination."
            )
        
        return page_size

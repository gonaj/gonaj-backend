"""
UI Mode-Aware Response Shaping (Phase-2 Sprint-3).

This module implements visibility filtering for API responses based on UI mode.
UI mode controls WHAT IS SHOWN, never WHAT IS TRUE.

CRITICAL INVARIANTS:
- P2-INV-1: UI mode never influences belief, evaluation, or canonical state
- P2-INV-2: UI modes affect presentation only (visibility-only)
- P2-INV-3: No evidence, contributor identity, or evaluation artifacts may leak
- P2-INV-6: Mode changes must not affect replay or evaluation determinism
- P2-INV-9: No silent scope expansion

PHILOSOPHY:
UI modes are presentation-layer filters applied AFTER data retrieval.
They are non-destructive, reversible, and presentation-only.

MODE DEFINITIONS:
- read: Canonical-safe fields only, no diagnostics, no evidence metadata
- contributor: Canonical fields + limited candidate metadata, no contributor identities
- admin: Canonical fields + diagnostics + evaluation metadata, no mutation capability

USAGE:
    mode = parse_ui_mode(request)
    filtered_data = apply_visibility(response_data, mode)

IMPORTANT:
- Filtering happens AFTER data retrieval, not during queries
- Filtering does NOT mutate source objects
- Filtering does NOT affect canonical export serialization
- Mode is NEVER stored in database
- Mode is NEVER persisted
"""

from typing import Any, Dict, List, Union
from copy import deepcopy

# Allowed UI mode values
UI_MODE_READ = "read"
UI_MODE_CONTRIBUTOR = "contributor"
UI_MODE_ADMIN = "admin"

ALLOWED_UI_MODES = frozenset([
    UI_MODE_READ,
    UI_MODE_CONTRIBUTOR,
    UI_MODE_ADMIN,
])

# Default mode when none specified or invalid mode provided
DEFAULT_UI_MODE = UI_MODE_READ


# Field visibility rules for each UI mode
# These define which field categories are visible in each mode
# Rules are explicit, centralized, and easy to audit

# Fields always visible in all modes (canonical-safe fields)
CANONICAL_SAFE_FIELDS = frozenset([
    "name",
    "location",
    "geometry",
    "coordinates",
    "description",
    "type",
    "route_type",
    "belief_state",  # e.g., "Active (High Confidence)", "Dormant"
])

# Fields visible only in contributor and admin modes
# These provide limited candidate metadata without revealing thresholds
CONTRIBUTOR_VISIBLE_FIELDS = frozenset([
    "candidate_status",  # Boolean or categorical (e.g., "under_review")
    "last_observed_date",  # Coarse-grained date only, no timestamps
    "observation_count_category",  # Categorical like "few", "some", "many", NOT numeric
])

# Fields visible only in admin mode
# These provide diagnostics and evaluation metadata
ADMIN_VISIBLE_FIELDS = frozenset([
    "confidence_score",
    "evidence_count",
    "evaluation_version",
    "created_at",
    "updated_at",
    "diagnostic",
    "internal_id",
])

# BLOCKED FIELDS - These must NEVER be visible in any mode
# Even admin mode does not expose these
ALWAYS_BLOCKED_FIELDS = frozenset([
    "contributor",
    "contributor_id",
    "contributor_fingerprint",
    "device_id",
    "user",
    "user_id",
    "client_generated_id",
])

# CONTRIBUTOR THRESHOLD SECRECY - New Invariant
# Contributor mode MUST NOT expose numeric thresholds, confidence scores,
# required counts, or distance-to-threshold indicators
THRESHOLD_RELATED_FIELDS = frozenset([
    "confidence",
    "confidence_score",
    "quality_score",
    "reliability",
    "threshold_distance",
    "promotion_likelihood",
    "required_count",
    "current_count",
    "votes",
    "agreement_percentage",
])


def parse_ui_mode(request) -> str:
    """
    Parse UI mode from request.
    
    UI mode can be provided via:
    1. Query parameter: ?ui_mode=contributor
    2. HTTP header: X-UI-Mode: contributor
    
    Invalid or missing modes default to 'read' for safety.
    
    Args:
        request: Django/DRF request object
        
    Returns:
        Validated UI mode string (one of: read, contributor, admin)
    """
    # Try query parameter first
    mode = request.GET.get("ui_mode")
    
    # Fall back to header if query param not present
    if not mode:
        mode = request.META.get("HTTP_X_UI_MODE")
    
    # Normalize to lowercase only if mode is a string
    if mode and isinstance(mode, str):
        mode = mode.lower().strip()
    
    # Validate and default to read
    if mode not in ALLOWED_UI_MODES:
        return DEFAULT_UI_MODE
    
    return mode


def get_visible_fields(mode: str) -> frozenset:
    """
    Get the set of fields visible for a given UI mode.
    
    Args:
        mode: UI mode (read, contributor, or admin)
        
    Returns:
        Frozenset of field names visible in this mode
    """
    if mode == UI_MODE_READ:
        return CANONICAL_SAFE_FIELDS
    elif mode == UI_MODE_CONTRIBUTOR:
        return CANONICAL_SAFE_FIELDS | CONTRIBUTOR_VISIBLE_FIELDS
    elif mode == UI_MODE_ADMIN:
        return (
            CANONICAL_SAFE_FIELDS 
            | CONTRIBUTOR_VISIBLE_FIELDS 
            | ADMIN_VISIBLE_FIELDS
        )
    else:
        # Default to read mode for safety
        return CANONICAL_SAFE_FIELDS


def apply_visibility(
    data: Union[Dict[str, Any], List[Dict[str, Any]]], 
    mode: str
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Apply mode-aware visibility filtering to response data.
    
    This function filters response data based on UI mode WITHOUT:
    - Mutating source objects
    - Affecting data retrieval
    - Influencing evaluation or canonical state
    
    IMPORTANT:
    - Filtering is non-destructive (creates a copy)
    - Filtering is reversible (switching modes retrieves same underlying data)
    - Filtering is presentation-only (does not affect truth)
    
    Args:
        data: Response data (dict or list of dicts)
        mode: UI mode (read, contributor, or admin)
        
    Returns:
        Filtered copy of data with only visible fields for the mode
    """
    # Validate mode
    if mode not in ALLOWED_UI_MODES:
        mode = DEFAULT_UI_MODE
    
    # Get visible fields for this mode
    visible_fields = get_visible_fields(mode)
    
    # Handle list of objects
    if isinstance(data, list):
        return [_filter_object(obj, visible_fields) for obj in data]
    
    # Handle single object
    return _filter_object(data, visible_fields)


def _filter_object(obj: Dict[str, Any], visible_fields: frozenset) -> Dict[str, Any]:
    """
    Recursively filters fields while creating new dict/list structures.
    Does not mutate the source object's structure, but may share references 
    to leaf values (safe for immutable types like strings/numbers).
    
    Args:
        obj: Object to filter
        visible_fields: Set of allowed field names
        
    Returns:
        Filtered copy of object
    """
    # Create deep copy to avoid mutation
    filtered = {}
    
    for key, value in obj.items():
        # Block always-blocked fields
        if key in ALWAYS_BLOCKED_FIELDS:
            continue
        
        # Include only visible fields
        if key in visible_fields:
            # Recursively filter nested objects
            if isinstance(value, dict):
                filtered[key] = _filter_object(value, visible_fields)
            elif isinstance(value, list):
                filtered[key] = [
                    _filter_object(item, visible_fields) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                filtered[key] = value
    
    return filtered


def validate_contributor_mode_safety(data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> bool:
    """
    Validate that data filtered for contributor mode does not expose threshold-related fields.
    
    This enforces the Contributor Threshold Secrecy invariant:
    - No numeric thresholds
    - No confidence scores
    - No required counts
    - No distance-to-threshold indicators
    
    Args:
        data: Filtered data to validate
        
    Returns:
        True if safe, raises AssertionError if threshold-related fields found
    """
    if isinstance(data, list):
        for item in data:
            _validate_threshold_secrecy_recursive(item)
    else:
        _validate_threshold_secrecy_recursive(data)
    
    return True


def _validate_threshold_secrecy_recursive(obj: Any) -> None:
    """
    Recursively validate that no threshold-related fields exist in object.
    
    Raises AssertionError if any threshold-related field is found.
    """
    if not isinstance(obj, dict):
        return
    
    for key, value in obj.items():
        # Check if key is a threshold-related field
        if key in THRESHOLD_RELATED_FIELDS:
            raise AssertionError(
                f"Contributor mode exposed threshold-related field: {key}. "
                "This violates Contributor Threshold Secrecy invariant."
            )
        
        # Recursively check nested objects
        if isinstance(value, dict):
            _validate_threshold_secrecy_recursive(value)
        elif isinstance(value, list):
            for item in value:
                _validate_threshold_secrecy_recursive(item)

"""
Abuse Signal Collection for Phase-2 Sprint-8.

This module provides observational abuse signal collection for contribution
submissions. It is STRICTLY observational and never affects:
- Contribution acceptance
- Canonical truth
- Evaluation logic

SCOPE (Frozen for Phase-2 Sprint-8):
- Velocity tracking (per-user and per-fingerprint, separated)
- Repetition detection (hash-based, non-blocking)
- Fingerprint correlation (existing fingerprints only)

PHILOSOPHY:
Abuse signals in Phase-2 are "smoke detectors", not fire alarms.
They inform humans and future policy - they never act.

CACHE USAGE:
- Best-effort and observational only
- Loss, eviction, or inconsistency MUST NOT affect truth
- LocMemCache is sufficient; Redis is not required
- No Redis-specific APIs or assumptions
- All cache interactions are wrapped in try/except
- Cache failures are silently tolerated

CONSTRAINTS:
- No DB models
- No blocking logic
- No PII storage
- No new identifiers
- No account linking
"""

import hashlib
import json
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

# Cache key prefixes for abuse signals
VELOCITY_USER_PREFIX = 'abuse:velocity:user:'
VELOCITY_FINGERPRINT_PREFIX = 'abuse:velocity:fp:'
REPETITION_PREFIX = 'abuse:repetition:'
FINGERPRINT_CORRELATION_PREFIX = 'abuse:fp_corr:'

# Time windows (in seconds)
VELOCITY_WINDOW_SECONDS = 60 * 60  # 1 hour (coarse window as required)
REPETITION_WINDOW_SECONDS = 60 * 60  # 1 hour
FINGERPRINT_WINDOW_SECONDS = 60 * 60  # 1 hour


def _compute_payload_signature(contribution_type, subject_ref, payload):
    """
    Compute a deterministic signature for repetition detection.
    
    Uses contribution_type, subject_ref shape, and payload shape.
    Does NOT include user identifiers or fingerprints.
    
    Args:
        contribution_type: The contribution type string
        subject_ref: Subject reference dict
        payload: Payload dict
        
    Returns:
        str: SHA-256 hash of the combined signature
    """
    signature_data = {
        'type': contribution_type,
        'subject_keys': sorted(subject_ref.keys()) if subject_ref else [],
        'payload_keys': sorted(payload.keys()) if payload else [],
    }
    serialized = json.dumps(signature_data, sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()


class AbuseSignalCollector:
    """
    Collects observational abuse signals for contribution submissions.
    
    This class is STRICTLY observational:
    - Never blocks submissions
    - Never affects canonical truth
    - Never affects evaluation
    - All failures are silently tolerated
    
    Usage:
        collector = AbuseSignalCollector()
        collector.record_submission(request, validated_data, contributor_fingerprint)
    """
    
    def record_submission(self, request, validated_data, contributor_fingerprint):
        """
        Record abuse signals for a contribution submission.
        
        This method is safe to call and will never raise exceptions.
        All failures are silently tolerated.
        
        Args:
            request: The HTTP request
            validated_data: Validated contribution data
            contributor_fingerprint: The existing de-identified contributor fingerprint
        """
        try:
            self._record_velocity_signals(request, contributor_fingerprint)
            self._record_repetition_signals(validated_data)
            self._record_fingerprint_correlation(contributor_fingerprint)
        except Exception:
            # Silently tolerate all failures
            # Abuse signals are observational only
            pass
    
    def _record_velocity_signals(self, request, contributor_fingerprint):
        """
        Record velocity signals (submission rate tracking).
        
        Tracks per-user velocity when authenticated.
        Tracks per-fingerprint velocity for de-identified submissions.
        Never combines user identity and fingerprint identity.
        """
        try:
            # Per-user velocity (authenticated users only)
            if hasattr(request, 'user') and request.user.is_authenticated:
                user_key = f"{VELOCITY_USER_PREFIX}{request.user.id}"
                self._increment_counter(user_key, VELOCITY_WINDOW_SECONDS)
            
            # Per-fingerprint velocity (separate metric, not combined with user)
            if contributor_fingerprint:
                fp_key = f"{VELOCITY_FINGERPRINT_PREFIX}{contributor_fingerprint}"
                self._increment_counter(fp_key, VELOCITY_WINDOW_SECONDS)
        except Exception:
            # Silently tolerate cache failures
            pass
    
    def _record_repetition_signals(self, validated_data):
        """
        Record repetition signals (duplicate payload detection).
        
        Detects repeated submissions with identical:
        - contribution_type
        - subject_ref shape
        - payload shape
        
        Does NOT collapse or reject submissions.
        Does NOT alter idempotency behavior.
        """
        try:
            contribution_type = validated_data.get('contribution_type', '')
            subject_ref = validated_data.get('subject_ref', {})
            payload = validated_data.get('payload', {})
            
            signature = _compute_payload_signature(
                contribution_type, subject_ref, payload
            )
            
            repetition_key = f"{REPETITION_PREFIX}{signature}"
            count = self._increment_counter(repetition_key, REPETITION_WINDOW_SECONDS)
            
            if count and count > 1:
                # Log repetition signal (INFO level, structured, no PII)
                logger.info(
                    'abuse_signal_repetition',
                    extra={
                        'signal_type': 'repetition',
                        'count': count,
                        'contribution_type': contribution_type,
                    }
                )
        except Exception:
            # Silently tolerate failures
            pass
    
    def _record_fingerprint_correlation(self, contributor_fingerprint):
        """
        Record fingerprint correlation signals.
        
        Observes frequency of reuse of the same contributor fingerprint.
        Uses EXISTING de-identified contributor_fingerprint only.
        
        Critical constraints:
        - Fingerprints must remain de-identified
        - No account linking is allowed
        - No contributor resolution is allowed
        - Results are not persisted beyond cache TTL
        """
        try:
            if not contributor_fingerprint:
                return
            
            fp_corr_key = f"{FINGERPRINT_CORRELATION_PREFIX}{contributor_fingerprint}"
            count = self._increment_counter(fp_corr_key, FINGERPRINT_WINDOW_SECONDS)
            
            if count and count > 5:
                # Log high-frequency fingerprint (INFO level, no fingerprint value)
                logger.info(
                    'abuse_signal_fingerprint_frequency',
                    extra={
                        'signal_type': 'fingerprint_frequency',
                        'count': count,
                    }
                )
        except Exception:
            # Silently tolerate failures
            pass
    
    def _increment_counter(self, key, timeout):
        """
        Increment a cache counter with expiration.
        
        Returns the new count, or None if cache fails.
        All cache operations are wrapped in try/except.
        
        Args:
            key: Cache key
            timeout: TTL in seconds
            
        Returns:
            int or None: New count, or None on failure
        """
        try:
            # Try to increment existing counter
            new_value = cache.incr(key)
            return new_value
        except ValueError:
            # Key doesn't exist, initialize it
            try:
                cache.set(key, 1, timeout)
                return 1
            except Exception:
                return None
        except Exception:
            return None


# Module-level singleton for convenience
_collector = AbuseSignalCollector()


def record_contribution_signals(request, validated_data, contributor_fingerprint):
    """
    Record abuse signals for a contribution submission.
    
    This is the primary entry point for abuse signal collection.
    Safe to call from views - never raises, never blocks.
    
    Args:
        request: The HTTP request
        validated_data: Validated contribution data
        contributor_fingerprint: The existing de-identified contributor fingerprint
    """
    _collector.record_submission(request, validated_data, contributor_fingerprint)

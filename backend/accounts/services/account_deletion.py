"""
Account Deletion Service - Sprint-5A/5B (DATA_RIGHTS_V1 Compliance).

This service implements irreversible user account deletion following
DATA_RIGHTS_V1 principles:

1. Identity is optional - Belief formation does not depend on user identity
2. Evidence is permanent - ContributionEvents are NEVER deleted
3. Belief is derived - Canonical belief remains stable across user deletion

WHAT THIS SERVICE DOES:
- Permanently removes user identity and profile data
- Revokes all active sessions and tokens immediately
- De-identifies ContributionEvents (sets contributor=NULL, preserves fingerprint)
- Prevents future authentication for the deleted account
- Creates an audit record WITHOUT personal identifiers

WHAT THIS SERVICE DOES NOT DO (Explicit Non-Goals):
- Delete or modify ContributionEvent evidence payload
- Trigger belief recomputation
- Expose deletion events publicly
- Allow deletion reversal
- Store personal identifiers in audit logs

CRITICAL INVARIANTS:
- Deletion is EXPLICIT and INTENTIONAL
- Deletion is IDEMPOTENT (safe on retry)
- Deletion is TRANSACTIONAL where possible
- All tokens are revoked IMMEDIATELY
- Evidence payload and belief remain INTACT
- contributor_fingerprint is preserved for evaluation (INV-I1, INV-I2)

CONFIGURATION:
- AUDIT_LOG_USER_ID_SALT: Optional setting for a dedicated salt used when hashing
  user IDs for audit logs. If not set, an HMAC-derived salt from SECRET_KEY is used.
  Setting a dedicated salt provides additional security isolation.
"""

import hashlib
import hmac
import logging
from dataclasses import dataclass
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeletionResult:
    """
    Result of an account deletion operation.

    Immutable dataclass containing deletion outcome information.
    Does NOT contain any personal identifiers.
    """

    success: bool
    deleted_at: Optional[str]  # ISO timestamp
    tokens_revoked: int
    error: Optional[str] = None

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "success": self.success,
            "deleted_at": self.deleted_at,
            "tokens_revoked": self.tokens_revoked,
            "error": self.error,
        }


class AccountDeletionService:
    """
    Service for irreversible user account deletion.

    This service implements DATA_RIGHTS_V1 compliant account deletion.
    Once deleted, an account cannot be recovered.

    Usage:
        service = AccountDeletionService()
        result = service.delete_account(user)
        if result.success:
            # Account deleted successfully
            pass

    SECURITY NOTES:
    - Always verify user identity before calling delete_account
    - Log the intention to delete (without PII) for audit purposes
    - This operation is FINAL and cannot be undone

    CONCURRENCY NOTES:
    - Uses database transactions to ensure atomicity
    - Safe to call multiple times (idempotent)
    - Handles race conditions with token creation during deletion
    """

    def __init__(self):
        """Initialize the account deletion service."""
        pass

    def delete_account(
        self,
        user,
        ip_address: Optional[str] = None,
        user_agent: str = "",
        reason: str = "user_initiated",
    ) -> DeletionResult:
        """
        Permanently delete a user account.

        This method:
        1. Revokes all refresh tokens
        2. De-identifies ContributionEvents (sets contributor=NULL)
        3. Clears user profile/identity data
        4. Deactivates the user account
        5. Logs an audit entry (without PII)

        Args:
            user: The User instance to delete
            ip_address: IP address of the deletion request (for audit)
            user_agent: User agent string (for audit)
            reason: Reason for deletion (default: 'user_initiated')

        Returns:
            DeletionResult with success status and metadata

        Note:
            ContributionEvent evidence payloads are NOT modified.
            Only the contributor FK is set to NULL.
            contributor_fingerprint is preserved for evaluation semantics.

        IDEMPOTENCY:
            If user is already deleted (is_active=False), returns success
            with tokens_revoked=0.
        """
        # Handle already deleted users (idempotent)
        if not user.is_active:
            return DeletionResult(
                success=True,
                deleted_at=None,  # Already deleted, no timestamp
                tokens_revoked=0,
                error=None,
            )

        try:
            with transaction.atomic():
                # Step 1: Revoke all refresh tokens FIRST
                # This ensures no new access tokens can be obtained
                tokens_revoked = self._revoke_all_tokens(user)

                # Step 2: De-identify ContributionEvents (Sprint-5B)
                # Set contributor=NULL while preserving contributor_fingerprint
                # This removes identity without affecting evaluation semantics
                contributions_deidentified = self._deidentify_contributions(user)

                # Step 3: Clear user identity and profile data
                self._clear_user_identity(user)

                # Step 4: Deactivate the user account
                deletion_time = timezone.now()
                self._deactivate_user(user, deletion_time)

                # Step 5: Log audit entry (no PII)
                user_id_hash = self._hash_user_id(str(user.id))
                self._log_deletion_audit(
                    user_id_hash=user_id_hash,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    reason=reason,
                )

            logger.info(
                "Account deletion completed",
                extra={
                    "user_id_hash": user_id_hash,  # For correlation with audit log
                    "tokens_revoked": tokens_revoked,
                    "contributions_deidentified": contributions_deidentified,
                    "reason": reason,
                },
            )

            return DeletionResult(
                success=True,
                deleted_at=deletion_time.isoformat(),
                tokens_revoked=tokens_revoked,
                error=None,
            )

        except Exception as e:
            logger.exception("Account deletion failed")
            return DeletionResult(
                success=False,
                deleted_at=None,
                tokens_revoked=0,
                error=str(e),
            )

    def _deidentify_contributions(self, user) -> int:
        """
        De-identify all ContributionEvents for a user (Sprint-5B).

        This method sets contributor=NULL on all ContributionEvents where
        contributor=user, while preserving contributor_fingerprint.

        DATA_RIGHTS_V1 compliance:
        - Evidence payload is NOT modified (PH-1: Evidence is permanent)
        - Only the contributor FK is nullified (PH-2: Identity is optional)
        - contributor_fingerprint is preserved for evaluation (PH-4: Replay determinism)

        INVARIANTS PRESERVED:
        - INV-E1: ContributionEvent payload is immutable (only FK changed)
        - INV-I1: Independence is counted via contributor_fingerprint, not FK
        - INV-I2: Deletion does not change contributor counts

        Args:
            user: User instance whose contributions should be de-identified

        Returns:
            Number of contributions de-identified
        """
        from core.models import ContributionEvent

        # Update all contributions to set contributor=NULL
        # contributor_fingerprint is already set and immutable
        count = ContributionEvent.objects.filter(contributor=user).update(
            contributor=None
        )

        logger.info(
            "Contributions de-identified",
            extra={
                "count": count,
            },
        )

        return count

    def _revoke_all_tokens(self, user) -> int:
        """
        Revoke all refresh tokens for a user.

        Args:
            user: User instance

        Returns:
            Number of tokens revoked
        """
        from accounts.models import RefreshToken

        # Get count before revoking
        tokens_to_revoke = RefreshToken.objects.filter(
            user=user,
            revoked=False,
        ).count()

        # Revoke all tokens using the model's method
        RefreshToken.revoke_all_for_user(user)

        return tokens_to_revoke

    def _clear_user_identity(self, user) -> None:
        """
        Clear all personally identifiable information from the user.

        DATA_RIGHTS_V1 Section 3.1 (Identity & Access Data):
        "Must be fully deleted or irreversibly anonymized upon user request"

        DATA_RIGHTS_V1 Section 3.2 (Profile & Preference Data):
        "Must be fully deleted upon user request"

        This method:
        - Clears email (set to anonymized placeholder)
        - Clears display_name
        - Clears username (set to anonymized placeholder)
        - Clears privacy consent information
        - Sets public_profile to False

        Args:
            user: User instance to anonymize
        """
        # Derive a purpose-specific salt using HMAC to avoid exposing SECRET_KEY directly.
        # This provides cryptographic isolation between different uses of secrets.
        derived_salt = hmac.new(
            key=settings.SECRET_KEY.encode("utf-8"),
            msg=b"account_deletion_anonymization",
            digestmod=hashlib.sha256,
        ).hexdigest()

        # Generate anonymized identifiers using the derived salt
        # This remains deterministic for a given deployment but is not reproducible
        # by attackers who do not know the secret key, preventing correlation attacks.
        salted_input = f"{derived_salt}:{str(user.id)}"
        id_hash = hashlib.sha256(salted_input.encode("utf-8")).hexdigest()[:16]
        anonymized_username = f"deleted_{id_hash}"
        anonymized_email = f"deleted_{id_hash}@deleted.invalid"

        # Clear profile/identity data
        user.email = anonymized_email
        user.username = anonymized_username
        user.display_name = ""
        user.first_name = ""
        user.last_name = ""

        # Clear privacy consent info
        user.privacy_consent_version = None
        user.privacy_consent_ts = None

        # Hide profile
        user.public_profile = False

        # Clear email verification status
        user.email_verified = False

        # Save changes
        user.save(
            update_fields=[
                "email",
                "username",
                "display_name",
                "first_name",
                "last_name",
                "privacy_consent_version",
                "privacy_consent_ts",
                "public_profile",
                "email_verified",
            ]
        )

    def _deactivate_user(self, user, deletion_time) -> None:
        """
        Deactivate the user account.

        This prevents the user from logging in ever again.

        Args:
            user: User instance to deactivate
            deletion_time: Timestamp of deletion
        """
        user.is_active = False

        # Clear password to prevent login attempts
        # set_unusable_password() is Django's recommended approach
        user.set_unusable_password()

        # Record when the account was deleted
        # We could add a deleted_at field, but is_active is sufficient for Phase-1
        user.save(update_fields=["is_active", "password"])

    def _hash_user_id(self, user_id: str) -> str:
        """
        Create a one-way hash of the user ID for audit purposes.
        This hash is distinct from the actual user ID, making it impractical to recover the
        original ID from the hash.

        Args:
            user_id: String representation of user ID

        Returns:
            Salted SHA256 hash of the user ID (first 16 hex characters)
        """
        # Check for explicit salt setting first
        explicit_salt = getattr(settings, "AUDIT_LOG_USER_ID_SALT", None)

        if explicit_salt:
            salt = explicit_salt
        else:
            # Derive a purpose-specific salt using HMAC to avoid exposing SECRET_KEY directly.
            # This provides cryptographic isolation between different uses of secrets.
            salt = hmac.new(
                key=settings.SECRET_KEY.encode("utf-8"),
                msg=b"audit_log_user_id_hash",
                digestmod=hashlib.sha256,
            ).hexdigest()

        data = f"{salt}:{user_id}".encode("utf-8")
        return hashlib.sha256(data).hexdigest()[:16]

    def _log_deletion_audit(
        self,
        user_id_hash: str,
        ip_address: Optional[str],
        user_agent: str,
        reason: str,
    ) -> None:
        """
        Log an audit entry for the account deletion.

        DATA_RIGHTS_V1 Section 9 (Audit & Governance):
        "Audit records must:
         - Contain no personal identifiers
         - Never re-enable re-identification
         - Be used only for governance and safety"

        Args:
            user_id_hash: Hashed user ID (not reversible)
            ip_address: IP address of the deletion request
            user_agent: User agent string
            reason: Reason for deletion
        """
        from core.models import AuditLog

        # Log WITHOUT personal identifiers
        # We use a hash of the user ID, not the actual ID
        AuditLog.log(
            action="account.deleted",
            actor_user=None,  # DO NOT store the user reference
            object_type="User",
            object_id=user_id_hash,  # Hashed ID, not actual ID
            ip_address=ip_address,
            user_agent=user_agent,
            detail={
                "reason": reason,
                # DO NOT include: email, username, display_name, etc.
            },
        )

    def can_delete(self, user) -> tuple[bool, Optional[str]]:
        """
        Check if a user account can be deleted.

        For Phase-1, all authenticated users can delete their accounts.
        This method exists for future extensibility (e.g., preventing
        deletion of moderator accounts without handoff).

        Args:
            user: User instance to check

        Returns:
            Tuple of (can_delete: bool, reason: Optional[str])
        """
        if not user.is_active:
            return False, "Account is already deleted"

        return True, None

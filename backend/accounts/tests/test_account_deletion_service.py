"""
Tests for Account Deletion Service (Sprint-5A).

These tests verify DATA_RIGHTS_V1 compliance for user account deletion:

1. Deleted users cannot authenticate (tokens revoked)
2. Tokens are revoked immediately
3. Canonical Stops remain unchanged after deletion
4. Deletion is irreversible
5. Evidence (ContributionEvents) is preserved

TESTING PHILOSOPHY:
Account deletion is a critical, irreversible operation that must:
- Respect user data rights (DATA_RIGHTS_V1)
- Preserve system integrity (evidence and belief)
- Be safe to retry (idempotent)
- Never leak personal information via audit logs
"""

import uuid
from datetime import timedelta

from accounts.models import RefreshToken
from accounts.services.account_deletion import AccountDeletionService, DeletionResult
from core.models import AuditLog, ContributionEvent
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import TestCase
from django.utils import timezone

User = get_user_model()


class AccountDeletionServiceTests(TestCase):
    """Core tests for AccountDeletionService."""

    def setUp(self):
        """Create test user and service instance."""
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="testpassword123",
            display_name="Test User",
            first_name="Test",
            last_name="User",
        )
        self.service = AccountDeletionService()

    def test_delete_account_returns_success(self):
        """Test that account deletion returns a successful result."""
        result = self.service.delete_account(self.user)

        self.assertIsInstance(result, DeletionResult)
        self.assertTrue(result.success)
        self.assertIsNotNone(result.deleted_at)
        self.assertIsNone(result.error)

    def test_delete_account_deactivates_user(self):
        """Test that deleted user is deactivated (is_active=False)."""
        self.assertTrue(self.user.is_active)

        self.service.delete_account(self.user)

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_delete_account_clears_email(self):
        """Test that email is anonymized after deletion."""
        original_email = self.user.email

        self.service.delete_account(self.user)

        self.user.refresh_from_db()
        self.assertNotEqual(self.user.email, original_email)
        self.assertIn("deleted_", self.user.email)
        self.assertTrue(self.user.email.endswith("@deleted.invalid"))

    def test_delete_account_clears_display_name(self):
        """Test that display_name is anonymized after deletion."""
        self.assertEqual(self.user.display_name, "Test User")

        self.service.delete_account(self.user)

        self.user.refresh_from_db()
        # Display name is cleared (the User.save() method may set it to the
        # anonymized username, but the original personal display name is gone)
        self.assertNotEqual(self.user.display_name, "Test User")

    def test_delete_account_clears_name_fields(self):
        """Test that first_name and last_name are cleared after deletion."""
        self.service.delete_account(self.user)

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "")
        self.assertEqual(self.user.last_name, "")

    def test_delete_account_sets_unusable_password(self):
        """Test that password becomes unusable after deletion."""
        self.assertTrue(self.user.has_usable_password())

        self.service.delete_account(self.user)

        self.user.refresh_from_db()
        self.assertFalse(self.user.has_usable_password())

    def test_delete_account_clears_privacy_consent(self):
        """Test that privacy consent data is cleared after deletion."""
        self.user.privacy_consent_version = "1.0"
        self.user.privacy_consent_ts = timezone.now()
        self.user.save()

        self.service.delete_account(self.user)

        self.user.refresh_from_db()
        self.assertIsNone(self.user.privacy_consent_version)
        self.assertIsNone(self.user.privacy_consent_ts)


class TokenRevocationTests(TestCase):
    """Tests for token revocation during account deletion."""

    def setUp(self):
        """Create test user with refresh tokens."""
        self.user = User.objects.create_user(
            username="tokenuser",
            email="tokenuser@example.com",
            password="testpassword123",
        )
        self.service = AccountDeletionService()

        # Create multiple refresh tokens
        self.tokens = []
        for _ in range(3):
            token_obj, _ = RefreshToken.create_for_user(self.user)
            self.tokens.append(token_obj)

    def test_tokens_revoked_immediately_on_deletion(self):
        """Test that all tokens are revoked when account is deleted."""
        # Verify tokens are valid before deletion
        for token in self.tokens:
            token.refresh_from_db()
            self.assertFalse(token.revoked)

        # Delete account
        result = self.service.delete_account(self.user)

        # Verify all tokens are revoked
        for token in self.tokens:
            token.refresh_from_db()
            self.assertTrue(token.revoked)

        # Verify count in result
        self.assertEqual(result.tokens_revoked, 3)

    def test_deleted_user_cannot_authenticate(self):
        """Test that deleted user cannot use existing tokens to authenticate."""
        # Create a token and get the raw value
        _, raw_token = RefreshToken.create_for_user(self.user)

        # Verify token is valid before deletion
        token_obj = RefreshToken.verify_and_get(raw_token)
        self.assertTrue(token_obj.is_valid())

        # Delete account
        self.service.delete_account(self.user)

        # Verify token is no longer valid
        with self.assertRaises(ValueError) as context:
            RefreshToken.verify_and_get(raw_token)

        self.assertIn("revoked", str(context.exception).lower())

    def test_no_tokens_to_revoke_returns_zero(self):
        """Test that deletion with no tokens returns zero tokens revoked."""
        # Create user without tokens
        new_user = User.objects.create_user(
            username="notokenuser",
            email="notokenuser@example.com",
            password="testpassword123",
        )

        result = self.service.delete_account(new_user)

        self.assertTrue(result.success)
        self.assertEqual(result.tokens_revoked, 0)


class DeletionIdempotencyTests(TestCase):
    """Tests for idempotent deletion behavior."""

    def setUp(self):
        """Create test user."""
        self.user = User.objects.create_user(
            username="idempotentuser",
            email="idempotent@example.com",
            password="testpassword123",
        )
        self.service = AccountDeletionService()

    def test_deletion_is_idempotent(self):
        """Test that deleting an already deleted user succeeds silently."""
        # First deletion
        result1 = self.service.delete_account(self.user)
        self.assertTrue(result1.success)

        # Second deletion (should also succeed)
        result2 = self.service.delete_account(self.user)
        self.assertTrue(result2.success)
        self.assertEqual(result2.tokens_revoked, 0)  # No tokens to revoke

    def test_can_delete_returns_false_for_deleted_user(self):
        """Test that can_delete returns False for already deleted users."""
        # Delete the user first
        self.service.delete_account(self.user)

        # Check can_delete
        can_delete, reason = self.service.can_delete(self.user)
        self.assertFalse(can_delete)
        self.assertIn("already deleted", reason.lower())


class DeletionIrreversibilityTests(TestCase):
    """Tests for deletion irreversibility."""

    def setUp(self):
        """Create test user."""
        self.user = User.objects.create_user(
            username="irreversibleuser",
            email="irreversible@example.com",
            password="testpassword123",
        )
        self.service = AccountDeletionService()

    def test_deleted_user_cannot_login_with_password(self):
        """Test that deleted user cannot authenticate with their old password."""
        # Verify user can authenticate before deletion
        self.assertTrue(self.user.check_password("testpassword123"))

        # Delete account
        self.service.delete_account(self.user)

        # Refresh user from database
        self.user.refresh_from_db()

        # User should have unusable password
        self.assertFalse(self.user.has_usable_password())
        self.assertFalse(self.user.check_password("testpassword123"))

    def test_deleted_user_is_inactive(self):
        """Test that deleted user's is_active is False."""
        self.service.delete_account(self.user)

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_original_email_is_not_recoverable(self):
        """Test that original email cannot be determined after deletion."""
        original_email = "irreversible@example.com"

        self.service.delete_account(self.user)

        self.user.refresh_from_db()

        # Email should not match original
        self.assertNotEqual(self.user.email, original_email)

        # Email should be anonymized
        self.assertNotIn("@example.com", self.user.email)


class EvidencePreservationTests(TestCase):
    """Tests for evidence preservation during account deletion."""

    def setUp(self):
        """Create test user with contribution events."""
        self.user = User.objects.create_user(
            username="contributoruser",
            email="contributor@example.com",
            password="testpassword123",
        )
        self.service = AccountDeletionService()

        # Create contribution events
        self.contributions = []
        for i in range(3):
            contribution = ContributionEvent.objects.create(
                client_generated_id=uuid.uuid4(),
                contributor=self.user,
                contributor_fingerprint=self.user.id,  # Sprint-5B
                contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
                subject_ref={"lat": 40.7128 + i * 0.01, "lon": -74.0060},
                payload={"confidence": "high", "notes": f"Contribution {i}"},
                observed_at=timezone.now() - timedelta(hours=i),
            )
            self.contributions.append(contribution)

    def test_contribution_events_preserved_after_deletion(self):
        """Test that ContributionEvents remain after account deletion."""
        contribution_ids = [c.id for c in self.contributions]

        # Delete account
        self.service.delete_account(self.user)

        # Verify all contributions still exist
        for contribution_id in contribution_ids:
            contribution = ContributionEvent.objects.get(id=contribution_id)
            self.assertIsNotNone(contribution)

    def test_contribution_event_count_unchanged_after_deletion(self):
        """Test that the number of ContributionEvents is unchanged after deletion."""
        contribution_ids = [c.id for c in self.contributions]
        count_before = ContributionEvent.objects.filter(id__in=contribution_ids).count()
        self.assertEqual(len(contribution_ids), 3)
        self.assertEqual(count_before, 3)

        # Delete account
        self.service.delete_account(self.user)

        # Count should still be 3 (contributions preserved, just de-identified)
        count_after = ContributionEvent.objects.filter(id__in=contribution_ids).count()
        self.assertEqual(count_after, count_before)

        # Verify contributor FK is now NULL (de-identified)
        for contribution_id in contribution_ids:
            contribution = ContributionEvent.objects.get(id=contribution_id)
            self.assertIsNone(contribution.contributor)
            # But fingerprint is preserved
            self.assertIsNotNone(contribution.contributor_fingerprint)

    def test_contribution_payloads_intact_after_deletion(self):
        """Test that contribution payloads are not modified during deletion."""
        # Store original payloads
        original_payloads = [c.payload.copy() for c in self.contributions]

        # Delete account
        self.service.delete_account(self.user)

        # Verify payloads are unchanged
        for i, contribution in enumerate(self.contributions):
            contribution.refresh_from_db()
            self.assertEqual(contribution.payload, original_payloads[i])


class CanonicalStabilityTests(TestCase):
    """Tests for canonical entity stability during account deletion."""

    def setUp(self):
        """Create test user and canonical Stop."""
        self.user = User.objects.create_user(
            username="canonicaluser",
            email="canonical@example.com",
            password="testpassword123",
        )
        self.service = AccountDeletionService()

    def test_canonical_stops_unchanged_after_deletion(self):
        """Test that canonical Stops remain unchanged after user deletion."""
        # Import Stop model
        from transit.models import Stop

        # Create a canonical Stop using internal save (mimicking what evaluation would produce)
        stop = Stop(
            public_id="stop-test-001",
            name="Test Stop",
            location=Point(-74.0060, 40.7128),
            belief_state=Stop.BeliefState.ACTIVE_HIGH,
        )
        stop._internal_save()

        # Also create a contribution from this user
        ContributionEvent.objects.create(
            client_generated_id=uuid.uuid4(),
            contributor=self.user,
            contributor_fingerprint=self.user.id,  # Sprint-5B
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            subject_ref={"lat": 40.7128, "lon": -74.0060},
            payload={"confidence": "high"},
            observed_at=timezone.now(),
        )

        # Store original Stop data
        original_stop_data = {
            "id": stop.id,
            "public_id": stop.public_id,
            "name": stop.name,
            "belief_state": stop.belief_state,
        }

        # Delete account
        self.service.delete_account(self.user)

        # Verify Stop is unchanged
        stop.refresh_from_db()
        self.assertEqual(stop.id, original_stop_data["id"])
        self.assertEqual(stop.public_id, original_stop_data["public_id"])
        self.assertEqual(stop.name, original_stop_data["name"])
        self.assertEqual(stop.belief_state, original_stop_data["belief_state"])

    def test_no_belief_recomputation_triggered(self):
        """
        Test that account deletion does not trigger belief recomputation.

        This is verified by checking that no new evaluation-related database
        operations occur during deletion.

        Note: In a full implementation, we might check that no evaluation
        signals are fired. For Sprint-5A, we verify by checking that
        canonical entities remain unchanged.
        """
        # Import Stop model
        from transit.models import Stop

        # Create multiple Stops using internal save
        stops = []
        for i in range(3):
            stop = Stop(
                public_id=f"stop-recompute-{i}",
                name=f"Recompute Test Stop {i}",
                location=Point(-74.0060 + i * 0.01, 40.7128),
                belief_state=Stop.BeliefState.ACTIVE_LOW,
            )
            stop._internal_save()
            stops.append(stop)

        # Store original version numbers
        original_versions = [s.version for s in stops]

        # Delete account
        self.service.delete_account(self.user)

        # Verify version numbers are unchanged (no recomputation)
        for i, stop in enumerate(stops):
            stop.refresh_from_db()
            self.assertEqual(stop.version, original_versions[i])


class AuditLogTests(TestCase):
    """Tests for audit logging during account deletion."""

    def setUp(self):
        """Create test user."""
        self.user = User.objects.create_user(
            username="audituser",
            email="audit@example.com",
            password="testpassword123",
        )
        self.user_id = str(self.user.id)
        self.service = AccountDeletionService()

    def test_deletion_creates_audit_log(self):
        """Test that account deletion creates an audit log entry."""
        initial_count = AuditLog.objects.filter(action="account.deleted").count()

        self.service.delete_account(self.user)

        final_count = AuditLog.objects.filter(action="account.deleted").count()
        self.assertEqual(final_count, initial_count + 1)

    def test_audit_log_does_not_contain_user_reference(self):
        """Test that audit log does not store direct user reference."""
        self.service.delete_account(self.user)

        audit_entry = AuditLog.objects.filter(action="account.deleted").latest(
            "created_at"
        )

        # actor_user should be None (no direct reference)
        self.assertIsNone(audit_entry.actor_user)

    def test_audit_log_does_not_contain_email(self):
        """Test that audit log does not contain the user's email."""
        original_email = self.user.email

        self.service.delete_account(self.user)

        audit_entry = AuditLog.objects.filter(action="account.deleted").latest(
            "created_at"
        )

        # Verify email is not in any audit field
        self.assertNotIn(original_email, str(audit_entry.detail))
        self.assertNotEqual(audit_entry.object_id, original_email)

    def test_audit_log_uses_hashed_user_id(self):
        """Test that audit log uses a hashed version of user ID."""
        self.service.delete_account(self.user)

        audit_entry = AuditLog.objects.filter(action="account.deleted").latest(
            "created_at"
        )

        # object_id should be a hash, not the actual UUID
        self.assertNotEqual(audit_entry.object_id, self.user_id)
        # Hash should be a 16-character truncated SHA-256 hex string (64 bits).
        # 64 bits of entropy is acceptable for our audit-log scale: even with tens of
        # millions of entries, the birthday-bound collision probability remains
        # negligible for our threat model while keeping the identifier compact.
        self.assertEqual(len(audit_entry.object_id), 16)

    def test_audit_log_captures_ip_address(self):
        """Test that audit log captures IP address when provided."""
        self.service.delete_account(
            self.user,
            ip_address="192.168.1.100",
        )

        audit_entry = AuditLog.objects.filter(action="account.deleted").latest(
            "created_at"
        )
        self.assertEqual(audit_entry.ip_address, "192.168.1.100")

    def test_audit_log_captures_reason(self):
        """Test that audit log captures deletion reason."""
        self.service.delete_account(
            self.user,
            reason="user_requested",
        )

        audit_entry = AuditLog.objects.filter(action="account.deleted").latest(
            "created_at"
        )
        self.assertEqual(audit_entry.detail.get("reason"), "user_requested")


class DeletionResultTests(TestCase):
    """Tests for DeletionResult dataclass."""

    def test_deletion_result_to_dict(self):
        """Test that DeletionResult can be converted to dict."""
        result = DeletionResult(
            success=True,
            deleted_at="2025-12-28T10:00:00+00:00",
            tokens_revoked=5,
            error=None,
        )

        result_dict = result.to_dict()

        self.assertEqual(result_dict["success"], True)
        self.assertEqual(result_dict["deleted_at"], "2025-12-28T10:00:00+00:00")
        self.assertEqual(result_dict["tokens_revoked"], 5)
        self.assertIsNone(result_dict["error"])

    def test_deletion_result_is_immutable(self):
        """Test that DeletionResult is frozen (immutable)."""
        result = DeletionResult(
            success=True,
            deleted_at="2025-12-28T10:00:00+00:00",
            tokens_revoked=5,
        )

        with self.assertRaises(Exception):  # FrozenInstanceError
            result.success = False

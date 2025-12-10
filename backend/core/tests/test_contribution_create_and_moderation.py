"""
Tests for Contribution and Moderation models.

Verifies:
- Contribution creation via create_from_request
- Idempotency key handling
- Status workflow
- Moderation entry creation
- apply_moderation method
"""

from django.test import TestCase

from core.models import Contribution, Developer, User


class ContributionModelTestCase(TestCase):
    """Test cases for the Contribution model."""

    def setUp(self):
        """Create test user and developer for contribution tests."""
        self.user = User.objects.create_user(
            username="contributor",
            email="contributor@example.com",
            password="testpass123",
        )

        self.developer = Developer.objects.create(
            name="Test Developer",
            contact_email="dev@example.com",
            verified=True,
            tier=Developer.TIER_BASIC,
        )

    def test_create_contribution_from_user(self):
        """Test creating a contribution from an authenticated user."""
        contribution, created = Contribution.create_from_request(
            contribution_type="route_update",
            payload={"route_id": "123", "changes": {"name": "New Route Name"}},
            user=self.user,
            source_type=Contribution.SOURCE_UI,
        )

        self.assertTrue(created)
        self.assertIsNotNone(contribution.id)
        self.assertEqual(contribution.type, "route_update")
        self.assertEqual(contribution.submitted_by, self.user)
        self.assertEqual(contribution.source_type, Contribution.SOURCE_UI)
        self.assertEqual(contribution.status, Contribution.STATUS_PENDING)
        self.assertEqual(contribution.points_awarded, 0)

    def test_create_contribution_from_developer(self):
        """Test creating a contribution via developer API."""
        contribution, created = Contribution.create_from_request(
            contribution_type="stop_edit",
            payload={"stop_id": "456", "lat": 40.7128, "lon": -74.0060},
            developer=self.developer,
            external_user_id="external_user_123",
            source_type=Contribution.SOURCE_API,
            idempotency_key="unique-key-123",
        )

        self.assertTrue(created)
        self.assertEqual(contribution.submitted_by_developer, self.developer)
        self.assertEqual(contribution.external_user_id, "external_user_123")
        self.assertEqual(contribution.idempotency_key, "unique-key-123")

    def test_create_contribution_requires_attribution(self):
        """Test that create_from_request requires at least one attribution source."""
        with self.assertRaises(ValueError) as context:
            Contribution.create_from_request(
                contribution_type="route_update", payload={"test": "data"}
            )

        self.assertIn("attribution", str(context.exception).lower())

    def test_contribution_status_workflow(self):
        """Test contribution status changes."""
        contribution, _ = Contribution.create_from_request(
            contribution_type="schedule_change",
            payload={"schedule": "data"},
            user=self.user,
        )

        self.assertEqual(contribution.status, Contribution.STATUS_PENDING)

        # Change to approved
        contribution.status = Contribution.STATUS_APPROVED
        contribution.save()

        contribution.refresh_from_db()
        self.assertEqual(contribution.status, Contribution.STATUS_APPROVED)


class ModerationTestCase(TestCase):
    """Test cases for moderation workflow."""

    def setUp(self):
        """Create test data for moderation tests."""
        self.contributor = User.objects.create_user(
            username="contributor",
            email="contributor@example.com",
            password="testpass123",
        )

        self.moderator = User.objects.create_user(
            username="moderator", email="moderator@example.com", password="testpass123"
        )

        self.contribution, _ = Contribution.create_from_request(
            contribution_type="route_update",
            payload={"route_id": "789", "update": "data"},
            user=self.contributor,
        )

    def test_apply_moderation_approve(self):
        """Test approving a contribution via apply_moderation."""
        moderation_entry = self.contribution.apply_moderation(
            action="approve", moderator=self.moderator, reason="Looks good"
        )

        # Verify moderation entry created
        self.assertIsNotNone(moderation_entry)
        self.assertEqual(moderation_entry.contribution, self.contribution)
        self.assertEqual(moderation_entry.moderator, self.moderator)
        self.assertEqual(moderation_entry.action, "approve")
        self.assertEqual(moderation_entry.reason, "Looks good")
        self.assertEqual(moderation_entry.previous_status, Contribution.STATUS_PENDING)
        self.assertEqual(moderation_entry.new_status, Contribution.STATUS_APPROVED)

        # Verify contribution status updated
        self.contribution.refresh_from_db()
        self.assertEqual(self.contribution.status, Contribution.STATUS_APPROVED)

    def test_apply_moderation_reject(self):
        """Test rejecting a contribution."""
        moderation_entry = self.contribution.apply_moderation(
            action="reject", moderator=self.moderator, reason="Invalid data"
        )

        self.assertEqual(moderation_entry.action, "reject")
        self.contribution.refresh_from_db()
        self.assertEqual(self.contribution.status, Contribution.STATUS_REJECTED)

    def test_apply_moderation_flag(self):
        """Test flagging a contribution for review."""
        moderation_entry = self.contribution.apply_moderation(
            action="flag",
            moderator=self.moderator,
            reason="Needs additional review",
            metadata={"flag_type": "quality_check"},
        )

        self.assertEqual(moderation_entry.action, "flag")
        self.assertEqual(moderation_entry.metadata["flag_type"], "quality_check")
        self.contribution.refresh_from_db()
        self.assertEqual(self.contribution.status, Contribution.STATUS_FLAGGED)

    def test_apply_moderation_invalid_action(self):
        """Test that invalid moderation action raises error."""
        with self.assertRaises(ValueError) as context:
            self.contribution.apply_moderation(
                action="invalid_action", moderator=self.moderator
            )

        self.assertIn("Invalid moderation action", str(context.exception))

    def test_moderation_log_relationship(self):
        """Test that moderation entries are accessible from contribution."""
        # Create multiple moderation entries
        self.contribution.apply_moderation(
            action="flag", moderator=self.moderator, reason="First review"
        )

        self.contribution.apply_moderation(
            action="approve", moderator=self.moderator, reason="Approved after review"
        )

        # Verify we can access moderation log
        log_entries = self.contribution.moderation_log.all()
        self.assertEqual(log_entries.count(), 2)
        self.assertEqual(log_entries[0].action, "approve")  # Most recent first
        self.assertEqual(log_entries[1].action, "flag")

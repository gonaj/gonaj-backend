"""
Comprehensive tests for contribution export functionality (Sprint-5C).

Tests cover DATA_RIGHTS_V1 compliance for the export endpoint:
- INV-D1: No system-internal identifiers exposed
- INV-D2: No cross-contribution linkage beyond timestamps
- INV-D3: No weakening of post-deletion anonymity
- INV-D4: No leaking contributor_fingerprint

TEST MATRIX:
1. Happy path: User can export their contributions
2. Security: Deleted users cannot export (403)
3. Privacy: No internal identifiers in export
4. Stability: Export is deterministic
5. Empty state: Export works with no contributions
"""

import uuid
from datetime import timedelta

from api.utils.tokens import create_access_token
from core.models import ContributionEvent, User
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient


class ContributionExportTestCase(TestCase):
    """Tests for GET /api/auth/me/contributions/export."""

    def setUp(self):
        """Create test user and client."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="exportuser",
            email="export@example.com",
            password="testpass123",
        )
        access_data = create_access_token(self.user)
        self.access_token = access_data["access_token"]

    def test_export_requires_authentication(self):
        """Test that export endpoint requires authentication."""
        response = self.client.get("/api/auth/me/contributions/export")
        # In this project, unauthenticated requests to views protected by
        # IsAuthenticated return 403 Forbidden (given the configured
        # authentication classes, e.g. SessionAuthentication), so we assert
        # 403 here rather than the more typical 401 Unauthorized.
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_export_empty_contributions(self):
        """Test export works when user has no contributions."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        response = self.client.get("/api/auth/me/contributions/export")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["export_version"], "1.0")
        self.assertEqual(response.data["contribution_count"], 0)
        self.assertEqual(response.data["contributions"], [])

    def test_export_includes_user_contributions(self):
        """Test that export returns user's contributions."""
        # Create contributions for user
        observed_time = timezone.now() - timedelta(hours=1)
        contribution = ContributionEvent.objects.create(
            contributor=self.user,
            contribution_type="stop_exists",
            subject_ref={"lat": 40.7128, "lon": -74.0060},
            payload={"name": "Test Stop", "confidence": "high"},
            contributor_fingerprint=self.user.id,
            client_generated_id=uuid.uuid4(),
            observed_at=observed_time,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get("/api/auth/me/contributions/export")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["contribution_count"], 1)
        self.assertEqual(len(response.data["contributions"]), 1)

        exported = response.data["contributions"][0]
        self.assertEqual(exported["contribution_type"], "stop_exists")
        self.assertEqual(exported["subject_ref"], {"lat": 40.7128, "lon": -74.0060})
        self.assertEqual(
            exported["payload"], {"name": "Test Stop", "confidence": "high"}
        )

    def test_export_excludes_other_users_contributions(self):
        """Test that export only returns the authenticated user's contributions."""
        other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="testpass123",
        )
        observed_time = timezone.now() - timedelta(hours=1)

        # Create contribution for other user
        ContributionEvent.objects.create(
            contributor=other_user,
            contribution_type="stop_exists",
            subject_ref={"lat": 40.0, "lon": -74.0},
            payload={"name": "Other Stop"},
            contributor_fingerprint=other_user.id,
            client_generated_id=uuid.uuid4(),
            observed_at=observed_time,
        )

        # Create contribution for test user
        ContributionEvent.objects.create(
            contributor=self.user,
            contribution_type="stop_exists",
            subject_ref={"lat": 41.0, "lon": -73.0},
            payload={"name": "My Stop"},
            contributor_fingerprint=self.user.id,
            client_generated_id=uuid.uuid4(),
            observed_at=observed_time,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get("/api/auth/me/contributions/export")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["contribution_count"], 1)
        self.assertEqual(
            response.data["contributions"][0]["payload"]["name"], "My Stop"
        )


class ContributionExportPrivacyTestCase(TestCase):
    """Tests for privacy invariants in export (INV-D1 through INV-D4)."""

    def setUp(self):
        """Create test user with contributions."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="privacyuser",
            email="privacy@example.com",
            password="testpass123",
        )
        access_data = create_access_token(self.user)
        self.access_token = access_data["access_token"]
        observed_time = timezone.now() - timedelta(hours=1)

        # Create contribution with all fields populated
        self.fingerprint = self.user.id  # Use user.id as fingerprint (UUID)
        self.contribution = ContributionEvent.objects.create(
            contributor=self.user,
            contribution_type="stop_exists",
            subject_ref={"lat": 40.7128, "lon": -74.0060},
            payload={"name": "Test Stop"},
            contributor_fingerprint=self.fingerprint,
            client_generated_id=uuid.uuid4(),
            device_id=uuid.uuid4(),
            context={"app_version": "1.0", "device_type": "android"},
            observed_at=observed_time,
        )

    def test_export_does_not_include_contributor_fingerprint(self):
        """
        INV-D4: contributor_fingerprint must NEVER appear in export.

        This is an internal evaluation identifier and exposing it would
        allow cross-referencing contributions post-deletion.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get("/api/auth/me/contributions/export")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        exported = response.data["contributions"][0]

        # contributor_fingerprint must not be present
        self.assertNotIn("contributor_fingerprint", exported)

        # Also verify the fingerprint UUID string is not in the export
        export_str = str(response.data)
        self.assertNotIn(str(self.fingerprint), export_str)

    def test_export_does_not_include_internal_ids(self):
        """
        INV-D1: No system-internal identifiers exposed.

        Export must not include database IDs, client_generated_id,
        device_id, or other internal identifiers.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get("/api/auth/me/contributions/export")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        exported = response.data["contributions"][0]

        # Internal identifiers must not be present
        self.assertNotIn("id", exported)
        self.assertNotIn("client_generated_id", exported)
        self.assertNotIn("device_id", exported)
        self.assertNotIn("context", exported)
        self.assertNotIn("contributor", exported)
        self.assertNotIn("submitted_at", exported)

    def test_export_only_includes_whitelisted_fields(self):
        """
        Test that export uses explicit whitelist of fields.

        Only user-supplied data should be included:
        - observed_at
        - contribution_type
        - subject_ref
        - payload
        """
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get("/api/auth/me/contributions/export")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        exported = response.data["contributions"][0]

        # Only these fields should be present
        expected_fields = {"observed_at", "contribution_type", "subject_ref", "payload"}
        actual_fields = set(exported.keys())

        self.assertEqual(actual_fields, expected_fields)


class ContributionExportDeletedUserTestCase(TestCase):
    """Tests for export behavior with deleted users."""

    def setUp(self):
        """Create test user and client."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="deleteduser",
            email="deleted@example.com",
            password="testpass123",
        )
        access_data = create_access_token(self.user)
        self.access_token = access_data["access_token"]
        observed_time = timezone.now() - timedelta(hours=1)

        # Create contribution before "deletion"
        ContributionEvent.objects.create(
            contributor=self.user,
            contribution_type="stop_exists",
            subject_ref={"lat": 40.7128, "lon": -74.0060},
            payload={"name": "Test Stop"},
            contributor_fingerprint=self.user.id,
            client_generated_id=uuid.uuid4(),
            observed_at=observed_time,
        )

    def test_deleted_user_cannot_export(self):
        """
        INV-D3: Deleted users cannot access export.

        After account deletion (is_active=False), the export endpoint
        must return 403 Forbidden to prevent data access.
        """
        # Simulate deletion by deactivating user
        self.user.is_active = False
        self.user.save()

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get("/api/auth/me/contributions/export")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("error", response.data)
        self.assertIn("deactivated", response.data["error"].lower())


class ContributionExportStabilityTestCase(TestCase):
    """Tests for export stability and determinism."""

    def setUp(self):
        """Create test user with multiple contributions."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="stabilityuser",
            email="stability@example.com",
            password="testpass123",
        )
        access_data = create_access_token(self.user)
        self.access_token = access_data["access_token"]

        # Create multiple contributions with different timestamps
        base_time = timezone.now() - timedelta(hours=10)

        for i in range(5):
            ContributionEvent.objects.create(
                contributor=self.user,
                contribution_type="stop_exists",
                subject_ref={"lat": 40.0 + i * 0.1, "lon": -74.0},
                payload={"index": i},
                contributor_fingerprint=self.user.id,
                client_generated_id=uuid.uuid4(),
                observed_at=base_time + timedelta(hours=i),
            )

    def test_export_is_deterministic(self):
        """
        Test that export produces identical results on repeated calls.

        Export must be stable to support data verification and
        compliance auditing.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        # Make two export requests
        response1 = self.client.get("/api/auth/me/contributions/export")
        response2 = self.client.get("/api/auth/me/contributions/export")

        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

        # Results should be identical
        self.assertEqual(response1.data, response2.data)

    def test_export_ordered_by_observed_at(self):
        """
        Test that contributions are ordered by observed_at.

        Consistent ordering is required for deterministic export.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        response = self.client.get("/api/auth/me/contributions/export")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        contributions = response.data["contributions"]
        self.assertEqual(len(contributions), 5)

        # Verify ordering by checking payload index
        for i, contrib in enumerate(contributions):
            self.assertEqual(contrib["payload"]["index"], i)


class ContributionExportVersionTestCase(TestCase):
    """Tests for export versioning and metadata."""

    def setUp(self):
        """Create test user and client."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="versionuser",
            email="version@example.com",
            password="testpass123",
        )
        access_data = create_access_token(self.user)
        self.access_token = access_data["access_token"]

    def test_export_includes_version(self):
        """Test that export includes version for future compatibility."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        response = self.client.get("/api/auth/me/contributions/export")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("export_version", response.data)
        self.assertEqual(response.data["export_version"], "1.0")

    def test_export_includes_count(self):
        """Test that export includes contribution count for validation."""
        observed_time = timezone.now() - timedelta(hours=1)
        # Create some contributions
        for i in range(3):
            ContributionEvent.objects.create(
                contributor=self.user,
                contribution_type="stop_exists",
                subject_ref={"lat": 40.0, "lon": -74.0},
                payload={"index": i},
                contributor_fingerprint=self.user.id,
                client_generated_id=uuid.uuid4(),
                observed_at=observed_time,
            )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        response = self.client.get("/api/auth/me/contributions/export")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("contribution_count", response.data)
        self.assertEqual(response.data["contribution_count"], 3)
        self.assertEqual(len(response.data["contributions"]), 3)

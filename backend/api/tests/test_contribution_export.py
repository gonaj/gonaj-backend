"""
Tests for user data export (Sprint-9, Phase-2).

Tests cover DATA_RIGHTS_V1 compliance for the export endpoint:
- Authorization enforcement
- Ownership isolation (user can only export own data)
- Determinism (same data produces identical output)
- Non-leakage (no canonical, evaluation, or abuse data)
- UI mode independence (export content unaffected by UI mode)

TEST INVARIANTS:
- P2-INV-8: User data rights preserved
- INV-D1: No system-internal identifiers exposed
- INV-D4: No leaking contributor_fingerprint
"""

import uuid
from datetime import timedelta

from api.utils.tokens import create_access_token
from core.models import ContributionEvent, User
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient


# Export endpoint URL (versioned, v1 frozen)
EXPORT_URL = "/api/v1/me/contributions/export"


class ContributionExportAuthorizationTestCase(TestCase):
    """Tests for export endpoint authorization."""

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
        response = self.client.get(EXPORT_URL)
        # Unauthenticated requests return 403 Forbidden
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_export_authenticated_user_succeeds(self):
        """Test that authenticated users can export."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get(EXPORT_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ContributionExportOwnershipTestCase(TestCase):
    """Tests for ownership isolation in export."""

    def setUp(self):
        """Create test users and contributions."""
        self.client = APIClient()
        self.user_a = User.objects.create_user(
            username="usera",
            email="usera@example.com",
            password="testpass123",
        )
        self.user_b = User.objects.create_user(
            username="userb",
            email="userb@example.com",
            password="testpass123",
        )
        access_data = create_access_token(self.user_a)
        self.access_token_a = access_data["access_token"]
        observed_time = timezone.now() - timedelta(hours=1)

        # Create contributions for both users
        ContributionEvent.objects.create(
            contributor=self.user_a,
            contribution_type="stop_exists",
            subject_ref={"lat": 40.0, "lon": -74.0},
            payload={"name": "User A Stop"},
            contributor_fingerprint=self.user_a.id,
            client_generated_id=uuid.uuid4(),
            observed_at=observed_time,
        )
        ContributionEvent.objects.create(
            contributor=self.user_b,
            contribution_type="stop_exists",
            subject_ref={"lat": 41.0, "lon": -73.0},
            payload={"name": "User B Stop"},
            contributor_fingerprint=self.user_b.id,
            client_generated_id=uuid.uuid4(),
            observed_at=observed_time,
        )

    def test_user_a_cannot_see_user_b_contributions(self):
        """Test that User A can only see their own contributions."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token_a}")
        response = self.client.get(EXPORT_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["contributions"]), 1)
        self.assertEqual(
            response.data["contributions"][0]["payload"]["name"],
            "User A Stop"
        )


class ContributionExportFormatTestCase(TestCase):
    """Tests for export format compliance (v1)."""

    def setUp(self):
        """Create test user with contributions."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="formatuser",
            email="format@example.com",
            password="testpass123",
        )
        access_data = create_access_token(self.user)
        self.access_token = access_data["access_token"]
        observed_time = timezone.now() - timedelta(hours=1)

        self.contribution = ContributionEvent.objects.create(
            contributor=self.user,
            contribution_type="stop_exists",
            subject_ref={"lat": 40.7128, "lon": -74.0060},
            payload={"name": "Test Stop"},
            contributor_fingerprint=self.user.id,
            client_generated_id=uuid.uuid4(),
            observed_at=observed_time,
        )

    def test_export_version_is_v1(self):
        """Test that export_version is 'v1'."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get(EXPORT_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["export_version"], "v1")

    def test_export_includes_generated_at(self):
        """Test that generated_at timestamp is present."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get(EXPORT_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("generated_at", response.data)
        self.assertIsNotNone(response.data["generated_at"])

    def test_export_includes_user_section(self):
        """Test that user section with user_id and created_at is present."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get(EXPORT_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("user", response.data)
        self.assertIn("user_id", response.data["user"])
        self.assertIn("created_at", response.data["user"])
        self.assertEqual(response.data["user"]["user_id"], str(self.user.id))

    def test_contribution_includes_required_fields(self):
        """Test that contributions include all required fields."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get(EXPORT_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        contribution = response.data["contributions"][0]

        required_fields = {
            "contribution_id",
            "contribution_type",
            "observed_at",
            "submitted_at",
            "subject_ref",
            "payload",
        }
        self.assertEqual(set(contribution.keys()), required_fields)

    def test_contribution_id_matches_client_generated_id(self):
        """Test that contribution_id is the client_generated_id."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get(EXPORT_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        contribution = response.data["contributions"][0]
        self.assertEqual(
            contribution["contribution_id"],
            str(self.contribution.client_generated_id)
        )


class ContributionExportPrivacyTestCase(TestCase):
    """Tests for privacy invariants in export (INV-D1 through INV-D4)."""

    def setUp(self):
        """Create test user with contributions including all fields."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="privacyuser",
            email="privacy@example.com",
            password="testpass123",
        )
        access_data = create_access_token(self.user)
        self.access_token = access_data["access_token"]
        observed_time = timezone.now() - timedelta(hours=1)

        self.fingerprint = self.user.id
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
        """INV-D4: contributor_fingerprint must NEVER appear as a key in export."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get(EXPORT_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        contribution = response.data["contributions"][0]

        # contributor_fingerprint key must not be present in contributions
        self.assertNotIn("contributor_fingerprint", contribution)
        # Also verify it's not in top-level response
        self.assertNotIn("contributor_fingerprint", response.data)

    def test_export_does_not_include_internal_ids(self):
        """INV-D1: No system-internal identifiers exposed."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get(EXPORT_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        contribution = response.data["contributions"][0]

        # Internal identifiers must not be present
        self.assertNotIn("id", contribution)
        self.assertNotIn("device_id", contribution)
        self.assertNotIn("context", contribution)
        self.assertNotIn("contributor", contribution)


class ContributionExportDeletedUserTestCase(TestCase):
    """Tests for export behavior with deleted users."""

    def setUp(self):
        """Create test user and contributions."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="deleteduser",
            email="deleted@example.com",
            password="testpass123",
        )
        access_data = create_access_token(self.user)
        self.access_token = access_data["access_token"]
        observed_time = timezone.now() - timedelta(hours=1)

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
        """INV-D3: Deleted users cannot access export."""
        # Simulate deletion by deactivating user
        self.user.is_active = False
        self.user.save()

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get(EXPORT_URL)

        # Deleted users lack CONTRIBUTE capability, so they get 403
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ContributionExportDeterminismTestCase(TestCase):
    """Tests for export determinism and stability."""

    def setUp(self):
        """Create test user with multiple contributions."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="determinismuser",
            email="determinism@example.com",
            password="testpass123",
        )
        access_data = create_access_token(self.user)
        self.access_token = access_data["access_token"]

        # Create contributions with different timestamps
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

    def test_repeated_exports_are_identical_except_generated_at(self):
        """Test that repeated exports produce identical data (except generated_at)."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        response1 = self.client.get(EXPORT_URL)
        response2 = self.client.get(EXPORT_URL)

        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

        # generated_at will differ, so compare everything else
        data1 = response1.data.copy()
        data2 = response2.data.copy()
        del data1["generated_at"]
        del data2["generated_at"]

        self.assertEqual(data1, data2)

    def test_export_ordered_by_submitted_at_asc(self):
        """Test that contributions are ordered by submitted_at ASC."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get(EXPORT_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        contributions = response.data["contributions"]
        self.assertEqual(len(contributions), 5)

        # Verify ordering by parsing timestamps
        timestamps = [c["submitted_at"] for c in contributions]
        self.assertEqual(timestamps, sorted(timestamps))


class ContributionExportUIModeIndependenceTestCase(TestCase):
    """Tests for UI mode independence in export."""

    def setUp(self):
        """Create test user with contributions."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="uimodeuser",
            email="uimode@example.com",
            password="testpass123",
        )
        access_data = create_access_token(self.user)
        self.access_token = access_data["access_token"]
        observed_time = timezone.now() - timedelta(hours=1)

        ContributionEvent.objects.create(
            contributor=self.user,
            contribution_type="stop_exists",
            subject_ref={"lat": 40.7128, "lon": -74.0060},
            payload={"name": "Test Stop"},
            contributor_fingerprint=self.user.id,
            client_generated_id=uuid.uuid4(),
            observed_at=observed_time,
        )

    def test_ui_mode_does_not_affect_export_content(self):
        """Test that UI mode header does not change export content."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        # Export without UI mode
        response_no_mode = self.client.get(EXPORT_URL)

        # Export with contributor UI mode
        response_contributor = self.client.get(
            EXPORT_URL,
            HTTP_X_UI_MODE="contributor"
        )

        # Export with explorer UI mode
        response_explorer = self.client.get(
            EXPORT_URL,
            HTTP_X_UI_MODE="explorer"
        )

        self.assertEqual(response_no_mode.status_code, status.HTTP_200_OK)
        self.assertEqual(response_contributor.status_code, status.HTTP_200_OK)
        self.assertEqual(response_explorer.status_code, status.HTTP_200_OK)

        # Compare contributions (exclude generated_at which varies)
        data_no_mode = response_no_mode.data.copy()
        data_contributor = response_contributor.data.copy()
        data_explorer = response_explorer.data.copy()

        del data_no_mode["generated_at"]
        del data_contributor["generated_at"]
        del data_explorer["generated_at"]

        self.assertEqual(data_no_mode, data_contributor)
        self.assertEqual(data_no_mode, data_explorer)


class ContributionExportEmptyStateTestCase(TestCase):
    """Tests for export with no contributions."""

    def setUp(self):
        """Create test user with no contributions."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="emptyuser",
            email="empty@example.com",
            password="testpass123",
        )
        access_data = create_access_token(self.user)
        self.access_token = access_data["access_token"]

    def test_export_works_with_no_contributions(self):
        """Test that export works when user has no contributions."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get(EXPORT_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["export_version"], "v1")
        self.assertEqual(response.data["contributions"], [])
        self.assertIn("user", response.data)

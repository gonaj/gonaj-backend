"""
Tests for Canonical Read API Hardening (Phase-2 Sprint-2).

This test suite validates that canonical read endpoints are:
- Safe for anonymous access (where permitted)
- Do not leak evidence or internal data
- Stable under malformed parameters
- Properly bounded

INVARIANTS TESTED:
- Canonical data is the only data exposed to anonymous users
- Evidence data must never be inferable from read APIs
- Absence of data must not be interpreted as falseness
- Backend remains sole authority on truth

PHILOSOPHY:
These tests prove safety, not functionality. They validate that the API
cannot be abused to extract internal state or overwhelm the system.

SPRINT-9 UPDATE:
Export endpoint moved to /api/v1/me/contributions/export with v1 frozen semantics:
- Atomic, complete, non-paginated, non-filterable
- No query parameters alter output
"""

import uuid
from datetime import timedelta

from core.models import ContributionEvent
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()

# Export endpoint URL (v1 frozen)
EXPORT_URL = "/api/v1/me/contributions/export"


class AnonymousSafetyTests(TestCase):
    """
    Test that anonymous users cannot access user-scoped data.
    
    REQUIREMENT: Anonymous users can only access public canonical endpoints.
    User-scoped data (contributions, profile) requires authentication.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        # Create some contributions for the user
        for i in range(3):
            ContributionEvent.objects.create(
                client_generated_id=uuid.uuid4(),
                contributor=self.user,
                contributor_fingerprint=self.user.id,
                contribution_type="stop_exists",
                subject_ref={"lat": 40.7 + i * 0.01, "lon": -74.0},
                payload={"confidence": "high"},
                observed_at=timezone.now() - timedelta(days=i),
            )

    def test_anonymous_cannot_access_contribution_export(self):
        """Anonymous users cannot export contributions."""
        response = self.client.get(EXPORT_URL)
        
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
            "Anonymous contribution export should be rejected"
        )

    def test_anonymous_cannot_access_user_profile(self):
        """Anonymous users cannot access user profile."""
        response = self.client.get("/api/auth/me")
        
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
            "Anonymous profile access should be rejected"
        )

    def test_anonymous_cannot_infer_user_existence_from_export(self):
        """
        Anonymous requests should not reveal whether users exist.
        
        The response for a non-existent user should be indistinguishable
        from the response for an existing user (both rejected).
        """
        # Request for authenticated endpoint without auth
        response1 = self.client.get(EXPORT_URL)
        
        # The error response should not indicate anything about user existence
        self.assertIn(
            response1.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
        )
        
        # Response should not contain user-identifying information
        response_str = str(response1.content)
        self.assertNotIn("testuser", response_str)
        self.assertNotIn("test@example.com", response_str)


class SerializerLeakageTests(TestCase):
    """
    Test that serializers do not leak internal data.
    
    REQUIREMENT: No internal identifiers, fingerprints, or evaluation
    artifacts are exposed through API responses.
    """

    def setUp(self):
        """Set up authenticated client with contributions."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.client.force_authenticate(user=self.user)
        
        # Create contributions with all fields populated
        self.contribution = ContributionEvent.objects.create(
            client_generated_id=uuid.uuid4(),
            contributor=self.user,
            contributor_fingerprint=self.user.id,
            device_id=uuid.uuid4(),
            contribution_type="stop_exists",
            subject_ref={"lat": 40.7, "lon": -74.0},
            payload={"confidence": "high", "notes": "Test note"},
            observed_at=timezone.now(),
            context={"gps_accuracy": 5.0, "app_version": "1.0.0"},
        )

    def test_export_does_not_leak_internal_id(self):
        """Export should not include internal UUID id."""
        response = self.client.get(EXPORT_URL)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        contributions = response.data.get("contributions", [])
        self.assertTrue(len(contributions) > 0, "Should have contributions")
        
        for contribution in contributions:
            self.assertNotIn("id", contribution)

    def test_export_does_not_leak_contributor_fingerprint(self):
        """Export should not include contributor_fingerprint (INV-D4)."""
        response = self.client.get(EXPORT_URL)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        for contribution in response.data.get("contributions", []):
            self.assertNotIn("contributor_fingerprint", contribution)

    def test_export_does_not_leak_device_id(self):
        """Export should not include device_id."""
        response = self.client.get(EXPORT_URL)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        for contribution in response.data.get("contributions", []):
            self.assertNotIn("device_id", contribution)

    def test_export_does_not_leak_context(self):
        """Export should not include context metadata."""
        response = self.client.get(EXPORT_URL)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        for contribution in response.data.get("contributions", []):
            self.assertNotIn("context", contribution)

    def test_export_does_not_leak_contributor_reference(self):
        """Export should not include contributor or contributor_id."""
        response = self.client.get(EXPORT_URL)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        for contribution in response.data.get("contributions", []):
            self.assertNotIn("contributor", contribution)
            self.assertNotIn("contributor_id", contribution)

    def test_export_only_contains_whitelisted_fields(self):
        """Export should contain ONLY the whitelisted fields (v1)."""
        response = self.client.get(EXPORT_URL)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # v1 allowed fields in export
        allowed_fields = {
            "contribution_id", "contribution_type", "observed_at",
            "submitted_at", "subject_ref", "payload"
        }
        
        for contribution in response.data.get("contributions", []):
            actual_fields = set(contribution.keys())
            unexpected_fields = actual_fields - allowed_fields
            self.assertEqual(
                unexpected_fields,
                set(),
                f"Unexpected fields in export: {unexpected_fields}"
            )

    def test_profile_does_not_leak_password(self):
        """Profile endpoint should never expose password."""
        response = self.client.get("/api/auth/me")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("password", response.data)
        self.assertNotIn("password_hash", response.data)

    def test_profile_does_not_leak_privilege_info(self):
        """Profile endpoint should not expose is_staff or is_superuser."""
        response = self.client.get("/api/auth/me")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("is_staff", response.data)
        self.assertNotIn("is_superuser", response.data)

    def test_profile_does_not_leak_internal_consent_data(self):
        """Profile endpoint should not expose internal consent tracking."""
        response = self.client.get("/api/auth/me")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("privacy_consent_version", response.data)
        self.assertNotIn("privacy_consent_ts", response.data)


class ExportV1SemanticsTests(TestCase):
    """
    Test that v1 export is atomic, complete, non-paginated, non-filterable.
    
    REQUIREMENT: Export v1 returns all data in single response.
    Query parameters do not alter output.
    """

    def setUp(self):
        """Set up authenticated client with contributions."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.client.force_authenticate(user=self.user)
        
        # Create many contributions
        for i in range(50):
            ContributionEvent.objects.create(
                client_generated_id=uuid.uuid4(),
                contributor=self.user,
                contributor_fingerprint=self.user.id,
                contribution_type="stop_exists",
                subject_ref={"lat": 40.7, "lon": -74.0},
                payload={"index": i},
                observed_at=timezone.now() - timedelta(hours=i),
            )

    def test_export_returns_all_contributions(self):
        """v1 export returns all contributions without pagination."""
        response = self.client.get(EXPORT_URL)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["contributions"]), 50)

    def test_export_ignores_pagination_parameters(self):
        """v1 export ignores page/page_size parameters."""
        response = self.client.get(f"{EXPORT_URL}?page=2&page_size=10")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should still return all 50, not paginated subset
        self.assertEqual(len(response.data["contributions"]), 50)

    def test_export_ignores_filter_parameters(self):
        """v1 export ignores filter parameters."""
        response = self.client.get(f"{EXPORT_URL}?contribution_type=stop_name")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should still return all 50 stop_exists contributions
        self.assertEqual(len(response.data["contributions"]), 50)

    def test_export_has_no_pagination_metadata(self):
        """v1 export does not include pagination metadata."""
        response = self.client.get(EXPORT_URL)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("pagination", response.data)


class HttpMethodEnforcementTests(TestCase):
    """
    Test that unsupported HTTP methods return 405 consistently.
    
    REQUIREMENT: Unsupported HTTP verbs return HTTP 405.
    """

    def setUp(self):
        """Set up authenticated client."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

    def test_export_rejects_post(self):
        """POST on export endpoint should return 405."""
        response = self.client.post(EXPORT_URL, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_export_rejects_put(self):
        """PUT on export endpoint should return 405."""
        response = self.client.put(EXPORT_URL, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_export_rejects_patch(self):
        """PATCH on export endpoint should return 405."""
        response = self.client.patch(EXPORT_URL, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_export_rejects_delete(self):
        """DELETE on export endpoint should return 405."""
        response = self.client.delete(EXPORT_URL)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_profile_rejects_post(self):
        """POST on profile endpoint should return 405."""
        response = self.client.post("/api/auth/me", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_profile_rejects_put(self):
        """PUT on profile endpoint should return 405."""
        response = self.client.put("/api/auth/me", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_profile_rejects_patch(self):
        """PATCH on profile endpoint should return 405."""
        response = self.client.patch("/api/auth/me", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_profile_rejects_delete(self):
        """DELETE on profile endpoint should return 405."""
        response = self.client.delete("/api/auth/me")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class OutputSchemaStabilityTests(TestCase):
    """
    Test that API output schemas are stable and predictable.
    
    REQUIREMENT: Output schema is stable across requests.
    """

    def setUp(self):
        """Set up authenticated client."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.client.force_authenticate(user=self.user)
        
        # Create a contribution
        ContributionEvent.objects.create(
            client_generated_id=uuid.uuid4(),
            contributor=self.user,
            contributor_fingerprint=self.user.id,
            contribution_type="stop_exists",
            subject_ref={"lat": 40.7, "lon": -74.0},
            payload={"confidence": "high"},
            observed_at=timezone.now(),
        )

    def test_export_schema_is_stable(self):
        """Export response schema should be consistent (v1)."""
        response = self.client.get(EXPORT_URL)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Required top-level fields (v1)
        self.assertIn("export_version", response.data)
        self.assertIn("generated_at", response.data)
        self.assertIn("user", response.data)
        self.assertIn("contributions", response.data)
        
        # Export version should be v1
        self.assertEqual(response.data["export_version"], "v1")
        
        # User section should have expected fields
        self.assertIn("user_id", response.data["user"])
        self.assertIn("created_at", response.data["user"])

    def test_profile_schema_is_stable(self):
        """Profile response schema should be consistent."""
        response = self.client.get("/api/auth/me")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Required fields
        expected_fields = {
            "id", "username", "email", "display_name",
            "email_verified", "public_profile", "date_joined", "last_login"
        }
        
        actual_fields = set(response.data.keys())
        
        # All expected fields should be present
        missing_fields = expected_fields - actual_fields
        self.assertEqual(
            missing_fields,
            set(),
            f"Missing expected fields: {missing_fields}"
        )

    def test_empty_export_has_correct_schema(self):
        """Empty export should still have correct schema (v1)."""
        # Create a new user with no contributions
        user2 = User.objects.create_user(
            username="emptyuser",
            email="empty@example.com",
            password="testpass123"
        )
        self.client.force_authenticate(user=user2)
        
        response = self.client.get(EXPORT_URL)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["export_version"], "v1")
        self.assertEqual(response.data["contributions"], [])
        self.assertIn("user", response.data)
        self.assertIn("generated_at", response.data)


class NoDebugLeakageTests(TestCase):
    """
    Test that error responses do not leak debug information.
    
    REQUIREMENT: No stack traces or debug info in responses.
    """

    def setUp(self):
        """Set up test client."""
        self.client = APIClient()

    def test_401_does_not_leak_stack_trace(self):
        """Unauthorized responses should not contain stack traces."""
        response = self.client.get("/api/auth/me")
        
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
        )
        
        content = response.content.decode('utf-8')
        self.assertNotIn("Traceback", content)
        self.assertNotIn("Traceback (most recent call last)", content)
        self.assertNotIn("File \"", content)
        self.assertNotIn("Exception", content)

    def test_405_does_not_leak_stack_trace(self):
        """Method not allowed responses should not contain stack traces."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.client.force_authenticate(user=user)
        
        response = self.client.delete(EXPORT_URL)
        
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        
        content = response.content.decode('utf-8')
        self.assertNotIn("Traceback", content)
        self.assertNotIn("File \"", content)

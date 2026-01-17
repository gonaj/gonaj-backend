"""
Tests for Canonical Read API Hardening (Phase-2 Sprint-2).

This test suite validates that canonical read endpoints are:
- Safe for anonymous access (where permitted)
- Do not leak evidence or internal data
- Stable under malformed parameters
- Properly paginated and bounded

INVARIANTS TESTED:
- Canonical data is the only data exposed to anonymous users
- Evidence data must never be inferable from read APIs
- Absence of data must not be interpreted as falseness
- Backend remains sole authority on truth

PHILOSOPHY:
These tests prove safety, not functionality. They validate that the API
cannot be abused to extract internal state or overwhelm the system.
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
        response = self.client.get("/api/me/contributions/export")
        
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
        response1 = self.client.get("/api/me/contributions/export")
        
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
        # contributor_fingerprint is required for evaluation identity
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
        response = self.client.get("/api/me/contributions/export")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        contributions = response.data.get("contributions", [])
        self.assertTrue(len(contributions) > 0, "Should have contributions")
        
        for contribution in contributions:
            self.assertNotIn("id", contribution)

    def test_export_does_not_leak_client_generated_id(self):
        """Export should not include client_generated_id."""
        response = self.client.get("/api/me/contributions/export")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        for contribution in response.data.get("contributions", []):
            self.assertNotIn("client_generated_id", contribution)

    def test_export_does_not_leak_contributor_fingerprint(self):
        """Export should not include contributor_fingerprint (INV-D4)."""
        response = self.client.get("/api/me/contributions/export")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        for contribution in response.data.get("contributions", []):
            self.assertNotIn("contributor_fingerprint", contribution)

    def test_export_does_not_leak_device_id(self):
        """Export should not include device_id."""
        response = self.client.get("/api/me/contributions/export")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        for contribution in response.data.get("contributions", []):
            self.assertNotIn("device_id", contribution)

    def test_export_does_not_leak_context(self):
        """Export should not include context metadata."""
        response = self.client.get("/api/me/contributions/export")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        for contribution in response.data.get("contributions", []):
            self.assertNotIn("context", contribution)

    def test_export_does_not_leak_submitted_at(self):
        """Export should not include server-generated submitted_at."""
        response = self.client.get("/api/me/contributions/export")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        for contribution in response.data.get("contributions", []):
            self.assertNotIn("submitted_at", contribution)

    def test_export_does_not_leak_contributor_reference(self):
        """Export should not include contributor or contributor_id."""
        response = self.client.get("/api/me/contributions/export")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        for contribution in response.data.get("contributions", []):
            self.assertNotIn("contributor", contribution)
            self.assertNotIn("contributor_id", contribution)

    def test_export_only_contains_whitelisted_fields(self):
        """Export should contain ONLY the whitelisted fields."""
        response = self.client.get("/api/me/contributions/export")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Allowed fields in export
        allowed_fields = {"observed_at", "contribution_type", "subject_ref", "payload"}
        
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


class MalformedParameterTests(TestCase):
    """
    Test that endpoints are stable under malformed or hostile parameters.
    
    REQUIREMENT: Malformed parameters result in safe defaults or
    clear error responses, never crashes or data leaks.
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
        
        # Create some contributions
        for i in range(25):
            ContributionEvent.objects.create(
                client_generated_id=uuid.uuid4(),
                contributor=self.user,
                contributor_fingerprint=self.user.id,
                contribution_type="stop_exists",
                subject_ref={"lat": 40.7, "lon": -74.0},
                payload={"confidence": "high"},
                observed_at=timezone.now() - timedelta(hours=i),
            )

    def test_export_with_negative_page(self):
        """Negative page number should default to 1."""
        response = self.client.get("/api/me/contributions/export?page=-5")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pagination"]["page"], 1)

    def test_export_with_zero_page(self):
        """Zero page number should default to 1."""
        response = self.client.get("/api/me/contributions/export?page=0")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pagination"]["page"], 1)

    def test_export_with_non_numeric_page(self):
        """Non-numeric page should default to 1."""
        response = self.client.get("/api/me/contributions/export?page=abc")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pagination"]["page"], 1)

    def test_export_with_very_large_page(self):
        """Very large page number should return empty results."""
        response = self.client.get("/api/me/contributions/export?page=999999")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["contributions"]), 0)

    def test_export_with_negative_page_size(self):
        """Negative page_size should use default."""
        response = self.client.get("/api/me/contributions/export?page_size=-10")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should use default page size (20)
        self.assertEqual(response.data["pagination"]["page_size"], 20)

    def test_export_with_zero_page_size(self):
        """Zero page_size should use default."""
        response = self.client.get("/api/me/contributions/export?page_size=0")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pagination"]["page_size"], 20)

    def test_export_with_oversized_page_size(self):
        """Page size exceeding maximum should be capped."""
        response = self.client.get("/api/me/contributions/export?page_size=1000")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should be capped at MAX_PAGE_SIZE (100)
        self.assertEqual(response.data["pagination"]["page_size"], 100)

    def test_export_with_non_numeric_page_size(self):
        """Non-numeric page_size should use default."""
        response = self.client.get("/api/me/contributions/export?page_size=invalid")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pagination"]["page_size"], 20)

    def test_export_with_sql_injection_attempt(self):
        """SQL injection attempts should be safely handled."""
        response = self.client.get(
            "/api/me/contributions/export?page=1;DROP TABLE contributions;"
        )
        
        # Should not crash, should use safe default
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pagination"]["page"], 1)

    def test_export_with_special_characters_in_params(self):
        """Special characters should not cause errors."""
        response = self.client.get(
            "/api/me/contributions/export?page=<script>alert(1)</script>"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pagination"]["page"], 1)


class PaginationBoundingTests(TestCase):
    """
    Test that pagination is properly bounded to prevent DoS.
    
    REQUIREMENT: Unbounded queries are rejected. Pagination defaults
    are enforced. Maximum page sizes are respected.
    """

    def setUp(self):
        """Set up authenticated client with many contributions."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.client.force_authenticate(user=self.user)
        
        # Create many contributions
        for i in range(150):
            ContributionEvent.objects.create(
                client_generated_id=uuid.uuid4(),
                contributor=self.user,
                contributor_fingerprint=self.user.id,
                contribution_type="stop_exists",
                subject_ref={"lat": 40.7, "lon": -74.0},
                payload={"confidence": "high"},
                observed_at=timezone.now() - timedelta(minutes=i),
            )

    def test_export_has_pagination_metadata(self):
        """Export response should include pagination metadata."""
        response = self.client.get("/api/me/contributions/export")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("pagination", response.data)
        
        pagination = response.data["pagination"]
        self.assertIn("page", pagination)
        self.assertIn("page_size", pagination)
        self.assertIn("total_count", pagination)
        self.assertIn("total_pages", pagination)
        self.assertIn("has_next", pagination)
        self.assertIn("has_previous", pagination)

    def test_export_default_page_size(self):
        """Default page size should be 20."""
        response = self.client.get("/api/me/contributions/export")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["contributions"]), 20)
        self.assertEqual(response.data["pagination"]["page_size"], 20)

    def test_export_respects_custom_page_size(self):
        """Custom page size within bounds should be respected."""
        response = self.client.get("/api/me/contributions/export?page_size=50")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["contributions"]), 50)
        self.assertEqual(response.data["pagination"]["page_size"], 50)

    def test_export_caps_page_size_at_maximum(self):
        """Page size should be capped at MAX_PAGE_SIZE (100)."""
        response = self.client.get("/api/me/contributions/export?page_size=500")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["contributions"]), 100)
        self.assertEqual(response.data["pagination"]["page_size"], 100)

    def test_export_pagination_navigation(self):
        """Pagination navigation flags should be correct."""
        # First page
        response = self.client.get("/api/me/contributions/export?page=1&page_size=50")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["pagination"]["has_previous"])
        self.assertTrue(response.data["pagination"]["has_next"])
        
        # Middle page
        response = self.client.get("/api/me/contributions/export?page=2&page_size=50")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["pagination"]["has_previous"])
        self.assertTrue(response.data["pagination"]["has_next"])
        
        # Last page
        response = self.client.get("/api/me/contributions/export?page=3&page_size=50")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["pagination"]["has_previous"])
        self.assertFalse(response.data["pagination"]["has_next"])

    def test_export_total_count_accuracy(self):
        """Total count should be accurate."""
        response = self.client.get("/api/me/contributions/export")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pagination"]["total_count"], 150)

    def test_export_cannot_retrieve_all_at_once(self):
        """Cannot retrieve all 150 items in a single request."""
        response = self.client.get("/api/me/contributions/export?page_size=200")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should be capped at 100
        self.assertEqual(len(response.data["contributions"]), 100)


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
        response = self.client.post(
            "/api/me/contributions/export",
            {},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_export_rejects_put(self):
        """PUT on export endpoint should return 405."""
        response = self.client.put(
            "/api/me/contributions/export",
            {},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_export_rejects_patch(self):
        """PATCH on export endpoint should return 405."""
        response = self.client.patch(
            "/api/me/contributions/export",
            {},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_export_rejects_delete(self):
        """DELETE on export endpoint should return 405."""
        response = self.client.delete("/api/me/contributions/export")
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
        """Export response schema should be consistent."""
        response = self.client.get("/api/me/contributions/export")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Required top-level fields
        self.assertIn("export_version", response.data)
        self.assertIn("contribution_count", response.data)
        self.assertIn("contributions", response.data)
        self.assertIn("pagination", response.data)
        
        # Export version should be stable
        self.assertEqual(response.data["export_version"], "1.0")

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
        """Empty export should still have correct schema."""
        # Create a new user with no contributions
        user2 = User.objects.create_user(
            username="emptyuser",
            email="empty@example.com",
            password="testpass123"
        )
        self.client.force_authenticate(user=user2)
        
        response = self.client.get("/api/me/contributions/export")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["export_version"], "1.0")
        self.assertEqual(response.data["contribution_count"], 0)
        self.assertEqual(response.data["contributions"], [])
        self.assertIn("pagination", response.data)


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
        self.assertNotIn("File \"", content)
        self.assertNotIn("line ", content)
        self.assertNotIn("Exception", content)

    def test_405_does_not_leak_stack_trace(self):
        """Method not allowed responses should not contain stack traces."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.client.force_authenticate(user=user)
        
        response = self.client.delete("/api/me/contributions/export")
        
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        
        content = response.content.decode('utf-8')
        self.assertNotIn("Traceback", content)
        self.assertNotIn("File \"", content)

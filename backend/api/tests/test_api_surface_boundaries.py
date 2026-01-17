"""
Tests for API Surface Boundary Lockdown (Phase-2 Sprint-1).

This test suite validates that the API boundaries are properly enforced:
- Anonymous users cannot mutate state
- HTTP method restrictions are enforced (405 for unsupported methods)
- Permission boundaries are respected
- Cross-user access is prevented

PHILOSOPHY:
These tests prove the API surface is secure by default. They validate
infrastructure, not business logic.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


class AnonymousMutationTests(TestCase):
    """
    Test that anonymous users cannot mutate state.
    
    REQUIREMENT: No state-changing endpoint is accessible without authentication.
    """

    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
        # Create a user for endpoints that need existing data
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

    def test_anonymous_cannot_submit_contribution(self):
        """Anonymous users cannot submit contributions."""
        response = self.client.post(
            "/api/v1/contributions/",
            {
                "client_generated_id": "test-id",
                "contribution_type": "stop_exists",
                "subject_ref": {"lat": 40.7, "lon": -74.0},
                "payload": {},
                "observed_at": "2025-12-23T10:30:00Z",
            },
            format="json"
        )
        
        # Should be 401 (Unauthorized) or 403 (Forbidden)
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
            "Anonymous contribution submission should be rejected"
        )

    def test_anonymous_cannot_delete_account(self):
        """Anonymous users cannot delete accounts."""
        response = self.client.delete("/api/me")
        
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
            "Anonymous account deletion should be rejected"
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

    def test_anonymous_cannot_logout(self):
        """Anonymous users cannot logout (requires authentication)."""
        response = self.client.post("/api/auth/logout", {}, format="json")
        
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
            "Anonymous logout should be rejected"
        )


class HttpMethodRestrictionTests(TestCase):
    """
    Test that unsupported HTTP methods are rejected with 405.
    
    REQUIREMENT: Unsupported HTTP methods are rejected consistently.
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

    def test_contribution_endpoint_only_allows_post(self):
        """Contribution endpoint should only accept POST."""
        url = "/api/v1/contributions/"
        
        # GET should be rejected
        response = self.client.get(url)
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
            "GET on contribution endpoint should return 405"
        )
        
        # PUT should be rejected
        response = self.client.put(url, {}, format="json")
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
            "PUT on contribution endpoint should return 405"
        )
        
        # PATCH should be rejected
        response = self.client.patch(url, {}, format="json")
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
            "PATCH on contribution endpoint should return 405"
        )
        
        # DELETE should be rejected
        response = self.client.delete(url)
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
            "DELETE on contribution endpoint should return 405"
        )

    def test_account_deletion_endpoint_only_allows_delete(self):
        """Account deletion endpoint should only accept DELETE."""
        url = "/api/me"
        
        # GET should be rejected
        response = self.client.get(url)
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
            "GET on account deletion endpoint should return 405"
        )
        
        # POST should be rejected
        response = self.client.post(url, {}, format="json")
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
            "POST on account deletion endpoint should return 405"
        )
        
        # PUT should be rejected
        response = self.client.put(url, {}, format="json")
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
            "PUT on account deletion endpoint should return 405"
        )
        
        # PATCH should be rejected
        response = self.client.patch(url, {}, format="json")
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
            "PATCH on account deletion endpoint should return 405"
        )

    def test_contribution_export_endpoint_only_allows_get(self):
        """Contribution export endpoint should only accept GET."""
        url = "/api/me/contributions/export"
        
        # POST should be rejected
        response = self.client.post(url, {}, format="json")
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
            "POST on export endpoint should return 405"
        )
        
        # PUT should be rejected
        response = self.client.put(url, {}, format="json")
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
            "PUT on export endpoint should return 405"
        )
        
        # DELETE should be rejected
        response = self.client.delete(url)
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
            "DELETE on export endpoint should return 405"
        )

    def test_user_profile_endpoint_only_allows_get(self):
        """User profile endpoint should only accept GET."""
        url = "/api/auth/me"
        
        # POST should be rejected
        response = self.client.post(url, {}, format="json")
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
            "POST on profile endpoint should return 405"
        )
        
        # PUT should be rejected
        response = self.client.put(url, {}, format="json")
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
            "PUT on profile endpoint should return 405"
        )
        
        # DELETE should be rejected
        response = self.client.delete(url)
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
            "DELETE on profile endpoint should return 405"
        )

    def test_login_endpoint_only_allows_post(self):
        """Login endpoint should only accept POST."""
        url = "/api/auth/login"
        
        # GET should be rejected
        response = self.client.get(url)
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
            "GET on login endpoint should return 405"
        )
        
        # PUT should be rejected
        response = self.client.put(url, {}, format="json")
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
            "PUT on login endpoint should return 405"
        )
        
        # DELETE should be rejected
        response = self.client.delete(url)
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
            "DELETE on login endpoint should return 405"
        )

    def test_logout_endpoint_only_allows_post(self):
        """Logout endpoint should only accept POST."""
        url = "/api/auth/logout"
        
        # GET should be rejected
        response = self.client.get(url)
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
            "GET on logout endpoint should return 405"
        )
        
        # PUT should be rejected
        response = self.client.put(url, {}, format="json")
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
            "PUT on logout endpoint should return 405"
        )
        
        # DELETE should be rejected
        response = self.client.delete(url)
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
            "DELETE on logout endpoint should return 405"
        )


class ReadOnlyEndpointTests(TestCase):
    """
    Test that read-only endpoints cannot be mutated.
    
    REQUIREMENT: Public read endpoints are read-only.
    Note: Currently no public read endpoints exist, but this tests
    the pattern for future endpoints.
    """

    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

    def test_auth_me_is_read_only(self):
        """GET /api/auth/me should be read-only."""
        url = "/api/auth/me"
        
        # GET should work
        response = self.client.get(url)
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            "GET on /api/auth/me should succeed"
        )
        
        # POST/PUT/PATCH/DELETE should be rejected
        for method in ['post', 'put', 'patch', 'delete']:
            method_func = getattr(self.client, method)
            response = method_func(url, {} if method != 'delete' else None, format="json")
            self.assertEqual(
                response.status_code,
                status.HTTP_405_METHOD_NOT_ALLOWED,
                f"{method.upper()} on read-only endpoint should return 405"
            )

    def test_contribution_export_is_read_only(self):
        """GET /api/me/contributions/export should be read-only."""
        url = "/api/me/contributions/export"
        
        # GET should work (even if empty)
        response = self.client.get(url)
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            "GET on /api/me/contributions/export should succeed"
        )
        
        # POST/PUT/PATCH/DELETE should be rejected
        for method in ['post', 'put', 'patch', 'delete']:
            method_func = getattr(self.client, method)
            response = method_func(url, {} if method != 'delete' else None, format="json")
            self.assertEqual(
                response.status_code,
                status.HTTP_405_METHOD_NOT_ALLOWED,
                f"{method.upper()} on read-only endpoint should return 405"
            )


class PermissionBoundaryTests(TestCase):
    """
    Test that permission boundaries are enforced.
    
    REQUIREMENT: No permission ambiguity exists.
    """

    def setUp(self):
        """Set up test users."""
        self.client = APIClient()
        self.user1 = User.objects.create_user(
            username="user1",
            email="user1@example.com",
            password="testpass123"
        )
        self.user2 = User.objects.create_user(
            username="user2",
            email="user2@example.com",
            password="testpass123"
        )

    def test_authenticated_user_can_access_own_profile(self):
        """Authenticated users can access their own profile."""
        self.client.force_authenticate(user=self.user1)
        
        response = self.client.get("/api/auth/me")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "user1@example.com")

    def test_authenticated_user_can_delete_own_account(self):
        """Authenticated users can delete their own account."""
        self.client.force_authenticate(user=self.user1)
        
        response = self.client.delete("/api/me")
        
        # Should succeed (200 OK)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify user is deleted
        self.user1.refresh_from_db()
        self.assertFalse(self.user1.is_active)

    def test_authenticated_user_can_export_own_contributions(self):
        """Authenticated users can export their own contributions."""
        self.client.force_authenticate(user=self.user1)
        
        response = self.client.get("/api/me/contributions/export")
        
        # Should succeed (even if empty)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("contributions", response.data)

    def test_contributor_permission_allows_submission(self):
        """
        Authenticated users with contributor capability can submit contributions.
        
        Currently, all authenticated users are contributors (Phase-2 Sprint-1).
        """
        self.client.force_authenticate(user=self.user1)
        
        response = self.client.post(
            "/api/v1/contributions/",
            {
                "client_generated_id": "550e8400-e29b-41d4-a716-446655440000",
                "contribution_type": "stop_exists",
                "subject_ref": {"lat": 40.7, "lon": -74.0},
                "payload": {},
                "observed_at": "2025-12-23T10:30:00Z",
            },
            format="json"
        )
        
        # Should succeed (201 Created)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class AccessFailureSecurityTests(TestCase):
    """
    Test that access failures do not leak internal details.
    
    REQUIREMENT: Access failures do not leak internal details.
    """

    def setUp(self):
        """Set up test client."""
        self.client = APIClient()

    def test_401_responses_do_not_leak_details(self):
        """Unauthorized responses should not leak sensitive information."""
        # Try to access protected endpoint without auth
        response = self.client.get("/api/auth/me")
        
        # Should return 401/403
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
        )
        
        # Response should not contain stack traces or internal errors
        response_text = str(response.content)
        self.assertNotIn("Traceback", response_text)
        self.assertNotIn("File", response_text)
        self.assertNotIn("line", response_text)

    def test_405_responses_are_consistent(self):
        """Method not allowed responses should be consistent."""
        # For protected endpoints, DRF checks authentication before HTTP methods.
        # This is expected behavior: don't reveal available methods to unauthenticated users.
        # Test with an authenticated user to verify 405 handling.
        User = get_user_model()
        user = User.objects.create_user(
            username="methodtest",
            email="methodtest@example.com",
            password="testpass123"
        )
        self.client.force_authenticate(user=user)
        
        response = self.client.get("/api/v1/contributions/")
        
        # Should return 405 for authenticated user using wrong method
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        
        # Response should not leak internal structure
        response_text = str(response.content)
        self.assertNotIn("Traceback", response_text)

"""
Tests for account deletion API endpoint (Sprint-5D).

This module tests the DELETE /api/me endpoint routing.
Business logic is tested in accounts/tests/test_account_deletion_service.py.

TEST SCOPE:
- Verify endpoint is routable
- Verify authentication is required
- Verify service integration works

Note: Full deletion semantics and invariants are tested in the
service layer tests (Sprint-5A).
"""

from core.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from api.utils.tokens import create_access_token


class AccountDeletionEndpointTestCase(TestCase):
    """Tests for DELETE /api/me endpoint routing."""

    def setUp(self):
        """Create test user and client."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="deleteuser",
            email="delete@example.com",
            password="testpass123",
        )
        access_data = create_access_token(self.user)
        self.access_token = access_data["access_token"]

    def test_deletion_requires_authentication(self):
        """Test that delete endpoint requires authentication."""
        response = self.client.delete("/api/me")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_deletion_endpoint_reachable(self):
        """Test that delete endpoint is routable and works."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        response = self.client.delete("/api/me")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("success", response.data)
        self.assertTrue(response.data["success"])
        self.assertIn("deleted_at", response.data)
        self.assertIn("tokens_revoked", response.data)

    def test_deletion_is_idempotent(self):
        """
        Test that deleted users cannot call delete endpoint again.
        
        UPDATED (Phase-2 Sprint-4):
        Authorization now prevents inactive users from mutating.
        Idempotency at service layer is preserved but not exposed via API.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        # First deletion
        response1 = self.client.delete("/api/me")
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # Second deletion should be denied (inactive users cannot mutate)
        response2 = self.client.delete("/api/me")
        # DRF may return 403 or 401, both are acceptable for denied access
        self.assertIn(
            response2.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
        )

    def test_deleted_user_is_deactivated(self):
        """Test that deleted user is marked as inactive."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        response = self.client.delete("/api/me")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Refresh user from database
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)


class AccountDeletionNamespaceTestCase(TestCase):
    """Tests to verify correct API namespace (/api/me/*)."""

    def setUp(self):
        """Create test user and client."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="namespaceuser",
            email="namespace@example.com",
            password="testpass123",
        )
        access_data = create_access_token(self.user)
        self.access_token = access_data["access_token"]

    def test_me_endpoint_uses_canonical_path(self):
        """Verify /api/me is the canonical path for account deletion."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        # The canonical path /api/me should work
        response = self.client.delete("/api/me")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_export_uses_canonical_path(self):
        """Verify /api/me/contributions/export is the canonical path."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        # The canonical path should work
        response = self.client.get("/api/me/contributions/export")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

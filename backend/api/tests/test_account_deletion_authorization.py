"""
Tests for account deletion authorization (Phase-2 Sprint-4).

Account deletion is a special case: users can delete their own account
but not others' accounts. This is still capability-based (contribute),
but with an ownership check.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


class AccountDeletionAuthorizationTests(TestCase):
    """Tests for account deletion authorization."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

    def test_anonymous_cannot_delete_account(self):
        """Anonymous users cannot delete accounts."""
        response = self.client.delete("/api/me")
        
        # DRF returns 403 for IsAuthenticated permission, which is acceptable
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
        )

    def test_authenticated_user_can_delete_own_account(self):
        """Authenticated users can delete their own account."""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.delete("/api/me")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify user is deactivated
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_ui_mode_does_not_affect_deletion_authorization(self):
        """UI mode does not affect account deletion authorization."""
        user2 = User.objects.create_user(
            username="user2",
            email="user2@example.com",
            password="testpass123"
        )
        self.client.force_authenticate(user=user2)
        
        # Try with read UI mode (should still allow deletion of own account)
        response = self.client.delete("/api/me?ui_mode=read")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify user2 is deactivated
        user2.refresh_from_db()
        self.assertFalse(user2.is_active)
        
        # Try user3 with admin UI mode (should still only delete own account)
        user3 = User.objects.create_user(
            username="user3",
            email="user3@example.com",
            password="testpass123"
        )
        self.client.force_authenticate(user=user3)
        
        # user3 can delete their own account via /api/me
        # UI mode should not grant cross-user deletion capability
        response = self.client.delete("/api/me?ui_mode=admin")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify user3 was deleted (not user2)
        user3.refresh_from_db()
        self.assertFalse(user3.is_active)

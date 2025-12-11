"""
Comprehensive tests for authentication flows.

Tests cover:
- Magic link request and verification
- Email/password login
- Token refresh and rotation
- Token revocation and logout
- User profile retrieval
- Social login callback (mocked)
"""

from unittest.mock import MagicMock, patch

import jwt
from accounts.email.magic_link import generate_magic_link_token
from accounts.models import RefreshToken
from api.utils.tokens import create_access_token, create_refresh_token
from core.models import AuditLog, User
from django.core import mail
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient


class MagicLinkTestCase(TestCase):
    """Tests for magic link authentication flow."""

    def setUp(self):
        """Set up test client and clear email outbox."""
        self.client = APIClient()
        mail.outbox = []

    def test_magic_link_request_sends_email(self):
        """Test that requesting a magic link sends an email."""
        response = self.client.post(
            "/api/auth/magic-link", format="json", data={"email": "test@example.com"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)
        self.assertEqual(response.data["email"], "test@example.com")

        # Check that email was sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("test@example.com", mail.outbox[0].to)
        self.assertIn("Magic Link", mail.outbox[0].subject)

        # Check audit log
        log = AuditLog.objects.filter(action="magic_link.requested").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.detail["email"], "test@example.com")

    def test_magic_link_request_normalizes_email(self):
        """Test that email is normalized to lowercase."""
        response = self.client.post(
            "/api/auth/magic-link", format="json", data={"email": "Test@EXAMPLE.com"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "test@example.com")

    def test_magic_link_verify_creates_new_user(self):
        """Test that verifying a magic link creates a new user."""
        email = "newuser@example.com"
        token = generate_magic_link_token(email)

        response = self.client.post(
            "/api/auth/magic-link/verify", format="json", data={"token": token}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.data)
        self.assertIn("refresh_token", response.data)
        self.assertIn("user", response.data)

        # Check user was created
        user = User.objects.get(email=email)
        self.assertTrue(user.email_verified)
        self.assertFalse(user.has_usable_password())

        # Check audit log
        log = AuditLog.objects.filter(action="user.login.magic_link").first()
        self.assertIsNotNone(log)
        self.assertTrue(log.detail["created"])

    def test_magic_link_verify_existing_user(self):
        """Test that verifying a magic link for existing user works."""
        user = User.objects.create_user(
            username="existing", email="existing@example.com", password="testpass123"
        )
        user.email_verified = False
        user.save()

        token = generate_magic_link_token("existing@example.com")

        response = self.client.post(
            "/api/auth/magic-link/verify", format="json", data={"token": token}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check email was verified
        user.refresh_from_db()
        self.assertTrue(user.email_verified)


class LoginTestCase(TestCase):
    """Tests for email/password login."""

    def setUp(self):
        """Create test user and client."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_login_success(self):
        """Test successful login with correct credentials."""
        response = self.client.post(
            "/api/auth/login",
            format="json",
            data={"email": "test@example.com", "password": "testpass123"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.data)
        self.assertIn("refresh_token", response.data)
        self.assertIn("user", response.data)
        self.assertEqual(response.data["user"]["email"], "test@example.com")

        # Check audit log
        log = AuditLog.objects.filter(action="user.login.password").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.actor_user, self.user)

    def test_login_wrong_password(self):
        """Test login fails with wrong password."""
        response = self.client.post(
            "/api/auth/login",
            format="json",
            data={"email": "test@example.com", "password": "wrongpassword"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_nonexistent_email(self):
        """Test login fails with nonexistent email."""
        response = self.client.post(
            "/api/auth/login",
            format="json",
            data={"email": "nonexistent@example.com", "password": "anypassword"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_inactive_user(self):
        """Test login fails for inactive user."""
        self.user.is_active = False
        self.user.save()

        response = self.client.post(
            "/api/auth/login",
            format="json",
            data={"email": "test@example.com", "password": "testpass123"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TokenRefreshTestCase(TestCase):
    """Tests for token refresh flow."""

    def setUp(self):
        """Create test user and tokens."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        # Create refresh token
        self.refresh_data = create_refresh_token(self.user)
        self.refresh_token = self.refresh_data["refresh_token"]

    def test_token_refresh_success(self):
        """Test successful token refresh."""
        response = self.client.post(
            "/api/auth/token/refresh",
            format="json",
            data={"refresh_token": self.refresh_token},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.data)
        self.assertIn("refresh_token", response.data)

        # New refresh token should be different
        self.assertNotEqual(response.data["refresh_token"], self.refresh_token)

    def test_token_refresh_rotates_token(self):
        """Test that refresh token is rotated (single-use)."""
        # First refresh succeeds
        response1 = self.client.post(
            "/api/auth/token/refresh",
            format="json",
            data={"refresh_token": self.refresh_token},
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # Second refresh with same token fails
        response2 = self.client.post(
            "/api/auth/token/refresh",
            format="json",
            data={"refresh_token": self.refresh_token},
        )
        self.assertEqual(response2.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("error", response2.data)

    def test_token_refresh_invalid_token(self):
        """Test refresh fails with invalid token."""
        response = self.client.post(
            "/api/auth/token/refresh",
            format="json",
            data={"refresh_token": "invalid-token-12345"},
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh_revoked_token(self):
        """Test refresh fails with revoked token."""
        # Revoke the token
        token_obj = RefreshToken.verify_and_get(self.refresh_token)
        token_obj.revoke()

        response = self.client.post(
            "/api/auth/token/refresh",
            format="json",
            data={"refresh_token": self.refresh_token},
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class LogoutTestCase(TestCase):
    """Tests for logout and token revocation."""

    def setUp(self):
        """Create test user and tokens."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        # Create access and refresh tokens
        access_data = create_access_token(self.user)
        self.access_token = access_data["access_token"]

        refresh_data = create_refresh_token(self.user)
        self.refresh_token = refresh_data["refresh_token"]

    def test_logout_with_specific_token(self):
        """Test logout revokes specific refresh token."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        response = self.client.post(
            "/api/auth/logout",
            format="json",
            data={"refresh_token": self.refresh_token},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Token should be revoked
        token_obj = RefreshToken.objects.get(
            token_hash=RefreshToken.hash_token(self.refresh_token)
        )
        self.assertTrue(token_obj.revoked)

    def test_logout_revokes_all_tokens(self):
        """Test logout with revoke_all flag."""
        # Create multiple refresh tokens
        token1 = create_refresh_token(self.user)
        token2 = create_refresh_token(self.user)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        response = self.client.post(
            "/api/auth/logout", format="json", data={"revoke_all": True}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # All tokens should be revoked
        revoked_count = RefreshToken.objects.filter(
            user=self.user, revoked=True
        ).count()
        self.assertGreaterEqual(revoked_count, 3)  # At least 3 tokens created

    def test_logout_requires_authentication(self):
        """Test logout requires valid access token."""
        response = self.client.post("/api/auth/logout")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class MeEndpointTestCase(TestCase):
    """Tests for /auth/me endpoint."""

    def setUp(self):
        """Create test user and tokens."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            display_name="Test User",
        )

        access_data = create_access_token(self.user)
        self.access_token = access_data["access_token"]

    def test_me_returns_user_profile(self):
        """Test /me returns current user profile."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        response = self.client.get("/api/auth/me")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "test@example.com")
        self.assertEqual(response.data["username"], "testuser")
        self.assertEqual(response.data["display_name"], "Test User")

    def test_me_requires_authentication(self):
        """Test /me requires authentication."""
        response = self.client.get("/api/auth/me")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_me_invalid_token(self):
        """Test /me fails with invalid token."""
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid-token")

        response = self.client.get("/api/auth/me")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TokenUtilityTestCase(TestCase):
    """Tests for token utility functions."""

    def setUp(self):
        """Create test user."""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_create_access_token(self):
        """Test access token creation."""
        token_data = create_access_token(self.user)

        self.assertIn("access_token", token_data)
        self.assertIn("token_type", token_data)
        self.assertIn("expires_in", token_data)
        self.assertEqual(token_data["token_type"], "Bearer")

        # Decode and verify token payload
        token = token_data["access_token"]
        from api.utils.tokens import get_jwt_secret

        payload = jwt.decode(token, get_jwt_secret(), algorithms=["HS256"])

        self.assertEqual(payload["sub"], str(self.user.id))
        self.assertEqual(payload["email"], self.user.email)
        self.assertEqual(payload["type"], "access")

    def test_create_refresh_token(self):
        """Test refresh token creation."""
        token_data = create_refresh_token(self.user)

        self.assertIn("refresh_token", token_data)
        self.assertIn("token_id", token_data)
        self.assertIn("expires_in_days", token_data)

        # Verify token is stored in database
        token_obj = RefreshToken.objects.get(id=token_data["token_id"])
        self.assertEqual(token_obj.user, self.user)
        self.assertFalse(token_obj.revoked)
        self.assertFalse(token_obj.is_expired())

    def test_refresh_token_rotation(self):
        """Test refresh token rotation."""
        # Create initial token
        token_data = create_refresh_token(self.user)
        old_token = token_data["refresh_token"]

        # Rotate token
        from api.utils.tokens import rotate_refresh_token

        new_data = rotate_refresh_token(old_token)

        self.assertIn("access_token", new_data)
        self.assertIn("refresh_token", new_data)
        self.assertNotEqual(new_data["refresh_token"], old_token)

        # Old token should be marked as replaced
        old_token_obj = RefreshToken.objects.get(
            token_hash=RefreshToken.hash_token(old_token)
        )
        self.assertIsNotNone(old_token_obj.replaced_by)
        self.assertFalse(old_token_obj.is_valid())


class SocialCallbackTestCase(TestCase):
    """Tests for social login callback."""

    def setUp(self):
        """Set up test client."""
        self.client = APIClient()

    def test_social_callback_placeholder(self):
        """Test social callback returns not implemented."""
        response = self.client.post(
            "/api/auth/social/google/callback",
            format="json",
            data={"code": "test-auth-code", "state": "test-state"},
        )

        # Currently returns 501 Not Implemented as a placeholder
        self.assertEqual(response.status_code, status.HTTP_501_NOT_IMPLEMENTED)
        self.assertIn("provider", response.data)
        self.assertEqual(response.data["provider"], "google")

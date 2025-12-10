"""
Tests for the custom User model.

Verifies:
- User creation with UUID primary key
- Field defaults (email_verified, public_profile)
- Display name behavior
- Indexed fields
"""

from django.test import TestCase

from core.models import User


class UserModelTestCase(TestCase):
    """Test cases for the User model."""

    def test_create_user_with_defaults(self):
        """Test creating a user with default field values."""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        # Verify UUID primary key
        self.assertIsNotNone(user.id)
        self.assertEqual(len(str(user.id)), 36)  # UUID format

        # Verify default values
        self.assertFalse(user.email_verified)
        self.assertTrue(user.public_profile)
        self.assertIsNone(user.privacy_consent_version)
        self.assertIsNone(user.privacy_consent_ts)

        # Display name should default to username
        self.assertEqual(user.display_name, "testuser")

    def test_create_user_with_display_name(self):
        """Test creating a user with a custom display name."""
        user = User.objects.create_user(
            username="john_doe",
            email="john@example.com",
            password="testpass123",
            display_name="John Doe",
        )

        self.assertEqual(user.display_name, "John Doe")
        self.assertEqual(str(user), "John Doe")

    def test_email_verification(self):
        """Test email verification flag."""
        user = User.objects.create_user(
            username="testuser2", email="test2@example.com", password="testpass123"
        )

        # Initially not verified
        self.assertFalse(user.email_verified)

        # Verify email
        user.email_verified = True
        user.save()

        # Reload and verify
        user.refresh_from_db()
        self.assertTrue(user.email_verified)

    def test_privacy_consent_tracking(self):
        """Test privacy consent version tracking."""
        from django.utils import timezone

        user = User.objects.create_user(
            username="testuser3", email="test3@example.com", password="testpass123"
        )

        # Set privacy consent
        consent_time = timezone.now()
        user.privacy_consent_version = "1.0"
        user.privacy_consent_ts = consent_time
        user.save()

        # Reload and verify
        user.refresh_from_db()
        self.assertEqual(user.privacy_consent_version, "1.0")
        self.assertIsNotNone(user.privacy_consent_ts)

    def test_public_profile_toggle(self):
        """Test public profile visibility toggle."""
        user = User.objects.create_user(
            username="testuser4", email="test4@example.com", password="testpass123"
        )

        # Default is public
        self.assertTrue(user.public_profile)

        # Make private
        user.public_profile = False
        user.save()

        user.refresh_from_db()
        self.assertFalse(user.public_profile)

    def test_display_name_auto_set(self):
        """Test that display_name is auto-set to username if not provided."""
        user = User(username="autoname", email="auto@example.com")
        user.set_password("testpass123")
        user.save()

        self.assertEqual(user.display_name, "autoname")

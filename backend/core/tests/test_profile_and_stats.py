"""
Tests for Profile and UserStats models.

Verifies:
- Profile creation and JSON settings
- UserStats counter increments using F() expressions
- One-to-one relationships with User
"""

from django.db.models import F
from django.test import TestCase

from core.models import Profile, User, UserStats


class ProfileModelTestCase(TestCase):
    """Test cases for the Profile model."""

    def setUp(self):
        """Create a test user for profile tests."""
        self.user = User.objects.create_user(
            username="profiletest", email="profile@example.com", password="testpass123"
        )

    def test_create_profile(self):
        """Test creating a user profile."""
        profile = Profile.objects.create(
            user=self.user, bio="Test bio", location_text="Test City"
        )

        self.assertEqual(profile.user, self.user)
        self.assertEqual(profile.bio, "Test bio")
        self.assertEqual(profile.location_text, "Test City")
        self.assertEqual(profile.profile_settings, {})

    def test_profile_json_settings(self):
        """Test updating JSON profile settings."""
        profile = Profile.objects.create(
            user=self.user,
            profile_settings={
                "theme": "dark",
                "language": "en",
                "notifications": {"email": True, "push": False},
            },
        )

        self.assertEqual(profile.profile_settings["theme"], "dark")
        self.assertEqual(profile.profile_settings["language"], "en")
        self.assertTrue(profile.profile_settings["notifications"]["email"])

        # Update settings
        profile.profile_settings["theme"] = "light"
        profile.save()

        profile.refresh_from_db()
        self.assertEqual(profile.profile_settings["theme"], "light")

    def test_profile_one_to_one_relationship(self):
        """Test one-to-one relationship with User."""
        profile = Profile.objects.create(user=self.user)

        # Access profile from user
        self.assertEqual(self.user.profile, profile)


class UserStatsModelTestCase(TestCase):
    """Test cases for the UserStats model."""

    def setUp(self):
        """Create a test user for stats tests."""
        self.user = User.objects.create_user(
            username="statstest", email="stats@example.com", password="testpass123"
        )

    def test_create_user_stats(self):
        """Test creating user statistics."""
        stats = UserStats.objects.create(user=self.user)

        self.assertEqual(stats.user, self.user)
        self.assertEqual(stats.contributions_total, 0)
        self.assertEqual(stats.edits_published, 0)
        self.assertEqual(stats.reviews_approved, 0)
        self.assertEqual(stats.reputation_score, 0.0)
        self.assertIsNone(stats.leaderboard_rank_cache)

    def test_increment_contributions_with_f_expression(self):
        """Test incrementing contributions counter using F() expression."""
        stats = UserStats.objects.create(user=self.user)

        # Increment using the helper method
        stats.increment_contributions(5)
        stats.refresh_from_db()

        self.assertEqual(stats.contributions_total, 5)

        # Increment again
        stats.increment_contributions()
        stats.refresh_from_db()

        self.assertEqual(stats.contributions_total, 6)

    def test_increment_published_counter(self):
        """Test incrementing published edits counter."""
        stats = UserStats.objects.create(user=self.user)

        stats.increment_published(3)
        stats.refresh_from_db()

        self.assertEqual(stats.edits_published, 3)

    def test_increment_approved_counter(self):
        """Test incrementing approved reviews counter."""
        stats = UserStats.objects.create(user=self.user)

        stats.increment_approved(2)
        stats.refresh_from_db()

        self.assertEqual(stats.reviews_approved, 2)

    def test_reputation_score_update(self):
        """Test updating reputation score."""
        stats = UserStats.objects.create(user=self.user)

        stats.reputation_score = 125.5
        stats.save()

        stats.refresh_from_db()
        self.assertEqual(stats.reputation_score, 125.5)

    def test_leaderboard_rank_cache(self):
        """Test leaderboard rank caching."""
        stats = UserStats.objects.create(user=self.user)

        stats.leaderboard_rank_cache = 42
        stats.save()

        stats.refresh_from_db()
        self.assertEqual(stats.leaderboard_rank_cache, 42)

    def test_stats_one_to_one_relationship(self):
        """Test one-to-one relationship with User."""
        stats = UserStats.objects.create(user=self.user)

        # Access stats from user
        self.assertEqual(self.user.stats, stats)

"""
User Profile model for extended user information.

The Profile model stores additional user information that's not part of
core authentication but is used for public display and personalization:
- Bio and avatar for public profiles
- Location information (text-based, user-entered)
- Profile settings as flexible JSON field
"""

from django.conf import settings
from django.db import models


class Profile(models.Model):
    """
    Extended user profile information.

    One-to-one relationship with User model. Created on-demand when
    a user first updates their profile settings.

    Fields:
    - bio: User's self-description
    - avatar_url: URL to user's profile image
    - location_text: User-entered location (not geocoded)
    - profile_settings: Flexible JSON field for UI preferences, notifications, etc.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        help_text="User this profile belongs to",
    )

    bio = models.TextField(
        blank=True,
        max_length=500,
        help_text="User's self-description (max 500 characters)",
    )

    avatar_url = models.URLField(
        blank=True, max_length=500, help_text="URL to user's avatar image"
    )

    location_text = models.CharField(
        max_length=200,
        blank=True,
        help_text="User-entered location text (not geocoded)",
    )

    # Flexible JSON field for storing various profile settings:
    # - UI preferences (theme, language, etc.)
    # - Notification preferences
    # - Privacy settings
    # - Custom fields added by future features
    profile_settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Flexible settings storage (UI prefs, notifications, etc.)",
    )

    created_at = models.DateTimeField(
        auto_now_add=True, help_text="When this profile was created"
    )

    updated_at = models.DateTimeField(
        auto_now=True, help_text="When this profile was last updated"
    )

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"Profile for {self.user.username}"

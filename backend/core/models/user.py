"""
Custom User model for the Gonaj platform.

CRITICAL: This model replaces Django's default auth.User model.
Before running any migrations, you MUST set AUTH_USER_MODEL = "core.User"
in settings.py. This cannot be changed after the first migration is run.

The User model extends AbstractUser to add platform-specific fields:
- UUID primary key for public API exposure
- Display name for public attribution
- Email verification tracking
- Privacy consent tracking
- Public profile visibility control
"""

import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user model for Gonaj platform.

    Extends Django's AbstractUser to add:
    - UUID primary key (instead of auto-incrementing integer)
    - Display name for public-facing attribution
    - Email verification status
    - Privacy consent tracking (GDPR compliance)
    - Public profile visibility toggle

    IMPORTANT: This replaces auth.User. Settings must define:
        AUTH_USER_MODEL = "core.User"
    This setting cannot be changed after running initial migrations.
    """

    # Use UUID as primary key for public API exposure (prevents enumeration)
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the user (UUID v4)",
    )

    # Display name shown in public attributions and leaderboards
    display_name = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Public display name for attributions and leaderboards",
    )

    # Email verification tracking
    email_verified = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether the user has verified their email address",
    )

    # Privacy consent tracking (GDPR/privacy compliance)
    privacy_consent_version = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Version of privacy policy consented to (e.g., '1.0', '2.1')",
    )

    privacy_consent_ts = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when user consented to privacy policy",
    )

    # Public profile visibility toggle
    public_profile = models.BooleanField(
        default=True, help_text="Whether the user's profile is publicly visible"
    )

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        indexes = [
            models.Index(fields=["display_name"]),
            models.Index(fields=["email_verified"]),
        ]

    def __str__(self):
        """Return display name if set, otherwise username."""
        return self.display_name or self.username

    def save(self, *args, **kwargs):
        """Override save to set display_name to username if not provided."""
        if not self.display_name:
            self.display_name = self.username
        super().save(*args, **kwargs)

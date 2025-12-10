"""
Badge system models.

Implements a badge/achievement system with:
- Badge master table defining available badges
- UserBadge junction table for awarded badges
- Unique constraint ensuring each user can only earn each badge once
"""

import uuid

from django.conf import settings
from django.db import models


class Badge(models.Model):
    """
    Master table of available badges/achievements.

    Badges are awarded to users for various accomplishments:
    - Contribution milestones (10 edits, 100 edits, etc.)
    - Quality achievements (5 approved reviews, etc.)
    - Special recognition (early adopter, community helper, etc.)

    Badges are defined by administrators and awarded programmatically
    or manually by moderators.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this badge",
    )

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique name of the badge (e.g., 'first_contribution')",
    )

    display_name = models.CharField(
        max_length=100,
        help_text="Human-readable display name (e.g., 'First Contribution')",
    )

    description = models.TextField(
        help_text="Description of what this badge represents"
    )

    icon_url = models.URLField(
        blank=True, max_length=500, help_text="URL to badge icon image"
    )

    # Badge tier/rarity (e.g., bronze, silver, gold, platinum)
    tier = models.CharField(
        max_length=20,
        blank=True,
        help_text="Badge tier/rarity (bronze, silver, gold, etc.)",
    )

    # Points value of earning this badge
    points = models.IntegerField(
        default=0, help_text="Points awarded for earning this badge"
    )

    # Whether this badge is currently active/earnable
    is_active = models.BooleanField(
        default=True, help_text="Whether this badge is currently active and earnable"
    )

    created_at = models.DateTimeField(
        auto_now_add=True, help_text="When this badge was created"
    )

    class Meta:
        verbose_name = "Badge"
        verbose_name_plural = "Badges"
        ordering = ["tier", "name"]

    def __str__(self):
        return self.display_name


class UserBadge(models.Model):
    """
    Junction table for badges awarded to users.

    Tracks which badges have been awarded to which users, along with
    when the badge was earned. Unique constraint ensures each user
    can only earn each badge once.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="badges",
        help_text="User who earned this badge",
    )

    badge = models.ForeignKey(
        Badge,
        on_delete=models.CASCADE,
        related_name="awarded_to",
        help_text="Badge that was earned",
    )

    earned_at = models.DateTimeField(
        auto_now_add=True, help_text="When the user earned this badge"
    )

    # Optional metadata about how the badge was earned
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Optional metadata about how this badge was earned",
    )

    class Meta:
        verbose_name = "User Badge"
        verbose_name_plural = "User Badges"
        # Ensure each user can only earn each badge once
        constraints = [
            models.UniqueConstraint(fields=["user", "badge"], name="unique_user_badge")
        ]
        ordering = ["-earned_at"]

    def __str__(self):
        return f"{self.user.username} - {self.badge.display_name}"

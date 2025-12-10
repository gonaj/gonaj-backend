"""
User statistics tracking model.

Tracks aggregate statistics for each user related to contributions,
edits, reviews, reputation, and leaderboard rankings. These are
denormalized counters updated by contribution and moderation workflows.
"""

from django.conf import settings
from django.db import models


class UserStats(models.Model):
    """
    Aggregate statistics for a user's contributions and reputation.

    One-to-one relationship with User. These are denormalized counters
    updated by background tasks or signals when contributions are
    created, moderated, or published.

    Fields:
    - contributions_total: Total number of contributions submitted
    - edits_published: Number of edits that have been published
    - reviews_approved: Number of contributions approved by moderators
    - reputation_score: Computed reputation (indexed for leaderboard queries)
    - leaderboard_rank_cache: Cached global rank (updated periodically)
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="stats",
        help_text="User these stats belong to",
    )

    contributions_total = models.BigIntegerField(
        default=0, help_text="Total number of contributions submitted by this user"
    )

    edits_published = models.BigIntegerField(
        default=0, help_text="Number of contributions that have been published"
    )

    reviews_approved = models.BigIntegerField(
        default=0, help_text="Number of contributions approved by moderators"
    )

    # Reputation score - computed from various factors (points, approvals, etc.)
    # Indexed for efficient leaderboard queries
    reputation_score = models.FloatField(
        default=0.0,
        db_index=True,
        help_text="Computed reputation score (indexed for leaderboard queries)",
    )

    # Cached leaderboard rank (updated periodically by background job)
    leaderboard_rank_cache = models.IntegerField(
        null=True,
        blank=True,
        help_text="Cached global leaderboard rank (updated periodically)",
    )

    # Track when stats were last updated
    updated_at = models.DateTimeField(
        auto_now=True, help_text="When these stats were last updated"
    )

    class Meta:
        verbose_name = "User Statistics"
        verbose_name_plural = "User Statistics"
        indexes = [
            models.Index(fields=["-reputation_score"]),  # Descending for leaderboard
        ]

    def __str__(self):
        return f"Stats for {self.user.username}"

    def increment_contributions(self, amount=1):
        """
        Increment total contributions counter.

        Use F() expression to avoid race conditions when incrementing counters.
        Call refresh_from_db() after to get updated value.
        """
        from django.db.models import F

        UserStats.objects.filter(pk=self.pk).update(
            contributions_total=F("contributions_total") + amount
        )

    def increment_published(self, amount=1):
        """Increment published edits counter using F() expression."""
        from django.db.models import F

        UserStats.objects.filter(pk=self.pk).update(
            edits_published=F("edits_published") + amount
        )

    def increment_approved(self, amount=1):
        """Increment approved reviews counter using F() expression."""
        from django.db.models import F

        UserStats.objects.filter(pk=self.pk).update(
            reviews_approved=F("reviews_approved") + amount
        )

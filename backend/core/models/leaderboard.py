"""
Leaderboard system for gamification and user engagement.

The LeaderboardEntry model tracks user rankings across different time
periods (all-time, monthly, weekly) to enable competitive features and
recognition of top contributors.
"""

from django.conf import settings
from django.db import models


class LeaderboardEntry(models.Model):
    """
    Leaderboard entry for tracking user rankings.

    Tracks user rankings across different time periods:
    - 'all-time': Overall lifetime rankings
    - 'monthly-YYYY-MM': Monthly rankings (e.g., 'monthly-2025-12')
    - 'weekly-YYYY-WW': Weekly rankings (e.g., 'weekly-2025-50')

    Leaderboard entries are computed periodically by background jobs
    that aggregate user points and contributions for each period.

    The unique constraint on (period, user) ensures each user appears
    once per leaderboard period.
    """

    # Auto-incrementing PK (not exposed in API)
    id = models.AutoField(
        primary_key=True, help_text="Internal ID for this leaderboard entry"
    )

    # Period identifier (e.g., 'all-time', 'monthly-2025-12', 'weekly-2025-50')
    period = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Period identifier (all-time, monthly-YYYY-MM, weekly-YYYY-WW)",
    )

    # User being ranked
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="leaderboard_entries",
        help_text="User being ranked",
    )

    # Rank within this period (1 = first place)
    rank = models.IntegerField(help_text="Rank within this period (1 = first place)")

    # Points for this period
    points = models.IntegerField(default=0, help_text="Points earned in this period")

    # Additional metadata (contributions count, badges earned, etc.)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metrics (contributions, badges, etc.)",
    )

    # When this entry was last updated
    updated_at = models.DateTimeField(
        auto_now=True, help_text="When this leaderboard entry was last updated"
    )

    class Meta:
        verbose_name = "Leaderboard Entry"
        verbose_name_plural = "Leaderboard Entries"
        # Ensure each user appears once per period
        constraints = [
            models.UniqueConstraint(
                fields=["period", "user"], name="unique_period_user"
            )
        ]
        indexes = [
            models.Index(fields=["period", "rank"]),
            models.Index(fields=["period", "-points"]),
        ]
        ordering = ["period", "rank"]

    def __str__(self):
        return f"{self.period} - Rank {self.rank}: {self.user.username} ({self.points} pts)"

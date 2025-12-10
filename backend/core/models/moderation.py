"""
Moderation system for contribution review and approval.

The ModerationEntry model tracks all moderation actions taken on
contributions, creating an audit trail of reviews, approvals,
rejections, and flags.
"""

from django.conf import settings
from django.db import models


class ModerationEntry(models.Model):
    """
    Log entry for moderation actions on contributions.

    Tracks who moderated a contribution, what action they took, and why.
    Creates an immutable audit trail of all moderation decisions.

    Actions:
    - approve: Contribution is valid and should be published
    - reject: Contribution is invalid or low quality
    - flag: Contribution needs additional review
    - publish: Approved contribution has been published to GTFS
    """

    # Moderation action choices
    ACTION_APPROVE = "approve"
    ACTION_REJECT = "reject"
    ACTION_FLAG = "flag"
    ACTION_PUBLISH = "publish"

    ACTION_CHOICES = [
        (ACTION_APPROVE, "Approve"),
        (ACTION_REJECT, "Reject"),
        (ACTION_FLAG, "Flag for Review"),
        (ACTION_PUBLISH, "Publish"),
    ]

    contribution = models.ForeignKey(
        "Contribution",
        on_delete=models.CASCADE,
        related_name="moderation_log",
        help_text="Contribution being moderated",
    )

    # Moderator (null for automated decisions)
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderation_actions",
        help_text="User who performed this moderation action (null for automated)",
    )

    action = models.CharField(
        max_length=20, choices=ACTION_CHOICES, help_text="Moderation action taken"
    )

    reason = models.TextField(
        blank=True, help_text="Text explanation for the moderation decision"
    )

    # Store previous and new status for audit trail
    previous_status = models.CharField(
        max_length=20, blank=True, help_text="Status before this moderation action"
    )

    new_status = models.CharField(
        max_length=20, blank=True, help_text="Status after this moderation action"
    )

    # Additional metadata about the decision
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (automated checks, confidence scores, etc.)",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When this moderation action was taken",
    )

    class Meta:
        verbose_name = "Moderation Entry"
        verbose_name_plural = "Moderation Entries"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["contribution", "-created_at"]),
            models.Index(fields=["moderator", "-created_at"]),
        ]

    def __str__(self):
        moderator_name = self.moderator.username if self.moderator else "Automated"
        return f"{moderator_name} - {self.action} - {self.contribution.type}"

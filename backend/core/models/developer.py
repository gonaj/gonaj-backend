"""
Developer and API client management.

The Developer model represents third-party developers and API clients
that integrate with the Gonaj platform. Developers can submit contributions
via API and are tracked separately from end users.
"""

import uuid

from django.db import models


class Developer(models.Model):
    """
    Third-party developer or API client.

    Represents organizations or individuals who integrate with the
    Gonaj platform via API. Developers can:
    - Submit contributions via API
    - Access bulk data exports
    - Integrate with external systems
    - Attribute contributions to external user IDs

    Developers are verified by administrators and assigned tiers that
    determine their API rate limits and feature access.
    """

    # Tier choices for API access levels
    TIER_FREE = "free"
    TIER_BASIC = "basic"
    TIER_PREMIUM = "premium"
    TIER_ENTERPRISE = "enterprise"

    TIER_CHOICES = [
        (TIER_FREE, "Free"),
        (TIER_BASIC, "Basic"),
        (TIER_PREMIUM, "Premium"),
        (TIER_ENTERPRISE, "Enterprise"),
    ]

    # UUID primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this developer",
    )

    # Developer name/organization
    name = models.CharField(max_length=200, help_text="Developer or organization name")

    # Contact information
    contact_email = models.EmailField(help_text="Contact email for this developer")

    website = models.URLField(
        blank=True, max_length=500, help_text="Developer website or documentation URL"
    )

    # Verification status
    verified = models.BooleanField(
        default=False,
        help_text="Whether this developer has been verified by administrators",
    )

    # API tier (determines rate limits and features)
    tier = models.CharField(
        max_length=20,
        choices=TIER_CHOICES,
        default=TIER_FREE,
        help_text="API access tier",
    )

    # Additional notes (internal use)
    notes = models.TextField(
        blank=True, help_text="Internal notes about this developer"
    )

    # Whether this developer account is active
    is_active = models.BooleanField(
        default=True, help_text="Whether this developer account is active"
    )

    created_at = models.DateTimeField(
        auto_now_add=True, help_text="When this developer account was created"
    )

    updated_at = models.DateTimeField(
        auto_now=True, help_text="When this developer account was last updated"
    )

    class Meta:
        verbose_name = "Developer"
        verbose_name_plural = "Developers"
        ordering = ["-created_at"]

    def __str__(self):
        status = "✓" if self.verified else "✗"
        return f"{status} {self.name} ({self.tier})"

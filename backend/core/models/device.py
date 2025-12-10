"""
Device tracking for mobile app usage analytics.

The Device model tracks mobile devices that access the platform,
enabling device-specific features, analytics, and user preferences.
"""

import uuid

from django.conf import settings
from django.db import models


class Device(models.Model):
    """
    Mobile device registration and tracking.

    Tracks devices that access the platform via mobile apps or SDKs.
    Used for:
    - Device-specific push notifications
    - Usage analytics and app metrics
    - Device-level feature flags and A/B testing
    - Opt-in/opt-out preferences

    Devices can be associated with a user (for logged-in usage) or
    anonymous (for tracking pre-authentication usage).
    """

    # Platform choices
    PLATFORM_IOS = "ios"
    PLATFORM_ANDROID = "android"
    PLATFORM_WEB = "web"
    PLATFORM_OTHER = "other"

    PLATFORM_CHOICES = [
        (PLATFORM_IOS, "iOS"),
        (PLATFORM_ANDROID, "Android"),
        (PLATFORM_WEB, "Web"),
        (PLATFORM_OTHER, "Other"),
    ]

    # UUID primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this device",
    )

    # Optional user association (null for anonymous devices)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="devices",
        help_text="User this device is associated with (null for anonymous)",
    )

    # SDK/app version
    sdk_version = models.CharField(
        max_length=50, blank=True, help_text="SDK or app version (e.g., '1.2.3')"
    )

    # Platform
    platform = models.CharField(
        max_length=20,
        choices=PLATFORM_CHOICES,
        default=PLATFORM_OTHER,
        help_text="Device platform",
    )

    # Device info (OS version, model, etc.)
    device_info = models.CharField(
        max_length=200,
        blank=True,
        help_text="Device information (OS version, model, etc.)",
    )

    # Last seen timestamp
    last_seen = models.DateTimeField(
        auto_now=True,
        db_index=True,
        help_text="When this device last accessed the platform",
    )

    # Opt-in flags for various features
    opt_in_flags = models.JSONField(
        default=dict,
        blank=True,
        help_text="Opt-in preferences (analytics, notifications, etc.)",
    )

    # Additional metadata
    metadata = models.JSONField(
        default=dict, blank=True, help_text="Additional device metadata"
    )

    # Push notification token (for mobile push)
    push_token = models.CharField(
        max_length=500, blank=True, help_text="Push notification token (FCM/APNS)"
    )

    created_at = models.DateTimeField(
        auto_now_add=True, help_text="When this device was first registered"
    )

    class Meta:
        verbose_name = "Device"
        verbose_name_plural = "Devices"
        indexes = [
            models.Index(fields=["user", "-last_seen"]),
            models.Index(fields=["platform", "-last_seen"]),
        ]
        ordering = ["-last_seen"]

    def __str__(self):
        user_str = f" ({self.user.username})" if self.user else " (anonymous)"
        return f"{self.platform} - {self.sdk_version}{user_str}"

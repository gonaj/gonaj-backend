"""
Audit logging for security and compliance.

The AuditLog model provides append-only logging of all significant
actions in the system for security auditing, compliance, and debugging.
"""

from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """
    Append-only audit log for security and compliance.

    Records all significant actions in the system:
    - User authentication events (login, logout, password changes)
    - Contribution creation and modification
    - Moderation actions
    - API access
    - Permission changes
    - Data exports

    Fields track both authenticated users and API developers, along with
    IP address and user agent for security analysis.

    This table is append-only and should never be modified or deleted
    except as part of data retention policies.
    """

    # Use BigAutoField for very high-volume logging
    id = models.BigAutoField(
        primary_key=True, help_text="Auto-incrementing ID for audit log entries"
    )

    # Timestamp - indexed for time-based queries
    created_at = models.DateTimeField(
        auto_now_add=True, db_index=True, help_text="When this action occurred"
    )

    # === Actor Attribution ===

    # Authenticated user who performed the action (if any)
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        help_text="User who performed this action",
    )

    # Developer/API client (if action via API)
    actor_developer = models.ForeignKey(
        "Developer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        help_text="Developer/API client that performed this action",
    )

    # === Action Details ===

    # Action type (e.g., 'user.login', 'contribution.create', 'moderation.approve')
    action = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Type of action (e.g., 'user.login', 'contribution.create')",
    )

    # Object being acted upon
    object_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Type of object affected (e.g., 'Contribution', 'User')",
    )

    object_id = models.CharField(
        max_length=100, blank=True, help_text="ID of the object affected"
    )

    # === Request Context ===

    # IP address of the request
    ip_address = models.GenericIPAddressField(
        null=True, blank=True, help_text="IP address of the request"
    )

    # User agent string
    user_agent = models.TextField(
        blank=True, help_text="User agent string from the request"
    )

    # Additional details in JSON format
    detail = models.JSONField(
        default=dict, blank=True, help_text="Additional details about this action"
    )

    class Meta:
        verbose_name = "Audit Log Entry"
        verbose_name_plural = "Audit Log Entries"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "-created_at"]),
            models.Index(fields=["actor_user", "-created_at"]),
            models.Index(fields=["object_type", "object_id"]),
        ]

    def __str__(self):
        actor = "System"
        if self.actor_user:
            actor = self.actor_user.username
        elif self.actor_developer:
            actor = f"Developer: {self.actor_developer.name}"
        return f"{actor} - {self.action} at {self.created_at}"

    @classmethod
    def log(
        cls,
        action,
        actor_user=None,
        actor_developer=None,
        object_type="",
        object_id="",
        ip_address=None,
        user_agent="",
        detail=None,
    ):
        """
        Create an audit log entry.

        This is the primary interface for creating audit logs throughout
        the application.

        Args:
            action: Action type (e.g., 'user.login', 'contribution.create')
            actor_user: User performing the action (optional)
            actor_developer: Developer performing the action (optional)
            object_type: Type of object affected (optional)
            object_id: ID of object affected (optional)
            ip_address: IP address of request (optional)
            user_agent: User agent string (optional)
            detail: Additional details dict (optional)

        Returns:
            AuditLog instance

        Example:
            AuditLog.log(
                action='contribution.create',
                actor_user=request.user,
                object_type='Contribution',
                object_id=str(contribution.id),
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                detail={'type': contribution.type}
            )
        """
        return cls.objects.create(
            action=action,
            actor_user=actor_user,
            actor_developer=actor_developer,
            object_type=object_type,
            object_id=str(object_id) if object_id else "",
            ip_address=ip_address,
            user_agent=user_agent or "",
            detail=detail or {},
        )

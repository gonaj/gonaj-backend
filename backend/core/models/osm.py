"""
OpenStreetMap integration credentials.

Stores OAuth credentials for users who link their OSM accounts,
enabling automatic attribution and cross-platform contribution tracking.

SECURITY NOTE: Token fields must be encrypted in production.
This Sprint-1 implementation includes TODO markers for encryption.
Sprint-2 should implement field-level encryption using django-encrypted-fields
or integration with a secrets vault (e.g., HashiCorp Vault, AWS Secrets Manager).
"""

from django.conf import settings
from django.db import models


class OSMCredential(models.Model):
    """
    OpenStreetMap OAuth credentials for users.

    Stores OAuth tokens for users who have linked their OSM accounts.
    This enables:
    - Automatic OSM attribution for contributions
    - Cross-platform contribution tracking
    - OSM API access on behalf of users
    - Integration with OSM editing tools

    SECURITY WARNING:
    Token fields (access_token_enc, refresh_token_enc) contain sensitive
    OAuth credentials and MUST be encrypted at rest in production.

    TODO (Sprint-2 or before production):
    - Implement field-level encryption using django-encrypted-fields
      OR integrate with secrets vault (HashiCorp Vault, AWS Secrets Manager)
    - Add token rotation mechanism
    - Implement token revocation on user request
    - Add audit logging for token access
    """

    # One-to-one relationship with User
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="osm_credential",
        help_text="User who linked this OSM account",
    )

    # OSM user information
    osm_user_id = models.BigIntegerField(unique=True, help_text="OpenStreetMap user ID")

    osm_username = models.CharField(max_length=255, help_text="OpenStreetMap username")

    # OAuth tokens
    # TODO (CRITICAL - Sprint-2): ENCRYPT THESE FIELDS
    # Option 1: Use django-encrypted-fields
    #   from encrypted_fields import fields
    #   access_token_enc = fields.EncryptedCharField(max_length=500)
    # Option 2: Use secrets vault and store only reference
    #   access_token_vault_path = models.CharField(max_length=200)

    access_token_enc = models.CharField(
        max_length=500, help_text="OAuth access token (TODO: ENCRYPT THIS FIELD)"
    )

    # TODO (CRITICAL - Sprint-2): ENCRYPT THIS FIELD
    refresh_token_enc = models.CharField(
        max_length=500,
        blank=True,
        help_text="OAuth refresh token (TODO: ENCRYPT THIS FIELD)",
    )

    # Token expiration
    token_expires_at = models.DateTimeField(
        null=True, blank=True, help_text="When the access token expires"
    )

    # Linking timestamps
    linked_at = models.DateTimeField(
        auto_now_add=True, help_text="When the OSM account was first linked"
    )

    last_used_at = models.DateTimeField(
        null=True, blank=True, help_text="When the OSM credentials were last used"
    )

    class Meta:
        verbose_name = "OSM Credential"
        verbose_name_plural = "OSM Credentials"
        indexes = [
            models.Index(fields=["osm_user_id"]),
        ]

    def __str__(self):
        return f"OSM: {self.osm_username} (linked to {self.user.username})"

    def is_token_expired(self):
        """
        Check if the access token has expired.

        Returns:
            True if token has expired, False otherwise
        """
        if not self.token_expires_at:
            return False

        from django.utils import timezone

        return timezone.now() >= self.token_expires_at

    # TODO (Sprint-2): Add methods for token refresh
    # def refresh_access_token(self):
    #     """Refresh the access token using the refresh token."""
    #     pass

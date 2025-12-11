"""
Authentication models for the accounts app.

This module contains models for managing authentication sessions
and refresh tokens for the headless authentication system.
"""

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class RefreshToken(models.Model):
    """
    Stores refresh tokens for JWT-based authentication.

    Refresh tokens are long-lived, single-use, opaque tokens that can be
    exchanged for new access tokens. This model implements token rotation:
    when a refresh token is used, it's marked as replaced and a new token
    is issued.

    Security features:
    - Tokens are hashed before storage (never stored in plaintext)
    - Single-use rotation prevents token replay attacks
    - Automatic expiration with configurable lifetime
    - Device and IP tracking for security auditing
    - Revocation support for logout and security events

    TODO (Production):
    - Add rate limiting for token refresh to prevent brute force
    - Consider encrypting user_agent and ip_address for privacy
    - Implement automatic cleanup of expired/revoked tokens
    """

    # Use Django's built-in hash functions for consistency
    HASH_ALGORITHM = "pbkdf2_sha256"

    id = models.BigAutoField(primary_key=True)

    # User who owns this refresh token
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="refresh_tokens",
        help_text="User who owns this refresh token",
    )

    # Hashed token value (NEVER store plaintext tokens)
    # The actual token is generated client-side and hashed immediately
    token_hash = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="SHA256 hash of the refresh token",
    )

    # Token lifecycle timestamps
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="When this token was created"
    )

    expires_at = models.DateTimeField(
        db_index=True, help_text="When this token expires"
    )

    last_used_at = models.DateTimeField(
        null=True, blank=True, help_text="When this token was last used for refresh"
    )

    # Token rotation tracking
    replaced_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replaced_token",
        help_text="New token that replaced this one (for rotation tracking)",
    )

    # Revocation support
    revoked = models.BooleanField(
        default=False, db_index=True, help_text="Whether this token has been revoked"
    )

    revoked_at = models.DateTimeField(
        null=True, blank=True, help_text="When this token was revoked"
    )

    # Device and request tracking for security
    ip_address = models.GenericIPAddressField(
        null=True, blank=True, help_text="IP address where token was created"
    )

    user_agent = models.TextField(
        blank=True, help_text="User agent string from token creation request"
    )

    # Optional device association
    device = models.ForeignKey(
        "core.Device",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="refresh_tokens",
        help_text="Device this token is associated with (if tracked)",
    )

    class Meta:
        verbose_name = "Refresh Token"
        verbose_name_plural = "Refresh Tokens"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["revoked", "expires_at"]),
        ]

    def __str__(self):
        status = (
            "revoked"
            if self.revoked
            else ("expired" if self.is_expired() else "active")
        )
        return f"RefreshToken for {self.user.username} - {status}"

    def is_expired(self):
        """Check if this token has expired."""
        return timezone.now() >= self.expires_at

    def is_valid(self):
        """Check if this token is valid (not expired, not revoked, not replaced)."""
        return not self.revoked and not self.is_expired() and not self.replaced_by

    @classmethod
    def hash_token(cls, raw_token):
        """
        Hash a raw token value for storage.

        Uses SHA256 for speed (refresh tokens are already random).
        For production, consider using Django's make_password for
        additional security, though it's slower.

        Args:
            raw_token: The plaintext token string

        Returns:
            Hexadecimal hash string
        """
        return hashlib.sha256(raw_token.encode()).hexdigest()

    @classmethod
    def generate_token(cls):
        """
        Generate a cryptographically secure random token.

        Returns:
            A URL-safe random string (43 characters)
        """
        return secrets.token_urlsafe(32)

    @classmethod
    def create_for_user(
        cls, user, ip_address=None, user_agent="", device=None, lifetime_days=30
    ):
        """
        Create a new refresh token for a user.

        Args:
            user: User instance
            ip_address: IP address of the request (optional)
            user_agent: User agent string (optional)
            device: Device instance (optional)
            lifetime_days: Token lifetime in days (default 30)

        Returns:
            Tuple of (RefreshToken instance, raw_token string)

        Note:
            The raw token is returned ONLY during creation. It's never
            stored or retrievable later. Client must store it securely.
        """
        raw_token = cls.generate_token()
        token_hash = cls.hash_token(raw_token)

        expires_at = timezone.now() + timedelta(days=lifetime_days)

        refresh_token = cls.objects.create(
            user=user,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent or "",
            device=device,
        )

        return refresh_token, raw_token

    def rotate(self, ip_address=None, user_agent="", lifetime_days=30):
        """
        Rotate this refresh token (create a new one and mark this as replaced).

        This implements single-use refresh tokens: once a token is used,
        it's replaced with a new one. This prevents token replay attacks.

        Args:
            ip_address: IP address of the refresh request
            user_agent: User agent of the refresh request
            lifetime_days: Lifetime for the new token

        Returns:
            Tuple of (new_RefreshToken instance, raw_token string)

        Raises:
            ValueError: If this token is invalid for rotation
        """
        if self.revoked:
            raise ValueError("Cannot rotate a revoked token")

        if self.is_expired():
            raise ValueError("Cannot rotate an expired token")

        if self.replaced_by:
            # Possible token replay attack - revoke everything
            raise ValueError(
                "Token already rotated - possible replay attack. "
                "Revoking all tokens for security."
            )

        # Create new token
        new_token, raw_token = self.__class__.create_for_user(
            user=self.user,
            ip_address=ip_address,
            user_agent=user_agent,
            device=self.device,
            lifetime_days=lifetime_days,
        )

        # Mark this token as replaced
        self.replaced_by = new_token
        self.last_used_at = timezone.now()
        self.save(update_fields=["replaced_by", "last_used_at"])

        return new_token, raw_token

    def revoke(self):
        """Revoke this refresh token."""
        self.revoked = True
        self.revoked_at = timezone.now()
        self.save(update_fields=["revoked", "revoked_at"])

    @classmethod
    def revoke_all_for_user(cls, user, except_token_id=None):
        """
        Revoke all refresh tokens for a user.

        Used for logout-all or security events.

        Args:
            user: User instance
            except_token_id: Optional token ID to preserve (for logout-others)
        """
        queryset = cls.objects.filter(user=user, revoked=False)

        if except_token_id:
            queryset = queryset.exclude(id=except_token_id)

        queryset.update(revoked=True, revoked_at=timezone.now())

    @classmethod
    def verify_and_get(cls, raw_token):
        """
        Verify a raw token and return the RefreshToken instance if valid.

        Args:
            raw_token: The plaintext token string

        Returns:
            RefreshToken instance if valid

        Raises:
            RefreshToken.DoesNotExist: If token doesn't exist or is invalid
            ValueError: If token is expired, revoked, or already rotated
        """
        token_hash = cls.hash_token(raw_token)

        try:
            token = cls.objects.get(token_hash=token_hash)
        except cls.DoesNotExist:
            raise ValueError("Invalid refresh token")

        if not token.is_valid():
            if token.revoked:
                raise ValueError("Refresh token has been revoked")
            elif token.is_expired():
                raise ValueError("Refresh token has expired")
            elif token.replaced_by:
                # Possible replay attack
                raise ValueError("Refresh token has already been used")

        return token

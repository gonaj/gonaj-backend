"""
Authentication serializers for DRF endpoints.

This module contains serializers for all authentication flows:
- Magic link request and verification
- Email/password login
- Token refresh and revocation
- User profile retrieval
- Social login callback
"""

from core.models import User
from django.contrib.auth import authenticate
from rest_framework import serializers


class MagicLinkRequestSerializer(serializers.Serializer):
    """
    Serializer for requesting a magic link.

    Input:
        - email: Email address to send magic link to

    The email will be sent a magic link that can be used for
    passwordless authentication.
    """

    email = serializers.EmailField(
        required=True, help_text="Email address to send magic link to"
    )

    def validate_email(self, value):
        """Normalize email to lowercase."""
        return value.lower().strip()


class MagicLinkVerifySerializer(serializers.Serializer):
    """
    Serializer for verifying a magic link token.

    Input:
        - token: Signed magic link token from email

    Output:
        - User is created or retrieved
        - Access and refresh tokens are issued
    """

    token = serializers.CharField(
        required=True, help_text="Signed magic link token from email"
    )


class LoginSerializer(serializers.Serializer):
    """
    Serializer for email/password login.

    Input:
        - email: User email address
        - password: User password

    Output:
        - Access and refresh tokens if credentials are valid
    """

    email = serializers.EmailField(required=True, help_text="Email address")
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={"input_type": "password"},
        help_text="Password",
    )

    def validate_email(self, value):
        """Normalize email to lowercase."""
        return value.lower().strip()

    def validate(self, attrs):
        """
        Validate credentials and authenticate user.

        Raises:
            ValidationError if credentials are invalid
        """
        email = attrs.get("email")
        password = attrs.get("password")

        # Try to get user by email
        try:
            user = User.objects.get(email=email)
            username = user.username
        except User.DoesNotExist:
            raise serializers.ValidationError(
                "Invalid email or password", code="authentication_failed"
            )

        # Authenticate with username (Django's default auth uses username)
        user = authenticate(username=username, password=password)

        if user is None:
            raise serializers.ValidationError(
                "Invalid email or password", code="authentication_failed"
            )

        if not user.is_active:
            raise serializers.ValidationError(
                "User account is disabled", code="account_disabled"
            )

        attrs["user"] = user
        return attrs


class TokenRefreshSerializer(serializers.Serializer):
    """
    Serializer for refreshing access tokens.

    Input:
        - refresh_token: Opaque refresh token

    Output:
        - New access token
        - New refresh token (rotated, old one is invalidated)
    """

    refresh_token = serializers.CharField(
        required=True,
        write_only=True,
        help_text="Refresh token to exchange for new access token",
    )


class TokenRevokeSerializer(serializers.Serializer):
    """
    Serializer for revoking refresh tokens.

    Input:
        - refresh_token: Token to revoke
        - revoke_all: Whether to revoke all user tokens (optional)
    """

    refresh_token = serializers.CharField(
        required=True, write_only=True, help_text="Refresh token to revoke"
    )
    revoke_all = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Revoke all refresh tokens for this user",
    )


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile information.

    Used by the /auth/me endpoint to return current user data.
    """

    id = serializers.UUIDField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "display_name",
            "email_verified",
            "public_profile",
            "date_joined",
            "last_login",
        ]
        read_only_fields = fields


class SocialCallbackSerializer(serializers.Serializer):
    """
    Serializer for social login callback.

    Input:
        - provider: Social provider name (e.g., 'google')
        - code: Authorization code from provider
        - state: State parameter for CSRF protection (optional)

    Output:
        - Access and refresh tokens
        - User info
    """

    code = serializers.CharField(
        required=True, help_text="Authorization code from social provider"
    )
    state = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="State parameter for CSRF protection",
    )
    redirect_uri = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Redirect URI used in authorization request",
    )

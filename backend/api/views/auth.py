"""
Authentication API views.

This module implements all authentication endpoints for the headless
authentication system using Django REST Framework.

Endpoints:
- POST /v1/auth/magic-link - Request magic link
- POST /v1/auth/magic-link/verify - Verify magic link and get tokens
- POST /v1/auth/login - Email/password login
- POST /v1/auth/logout - Logout and revoke tokens
- POST /v1/auth/token/refresh - Refresh access token
- POST /v1/auth/token/revoke - Revoke refresh token
- GET /v1/auth/me - Get current user profile
- POST /v1/auth/social/<provider>/callback - Social login callback
"""

from accounts.email.magic_link import (
    generate_magic_link_token,
    send_magic_link_email,
    validate_magic_link_token,
)
from core.models import AuditLog, User
from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions as drf_exceptions
from rest_framework import status
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers.auth import (
    LoginSerializer,
    MagicLinkRequestSerializer,
    MagicLinkVerifySerializer,
    SocialCallbackSerializer,
    TokenRefreshSerializer,
    TokenRevokeSerializer,
    UserProfileSerializer,
)
from api.utils.tokens import (
    create_access_token,
    create_refresh_token,
    get_user_from_token,
    revoke_all_refresh_tokens,
    revoke_refresh_token,
    rotate_refresh_token,
    validate_access_token,
)


def get_client_ip(request):
    """Extract client IP address from request."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def get_user_agent(request):
    """Extract user agent from request."""
    return request.META.get("HTTP_USER_AGENT", "")


class JWTAuthentication(BaseAuthentication):
    """
    Custom authentication class for JWT tokens.

    Extracts token from Authorization header (Bearer token)
    and validates it.
    """

    def authenticate(self, request):
        """
        Authenticate the request and return a two-tuple of (user, token).
        """
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")

        if not auth_header.startswith("Bearer "):
            return None

        token = auth_header.replace("Bearer ", "", 1)

        try:
            user = get_user_from_token(token)
            return (user, token)
        except (ValueError, User.DoesNotExist):
            raise drf_exceptions.AuthenticationFailed("Invalid or expired token")


class MagicLinkRequestView(APIView):
    """
    POST /v1/auth/magic-link

    Request a magic link for passwordless authentication.

    Request body:
        {
            "email": "user@example.com"
        }

    Response (200):
        {
            "message": "Magic link sent to your email",
            "email": "user@example.com"
        }

    The magic link will be sent to the provided email address.
    The link is valid for 15 minutes.

    TODO:
    - Implement rate limiting (max N requests per email per hour)
    - Add idempotency key support
    - Track magic link requests in analytics
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = MagicLinkRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]

        # Generate magic link token
        token = generate_magic_link_token(email)

        # Send email (in production, this should be async via Celery)
        try:
            send_magic_link_email(email, token, request)
        except Exception as e:
            # Log error but don't expose it to user
            AuditLog.log(
                action="magic_link.send_failed",
                object_type="User",
                object_id=email,
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request),
                detail={"error": str(e), "email": email},
            )
            # Return success anyway to prevent email enumeration
            pass

        # Log the request
        AuditLog.log(
            action="magic_link.requested",
            object_type="User",
            object_id=email,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            detail={"email": email},
        )

        return Response(
            {
                "message": "Magic link sent to your email",
                "email": email,
            },
            status=status.HTTP_200_OK,
        )


class MagicLinkVerifyView(APIView):
    """
    POST /v1/auth/magic-link/verify

    Verify a magic link token and issue access/refresh tokens.

    Request body:
        {
            "token": "<signed-token-from-email>"
        }

    Response (200):
        {
            "access_token": "<jwt>",
            "token_type": "Bearer",
            "expires_in": 900,
            "expires_at": "2025-12-10T12:00:00Z",
            "refresh_token": "<opaque-token>",
            "refresh_token_id": 123,
            "refresh_expires_in_days": 30,
            "user": {
                "id": "uuid",
                "email": "user@example.com",
                ...
            }
        }

    If the email doesn't exist, a new user is created.
    """

    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = MagicLinkVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data["token"]

        # Validate token and extract email
        try:
            email = validate_magic_link_token(token)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Get or create user
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": email.split("@")[0],  # Simple username from email
                "email_verified": True,  # Mark as verified since they clicked the link
            },
        )

        if created:
            # Set unusable password for passwordless users
            user.set_unusable_password()
            user.save()
        else:
            # Mark email as verified
            if not user.email_verified:
                user.email_verified = True
                user.save(update_fields=["email_verified"])

        # Update last login
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        # Create tokens
        access_token_data = create_access_token(user)
        refresh_token_data = create_refresh_token(
            user, ip_address=get_client_ip(request), user_agent=get_user_agent(request)
        )

        # Log the login
        AuditLog.log(
            action="user.login.magic_link",
            actor_user=user,
            object_type="User",
            object_id=str(user.id),
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            detail={"email": email, "created": created},
        )

        # Return tokens and user info
        return Response(
            {
                **access_token_data,
                **refresh_token_data,
                "user": UserProfileSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class LoginView(APIView):
    """
    POST /v1/auth/login

    Login with email and password.

    Request body:
        {
            "email": "user@example.com",
            "password": "password123"
        }

    Response (200):
        {
            "access_token": "<jwt>",
            "token_type": "Bearer",
            "expires_in": 900,
            "refresh_token": "<opaque-token>",
            "user": {...}
        }

    Response (400/401):
        {
            "error": "Invalid email or password"
        }
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        # Update last login
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        # Create tokens
        access_token_data = create_access_token(user)
        refresh_token_data = create_refresh_token(
            user, ip_address=get_client_ip(request), user_agent=get_user_agent(request)
        )

        # Log the login
        AuditLog.log(
            action="user.login.password",
            actor_user=user,
            object_type="User",
            object_id=str(user.id),
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            detail={"email": user.email},
        )

        return Response(
            {
                **access_token_data,
                **refresh_token_data,
                "user": UserProfileSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """
    POST /v1/auth/logout

    Logout and revoke refresh tokens.

    Request body (optional):
        {
            "refresh_token": "<token>",  # If not provided, revokes all
            "revoke_all": false          # Set to true to revoke all tokens
        }

    Response (200):
        {
            "message": "Logged out successfully"
        }
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        refresh_token = request.data.get("refresh_token")
        revoke_all = request.data.get("revoke_all", False)

        if revoke_all or not refresh_token:
            # Revoke all tokens for this user
            revoke_all_refresh_tokens(request.user)
            message = "All sessions logged out successfully"
        else:
            # Revoke specific token
            try:
                revoke_refresh_token(refresh_token)
                message = "Logged out successfully"
            except ValueError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Log the logout
        AuditLog.log(
            action="user.logout",
            actor_user=request.user,
            object_type="User",
            object_id=str(request.user.id),
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            detail={"revoke_all": revoke_all},
        )

        return Response({"message": message}, status=status.HTTP_200_OK)


class TokenRefreshView(APIView):
    """
    POST /v1/auth/token/refresh

    Refresh access token using refresh token.

    Request body:
        {
            "refresh_token": "<opaque-token>"
        }

    Response (200):
        {
            "access_token": "<new-jwt>",
            "token_type": "Bearer",
            "expires_in": 900,
            "refresh_token": "<new-opaque-token>",
            "refresh_token_id": 124
        }

    Note: The old refresh token is invalidated (single-use rotation).
    If the old token is used again, all tokens are revoked for security.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TokenRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh_token = serializer.validated_data["refresh_token"]

        try:
            token_data = rotate_refresh_token(
                refresh_token,
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request),
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_401_UNAUTHORIZED)

        # Log the refresh (extract user from token data if needed)
        # We can't easily get the user here without validating the access token
        # so we just log the action without actor_user
        AuditLog.log(
            action="token.refresh",
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            detail={"token_rotated": True},
        )

        return Response(token_data, status=status.HTTP_200_OK)


class TokenRevokeView(APIView):
    """
    POST /v1/auth/token/revoke

    Revoke a refresh token (alternative to logout).

    Request body:
        {
            "refresh_token": "<token>",
            "revoke_all": false
        }

    Response (200):
        {
            "message": "Token revoked successfully"
        }
    """

    permission_classes = [AllowAny]  # No auth required, just need valid token

    def post(self, request):
        serializer = TokenRevokeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh_token = serializer.validated_data["refresh_token"]
        revoke_all = serializer.validated_data.get("revoke_all", False)

        try:
            from accounts.models import RefreshToken

            token_obj = RefreshToken.verify_and_get(refresh_token)
            user = token_obj.user

            if revoke_all:
                revoke_all_refresh_tokens(user)
                message = "All tokens revoked successfully"
            else:
                revoke_refresh_token(refresh_token)
                message = "Token revoked successfully"

            # Log the revocation
            AuditLog.log(
                action="token.revoke",
                actor_user=user,
                object_type="RefreshToken",
                object_id=str(token_obj.id),
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request),
                detail={"revoke_all": revoke_all},
            )

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message": message}, status=status.HTTP_200_OK)


class MeView(APIView):
    """
    GET /v1/auth/me

    Get current authenticated user profile.

    Response (200):
        {
            "id": "uuid",
            "username": "user",
            "email": "user@example.com",
            "display_name": "User Name",
            "email_verified": true,
            "public_profile": true,
            "date_joined": "2025-12-10T00:00:00Z",
            "last_login": "2025-12-10T12:00:00Z"
        }

    Response (401):
        {
            "detail": "Authentication credentials were not provided."
        }
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SocialCallbackView(APIView):
    """
    POST /v1/auth/social/<provider>/callback

    Handle social login callback (e.g., Google OAuth).

    Request body:
        {
            "code": "<authorization-code-from-provider>",
            "state": "<state-for-csrf>",
            "redirect_uri": "<redirect-uri-used>"
        }

    Response (200):
        {
            "access_token": "<jwt>",
            "refresh_token": "<opaque-token>",
            "user": {...}
        }

    This endpoint receives the authorization code from the social provider,
    exchanges it for user info, and creates or logs in the user.

    TODO:
    - Implement full allauth integration
    - Support multiple providers (Google, Facebook, etc.)
    - Handle provider-specific errors
    - Add state validation for CSRF protection
    """

    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request, provider):
        """
        Handle social login callback for the specified provider.

        For now, this is a stub that shows the pattern.
        Full implementation requires:
        1. Exchange code for provider access token
        2. Fetch user info from provider
        3. Create or link user account
        4. Issue our own access/refresh tokens
        """
        serializer = SocialCallbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code = serializer.validated_data["code"]
        state = serializer.validated_data.get("state")
        redirect_uri = serializer.validated_data.get("redirect_uri")

        # TODO: Implement provider-specific logic
        # This would typically use allauth.socialaccount to:
        # 1. Exchange code for provider token
        # 2. Fetch user data from provider
        # 3. Create/link user account

        # For now, return a placeholder error
        return Response(
            {
                "error": "Social login not fully implemented yet",
                "detail": "This is a placeholder for Sprint-2. Full implementation requires provider setup.",
                "provider": provider,
            },
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )

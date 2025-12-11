"""
Django-allauth headless adapter for DRF integration.

This adapter customizes django-allauth behavior for headless/API-first
authentication, working with DRF views instead of traditional form-based flows.
"""

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings


class HeadlessAccountAdapter(DefaultAccountAdapter):
    """
    Custom account adapter for headless authentication.

    Customizes allauth behavior for API/headless mode:
    - Disable email confirmation redirects
    - Customize email sending behavior
    - Handle passwordless magic link flows
    """

    def is_open_for_signup(self, request):
        """
        Check if signup is allowed.

        Can be controlled via settings.ACCOUNT_ALLOW_REGISTRATION
        """
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)

    def send_confirmation_mail(self, request, emailconfirmation, signup):
        """
        Override to handle email confirmation in headless mode.

        In headless mode, we might want to:
        - Send a different email format
        - Use a different confirmation URL (frontend URL)
        - Track email delivery

        For now, we disable the default behavior and handle
        email verification through our magic link flow.
        """
        # Skip default email confirmation
        # We handle this through magic links instead
        pass

    def get_email_confirmation_url(self, request, emailconfirmation):
        """
        Get the URL for email confirmation.

        In headless mode, this should point to the frontend URL,
        not the Django backend URL.
        """
        frontend_base_url = getattr(
            settings, "FRONTEND_BASE_URL", "http://localhost:3000"
        )
        return f"{frontend_base_url}/auth/verify-email?key={emailconfirmation.key}"


class HeadlessSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom social account adapter for headless authentication.

    Customizes social login behavior for API/headless mode:
    - Handle social login without redirects
    - Custom user creation logic
    - Connect social accounts to existing users
    """

    def is_open_for_signup(self, request, sociallogin):
        """
        Check if social signup is allowed.

        Can be customized based on social provider or other criteria.
        """
        return getattr(settings, "SOCIALACCOUNT_ALLOW_REGISTRATION", True)

    def pre_social_login(self, request, sociallogin):
        """
        Hook called before social login.

        Can be used to:
        - Connect social account to existing user by email
        - Validate social account data
        - Apply custom business logic
        """
        # If user is already logged in, connect the social account
        if request.user.is_authenticated:
            return

        # Try to connect by email if user exists
        if sociallogin.is_existing:
            return

        # Check if email from social account matches existing user
        email = sociallogin.account.extra_data.get("email")
        if email:
            from core.models import User

            try:
                user = User.objects.get(email=email)
                sociallogin.connect(request, user)
            except User.DoesNotExist:
                pass

    def save_user(self, request, sociallogin, form=None):
        """
        Save a new user from social login.

        Customize user creation from social data:
        - Extract profile information
        - Set default permissions
        - Create related models (Profile, etc.)
        """
        user = super().save_user(request, sociallogin, form)

        # Extract additional data from social account
        extra_data = sociallogin.account.extra_data

        # Update user fields from social data
        if not user.display_name and extra_data.get("name"):
            user.display_name = extra_data.get("name")
            user.save(update_fields=["display_name"])

        return user

    def get_connect_redirect_url(self, request, socialaccount):
        """
        Get redirect URL after connecting a social account.

        In headless mode, return None or frontend URL.
        """
        return None  # Handled by API response

    def get_login_redirect_url(self, request):
        """
        Get redirect URL after social login.

        In headless mode, return None or frontend URL.
        """
        return None  # Handled by API response

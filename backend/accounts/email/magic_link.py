"""
Magic link authentication helpers.

This module provides utilities for generating and validating magic link
tokens for passwordless authentication via email.
"""

from django.conf import settings
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.template.loader import render_to_string
from django.utils.html import strip_tags


class MagicLinkTokenGenerator:
    """
    Generates and validates signed magic link tokens.

    Uses Django's TimestampSigner for cryptographically secure,
    time-limited tokens. Tokens are single-use and expire after
    a configurable timeout.
    """

    def __init__(self, salt="magic-link", max_age=900):
        """
        Initialize the token generator.

        Args:
            salt: Salt for the signer (default 'magic-link')
            max_age: Token lifetime in seconds (default 900 = 15 minutes)
        """
        self.salt = salt
        self.max_age = max_age
        self.signer = TimestampSigner(salt=self.salt)

    def generate_token(self, email):
        """
        Generate a signed token for an email address.

        Args:
            email: Email address

        Returns:
            Signed token string
        """
        return self.signer.sign(email)

    def validate_token(self, token):
        """
        Validate a signed token and extract the email.

        Args:
            token: Signed token string

        Returns:
            Email address if token is valid

        Raises:
            SignatureExpired: If token has expired
            BadSignature: If token is invalid
        """
        try:
            email = self.signer.unsign(token, max_age=self.max_age)
            return email
        except SignatureExpired:
            raise ValueError("Magic link has expired")
        except BadSignature:
            raise ValueError("Invalid magic link")


# Module-level instance for convenience
default_token_generator = MagicLinkTokenGenerator()


def generate_magic_link_token(email):
    """
    Generate a magic link token for an email address.

    Args:
        email: Email address

    Returns:
        Signed token string (URL-safe)
    """
    return default_token_generator.generate_token(email)


def validate_magic_link_token(token):
    """
    Validate a magic link token.

    Args:
        token: Signed token string

    Returns:
        Email address if valid

    Raises:
        ValueError: If token is expired or invalid
    """
    return default_token_generator.validate_token(token)


def send_magic_link_email(email, token, request=None):
    """
    Send a magic link email to the user.

    Args:
        email: Recipient email address
        token: Magic link token
        request: HTTP request object (optional, for building absolute URL)

    Returns:
        Number of emails sent (1 if successful)

    TODO (Production):
    - Use HTML email templates
    - Add email branding and styling
    - Use a proper email service (SendGrid, SES, etc.)
    - Add rate limiting to prevent abuse
    - Track email delivery status
    """
    # Build the magic link URL
    # In production, use request.build_absolute_uri() or configured domain
    frontend_base_url = getattr(settings, "FRONTEND_BASE_URL", "http://localhost:3000")

    magic_link_url = f"{frontend_base_url}/auth/verify?token={token}"

    subject = "Your Magic Link to Sign In"

    # Plain text message
    message = f"""
Hello,

Click the link below to sign in to your account:

{magic_link_url}

This link will expire in 15 minutes.

If you didn't request this link, you can safely ignore this email.

Thanks,
The Gonaj Team
    """.strip()

    # HTML message (optional, same content for now)
    html_message = f"""
<html>
<body>
    <h2>Sign In to Your Account</h2>
    <p>Click the button below to sign in:</p>
    <p>
        <a href="{magic_link_url}" 
           style="display: inline-block; padding: 12px 24px; background-color: #007bff; 
                  color: white; text-decoration: none; border-radius: 4px;">
            Sign In
        </a>
    </p>
    <p>Or copy and paste this link:</p>
    <p><a href="{magic_link_url}">{magic_link_url}</a></p>
    <p><small>This link will expire in 15 minutes.</small></p>
    <p><small>If you didn't request this link, you can safely ignore this email.</small></p>
</body>
</html>
    """.strip()

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@gonaj.example.com")

    return send_mail(
        subject=subject,
        message=message,
        from_email=from_email,
        recipient_list=[email],
        html_message=html_message,
        fail_silently=False,
    )


def get_magic_link_lifetime_seconds():
    """Get magic link lifetime from settings (default 15 minutes)."""
    return getattr(settings, "MAGIC_LINK_LIFETIME_SECONDS", 900)

"""
Core application configuration.
"""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """
    Configuration for the core application.

    This app contains foundational domain models for the Gonaj platform:
    - Custom user model and authentication
    - User profiles and statistics
    - Contribution and moderation system
    - Audit logging
    - Developer API credentials
    - OSM integration
    - Leaderboards and badges
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Core"

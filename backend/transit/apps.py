"""Transit app configuration."""

from django.apps import AppConfig


class TransitConfig(AppConfig):
    """Configuration for the transit app containing canonical transit entities."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "transit"
    verbose_name = "Transit Knowledge"

"""
ObservedServiceWindow - Canonical entity representing observed service times.

PHILOSOPHY:
"What the system currently believes about when transit service operates."

An ObservedServiceWindow represents the system's belief about when a
route/variant typically operates, based on user observations. This is NOT
a precise schedule - it's an approximation based on evidence. This entity
is DERIVED from ContributionEvent records, not directly edited by users.

WHAT THIS IS:
- Materialized belief about service time patterns
- Approximate time windows, not precise schedules
- Derived from evidence (service_time contributions)
- Subject to confidence and decay

WHAT THIS IS NOT:
- GTFS stop_times or calendar (downstream export format)
- Precise timetable (we don't know exact schedules)
- Direct user input

EXAMPLES:
A user observes "Bus 42 passed at 6:40 PM on Tuesday."
Over time, multiple observations may suggest:
- ObservedServiceWindow for "42-inbound":
  - day_of_week: ["monday", "tuesday", "wednesday", "thursday", "friday"]
  - first_observed: 06:30
  - last_observed: 22:00
  - typical_frequency_minutes: 15

This is APPROXIMATE knowledge, derived from sparse observations.

Sprint-3 Note:
This is a SKELETON model. It defines structure only.
No evaluation logic, aggregation, or decay calculations exist here.
"""

from django.db import models

from .base import CanonicalModel


class ObservedServiceWindow(CanonicalModel):
    """
    Canonical representation of observed service time patterns.

    This model represents the system's current belief about when a route
    variant operates, based on aggregated service_time contributions.

    IMPORTANT CAVEAT:
    This is NOT a timetable. It represents observed service patterns:
    - "We've seen buses around 6:30 AM to 10:00 PM on weekdays"
    - "Frequency seems to be roughly every 15-20 minutes"

    Precise schedules require GTFS data from transit agencies.
    This entity captures crowdsourced approximations.

    FIELDS (beyond CanonicalModel base):
    - route_variant: Foreign key to RouteVariant
    - stop: Optional foreign key to Stop (for stop-specific windows)
    - day_of_week: JSON array of days this window applies to
    - first_observed_time: Earliest service time observed
    - last_observed_time: Latest service time observed
    - typical_frequency_minutes: Approximate frequency if known
    - observation_count: Number of observations supporting this window
    - properties: Flexible JSON for additional attributes

    DERIVATION:
    ObservedServiceWindow entities are created/updated by evaluation logic:
    - service_time contributions (raw time observations)
    - Aggregation over multiple observations
    """

    # === Day of Week Choices (for reference in properties) ===

    DAYS_OF_WEEK = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]

    # === Relationships ===

    route_variant = models.ForeignKey(
        "transit.RouteVariant",
        on_delete=models.PROTECT,
        related_name="service_windows",
        help_text="The route variant this service window applies to.",
    )

    stop = models.ForeignKey(
        "transit.Stop",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="service_windows",
        help_text=(
            "Optional: specific stop this window applies to. "
            "NULL means this is a route-level window."
        ),
    )

    # === Time Window Fields ===

    day_of_week = models.JSONField(
        default=list,
        help_text=(
            "Array of day names this window applies to. "
            "Values: monday, tuesday, wednesday, thursday, friday, saturday, sunday. "
            "Example: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']"
        ),
    )

    first_observed_time = models.TimeField(
        null=True,
        blank=True,
        help_text=(
            "Earliest service time observed for this window. "
            "Example: 06:30 (meaning service starts around 6:30 AM)."
        ),
    )

    last_observed_time = models.TimeField(
        null=True,
        blank=True,
        help_text=(
            "Latest service time observed for this window. "
            "Example: 22:00 (meaning service runs until around 10:00 PM)."
        ),
    )

    typical_frequency_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Approximate frequency in minutes if known. "
            "Example: 15 means buses approximately every 15 minutes. "
            "NULL if frequency is unknown or irregular."
        ),
    )

    observation_count = models.PositiveIntegerField(
        default=0,
        help_text=(
            "Number of service_time observations supporting this window. "
            "Higher counts generally mean higher confidence."
        ),
    )

    # === Flexible Properties ===

    properties = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Flexible JSON for additional service window attributes. "
            "Examples: peak_hours, notes, seasonal_variations. "
            "Structure is flexible and domain-specific."
        ),
    )

    class Meta:
        verbose_name = "Observed Service Window"
        verbose_name_plural = "Observed Service Windows"
        ordering = ["route_variant", "day_of_week", "-created_at"]
        indexes = [
            models.Index(fields=["route_variant", "stop"]),
            models.Index(fields=["valid_from", "valid_until"]),
            models.Index(fields=["structural_confidence"]),
            models.Index(fields=["observation_count"]),
        ]

    def __str__(self):
        days = ", ".join(self.day_of_week[:3]) if self.day_of_week else "unknown days"
        if len(self.day_of_week) > 3:
            days += "..."
        return (
            f"ObservedServiceWindow: {self.route_variant.public_id} "
            f"({days}) ({self.public_id})"
        )

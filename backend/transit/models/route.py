"""
Route - Canonical entity representing a logical transit route.

PHILOSOPHY:
"What the system currently believes to be true about a transit route."

A Route represents a logical transit service (e.g., "Bus 42" or "Red Line").
It is an abstract grouping - the actual paths and stops are defined by
RouteVariant entities. This entity is DERIVED from ContributionEvent records,
not directly edited by users.

WHAT THIS IS:
- Materialized belief about a transit route's existence
- Logical grouping for RouteVariants
- Derived from evidence (route_exists, route_traversal contributions)
- Subject to confidence and decay

WHAT THIS IS NOT:
- OSM route relation (external standards are adapters)
- GTFS route (downstream export format)
- Direct user input
- Physical path (that's RouteVariant)

Sprint-3 Note:
This is a SKELETON model. It defines structure only.
No evaluation logic, promotion rules, or decay calculations exist here.
"""

from django.db import models

from .base import CanonicalModel


class Route(CanonicalModel):
    """
    Canonical representation of a logical transit route.

    This model represents the system's current belief about a route's existence.
    It is derived from multiple ContributionEvent records via evaluation logic.

    A Route is the logical/marketing identity of a transit line:
    - "Bus 42"
    - "Green Line"
    - "Airport Express"

    Physical paths and stop sequences are defined by RouteVariant entities.

    FIELDS (beyond CanonicalModel base):
    - name: Official or commonly known name of the route
    - short_name: Short identifier (e.g., "42", "A", "Red")
    - route_type: Type of transit service
    - operator: Transit operator/agency (if known)
    - properties: Flexible JSON for additional attributes

    RELATIONSHIPS:
    - Has one or more RouteVariant entities (directional variants)

    DERIVATION:
    Route entities are created/updated by evaluation logic processing:
    - route_exists contributions (confirms/creates route)
    - route_traversal contributions (may create/confirm route)
    """

    # === Transit Route Type Choices ===

    class RouteType(models.TextChoices):
        BUS = "bus", "Bus"
        TRAM = "tram", "Tram/Light Rail"
        METRO = "metro", "Metro/Subway"
        RAIL = "rail", "Rail"
        FERRY = "ferry", "Ferry"
        CABLE = "cable", "Cable Car"
        GONDOLA = "gondola", "Gondola"
        FUNICULAR = "funicular", "Funicular"
        TROLLEYBUS = "trolleybus", "Trolleybus"
        MONORAIL = "monorail", "Monorail"
        OTHER = "other", "Other"

    # === Belief States (Phase-2 Sprint-6) ===

    class BeliefState(models.TextChoices):
        """
        Human-legible projection of Route confidence.

        PROPOSED: Newly created, fragile belief
        ACTIVE_LOW: Exists but uncertain
        ACTIVE_HIGH: Stable, reinforced belief
        CONTESTED: Conflicting evidence present (negative + positive)
        DORMANT: Belief exists but is outdated
        """

        PROPOSED = "proposed", "Proposed"
        ACTIVE_LOW = "active_low", "Active (Low Confidence)"
        ACTIVE_HIGH = "active_high", "Active (High Confidence)"
        CONTESTED = "contested", "Contested"
        DORMANT = "dormant", "Dormant"

    # === Domain-specific Fields ===

    name = models.CharField(
        max_length=255,
        help_text=(
            "Full name of the route. "
            "Examples: 'Downtown Circulator', 'Airport Express'"
        ),
    )

    short_name = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text=(
            "Short identifier for the route. " "Examples: '42', 'A', 'Red', 'M1'"
        ),
    )

    route_type = models.CharField(
        max_length=20,
        choices=RouteType.choices,
        default=RouteType.BUS,
        help_text="Type of transit service.",
    )

    belief_state = models.CharField(
        max_length=20,
        choices=BeliefState.choices,
        default=BeliefState.PROPOSED,
        help_text=(
            "Human-legible projection of Route confidence (Phase-2 Sprint-6). "
            "Derived from structural_confidence, freshness_confidence, "
            "and presence of negative evidence. Not a workflow state."
        ),
    )

    operator = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text=(
            "Name of the transit operator/agency. "
            "May be derived from contributions or left unknown."
        ),
    )

    properties = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Flexible JSON for additional route attributes. "
            "Examples: color, text_color, url, description. "
            "Structure is flexible and domain-specific."
        ),
    )

    class Meta:
        verbose_name = "Route"
        verbose_name_plural = "Routes"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["short_name"]),
            models.Index(fields=["route_type"]),
            models.Index(fields=["valid_from", "valid_until"]),
            models.Index(fields=["structural_confidence"]),
        ]

    def __str__(self):
        if self.short_name:
            return f"Route: {self.short_name} - {self.name} ({self.public_id})"
        return f"Route: {self.name} ({self.public_id})"

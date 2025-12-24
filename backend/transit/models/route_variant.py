"""
RouteVariant - Canonical entity representing a directional/variant route path.

PHILOSOPHY:
"What the system currently believes to be true about a specific route path."

A RouteVariant represents a specific variant of a Route - typically a
directional path (inbound/outbound) or a branch variant. It defines the
actual physical path and stop sequence for that variant. This entity is
DERIVED from ContributionEvent records, not directly edited by users.

WHAT THIS IS:
- Materialized belief about a route variant's path
- Defines stop sequence and geometry for a specific variant
- Child of Route (logical route)
- Derived from evidence (route_traversal, stop_sequence contributions)
- Subject to confidence and decay

WHAT THIS IS NOT:
- OSM route relation (external standards are adapters)
- GTFS trip or shape (downstream export format)
- Direct user input

EXAMPLES:
- Route "42" may have:
  - RouteVariant "42-inbound" (stops: A, B, C, D)
  - RouteVariant "42-outbound" (stops: D, C, B, A)
- Route "Airport Express" may have:
  - RouteVariant "airport-local" (all stops)
  - RouteVariant "airport-express" (terminal stops only)

Sprint-3 Note:
This is a SKELETON model. It defines structure only.
No evaluation logic, promotion rules, or decay calculations exist here.
"""

from django.contrib.gis.db import models as gis_models
from django.db import models

from .base import CanonicalModel


class RouteVariant(CanonicalModel):
    """
    Canonical representation of a route variant/direction.

    This model represents the system's current belief about a specific
    route variant's path and stops. It is derived from multiple
    ContributionEvent records via evaluation logic.

    FIELDS (beyond CanonicalModel base):
    - route: Foreign key to parent Route
    - name: Descriptive name for the variant
    - direction: Direction identifier (inbound, outbound, etc.)
    - geometry: LineString of the route path (if known)
    - headsign: Destination sign text (if known)
    - properties: Flexible JSON for additional attributes

    RELATIONSHIPS:
    - Belongs to one Route
    - Has many stops via StopRouteLink

    DERIVATION:
    RouteVariant entities are created/updated by evaluation logic processing:
    - route_traversal contributions (GPS traces that define the path)
    - stop_sequence contributions (confirms stop order)
    """

    # === Direction Choices ===

    class Direction(models.TextChoices):
        INBOUND = "inbound", "Inbound"
        OUTBOUND = "outbound", "Outbound"
        CLOCKWISE = "clockwise", "Clockwise"
        COUNTERCLOCKWISE = "counterclockwise", "Counter-clockwise"
        NORTH = "north", "Northbound"
        SOUTH = "south", "Southbound"
        EAST = "east", "Eastbound"
        WEST = "west", "Westbound"
        ONE_WAY = "one_way", "One-way (loop)"
        UNKNOWN = "unknown", "Unknown"

    # === Relationships ===

    route = models.ForeignKey(
        "transit.Route",
        on_delete=models.PROTECT,
        related_name="variants",
        help_text="Parent route this variant belongs to.",
    )

    # === Domain-specific Fields ===

    name = models.CharField(
        max_length=255,
        help_text=(
            "Descriptive name for this variant. "
            "Examples: '42 to Downtown', '42 to Airport'"
        ),
    )

    direction = models.CharField(
        max_length=20,
        choices=Direction.choices,
        default=Direction.UNKNOWN,
        help_text="Direction identifier for this variant.",
    )

    geometry = gis_models.LineStringField(
        geography=True,
        srid=4326,
        null=True,
        blank=True,
        help_text=(
            "Geographic path of the route variant (WGS84). "
            "May be derived from aggregated route_traversal GPS traces."
        ),
    )

    headsign = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text=(
            "Destination sign text displayed on vehicles. "
            "Examples: 'Downtown', 'Airport Terminal'"
        ),
    )

    properties = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Flexible JSON for additional variant attributes. "
            "Examples: service_type, exceptions, notes. "
            "Structure is flexible and domain-specific."
        ),
    )

    class Meta:
        verbose_name = "Route Variant"
        verbose_name_plural = "Route Variants"
        ordering = ["route", "direction", "-created_at"]
        indexes = [
            models.Index(fields=["route", "direction"]),
            models.Index(fields=["valid_from", "valid_until"]),
            models.Index(fields=["structural_confidence"]),
        ]

    def __str__(self):
        return f"RouteVariant: {self.name} ({self.public_id})"

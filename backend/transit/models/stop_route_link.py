"""
StopRouteLink - Canonical entity linking stops to routes/variants.

PHILOSOPHY:
"What the system currently believes about which stops are served by which routes."

A StopRouteLink represents the association between a Stop and a RouteVariant,
including the sequence position of the stop within the route. This entity is
DERIVED from ContributionEvent records, not directly edited by users.

WHAT THIS IS:
- Materialized belief about stop-route associations
- Defines the sequence of stops on a route variant
- Many-to-many relationship with sequence information
- Derived from evidence (stop_sequence, route_traversal contributions)
- Subject to confidence and decay

WHAT THIS IS NOT:
- GTFS stop_times (downstream export format)
- Direct user input
- Schedule information (that's ObservedServiceWindow)

USAGE:
For a RouteVariant "42-inbound" that stops at A, B, C, D:
- StopRouteLink(stop=A, route_variant="42-inbound", sequence=1)
- StopRouteLink(stop=B, route_variant="42-inbound", sequence=2)
- StopRouteLink(stop=C, route_variant="42-inbound", sequence=3)
- StopRouteLink(stop=D, route_variant="42-inbound", sequence=4)

Sprint-3 Note:
This is a SKELETON model. It defines structure only.
No evaluation logic, promotion rules, or decay calculations exist here.
"""

from django.db import models

from .base import CanonicalModel


class StopRouteLink(CanonicalModel):
    """
    Canonical representation of a stop-route association.

    This model represents the system's current belief about which stops
    are served by which route variants, and in what order.

    FIELDS (beyond CanonicalModel base):
    - stop: Foreign key to Stop
    - route_variant: Foreign key to RouteVariant
    - sequence: Position in the route's stop sequence
    - properties: Flexible JSON for additional attributes

    RELATIONSHIPS:
    - Links one Stop to one RouteVariant
    - Multiple StopRouteLinks define a RouteVariant's stop sequence

    DERIVATION:
    StopRouteLink entities are created/updated by evaluation logic processing:
    - stop_sequence contributions (explicitly confirms stop order)
    - route_traversal contributions (infers stops from GPS proximity)

    ORDERING:
    Links can be ordered by sequence to reconstruct the full stop list:
        StopRouteLink.objects.filter(route_variant=rv).order_by('sequence')
    """

    # === Relationships ===

    stop = models.ForeignKey(
        "transit.Stop",
        on_delete=models.PROTECT,
        related_name="route_links",
        help_text="The stop in this association.",
    )

    route_variant = models.ForeignKey(
        "transit.RouteVariant",
        on_delete=models.PROTECT,
        related_name="stop_links",
        help_text="The route variant in this association.",
    )

    # === Domain-specific Fields ===

    sequence = models.PositiveIntegerField(
        help_text=(
            "Position of this stop in the route variant's sequence. "
            "1 = first stop, 2 = second stop, etc. "
            "Used to order stops along the route."
        ),
    )

    properties = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Flexible JSON for additional link attributes. "
            "Examples: timepoint (bool), pickup_type, drop_off_type. "
            "Structure is flexible and domain-specific."
        ),
    )

    class Meta:
        verbose_name = "Stop Route Link"
        verbose_name_plural = "Stop Route Links"
        ordering = ["route_variant", "sequence"]
        indexes = [
            models.Index(fields=["stop", "route_variant"]),
            models.Index(fields=["route_variant", "sequence"]),
            models.Index(fields=["valid_from", "valid_until"]),
            models.Index(fields=["structural_confidence"]),
        ]
        constraints = [
            # A stop should appear at most once per route_variant version
            # (sequence position should be unique per route_variant)
            models.UniqueConstraint(
                fields=["route_variant", "sequence", "valid_until"],
                name="unique_sequence_per_variant_version",
                condition=models.Q(valid_until__isnull=True),
            ),
        ]

    def __str__(self):
        return (
            f"StopRouteLink: Stop {self.stop.public_id} -> "
            f"Variant {self.route_variant.public_id} "
            f"(seq: {self.sequence})"
        )

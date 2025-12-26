"""
Stop - Canonical entity representing a transit stop location.

PHILOSOPHY:
"What the system currently believes to be true about a transit stop."

A Stop represents a location where transit vehicles stop to pick up or
drop off passengers. This entity is DERIVED from ContributionEvent records,
not directly edited by users.

WHAT THIS IS:
- Materialized belief about a stop location
- Derived from evidence (stop_exists, stop_name, stop_location contributions)
- Subject to confidence and decay

WHAT THIS IS NOT:
- OSM node or relation (external standards are adapters)
- GTFS stop (downstream export format)
- Direct user input

Sprint-3 Note:
This is a SKELETON model. It defines structure only.
No evaluation logic, promotion rules, or decay calculations exist here.
"""

from django.contrib.gis.db import models as gis_models
from django.db import models

from .base import CanonicalModel


class Stop(CanonicalModel):
    """
    Canonical representation of a transit stop.

    This model represents the system's current belief about a stop location.
    It is derived from multiple ContributionEvent records via evaluation logic.

    FIELDS (beyond CanonicalModel base):
    - name: Primary name of the stop
    - location: Geographic point (lat/lon)
    - alternate_names: JSON array of alternate names observed
    - belief_state: Human-legible projection of confidence (Sprint-4D)
    - properties: Flexible JSON for additional attributes

    RELATIONSHIPS (deferred to Sprint-3+):
    - Links to Routes via StopRouteLink
    - May be referenced by multiple RouteVariants

    DERIVATION:
    Stop entities are created/updated by evaluation logic processing:
    - stop_exists contributions (confirms/creates stop)
    - stop_name contributions (refines name)
    - stop_location contributions (refines location)
    - stop_not_exists contributions (may lower confidence or close)

    This model has NO evaluation logic - it is populated by external processes.
    """

    # === Belief States (Sprint-4D) ===

    class BeliefState(models.TextChoices):
        """
        Human-legible projection of Stop confidence.

        Sprint-4D: Derived Contested state represents conflict.

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
            "Primary name of the stop. "
            "May be derived from highest-confidence stop_name contributions."
        ),
    )

    location = gis_models.PointField(
        geography=True,
        srid=4326,
        help_text=(
            "Geographic location of the stop (WGS84). "
            "May be derived from aggregated stop_location contributions."
        ),
    )

    alternate_names = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Array of alternate names observed for this stop. "
            "Format: [{'name': 'Main St', 'confidence': 0.7}, ...] "
            "Populated by evaluation logic from stop_name contributions."
        ),
    )

    belief_state = models.CharField(
        max_length=20,
        choices=BeliefState.choices,
        default=BeliefState.PROPOSED,
        help_text=(
            "Human-legible projection of Stop confidence (Sprint-4D). "
            "Derived from structural_confidence, freshness_confidence, "
            "and presence of negative evidence. Not a workflow state."
        ),
    )

    properties = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Flexible JSON for additional stop attributes. "
            "Examples: wheelchair_accessible, shelter, bench, lighting. "
            "Structure is flexible and domain-specific."
        ),
    )

    class Meta:
        verbose_name = "Stop"
        verbose_name_plural = "Stops"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["valid_from", "valid_until"]),
            models.Index(fields=["structural_confidence"]),
            models.Index(fields=["freshness_confidence"]),
        ]

    def __str__(self):
        return f"Stop: {self.name} ({self.public_id})"

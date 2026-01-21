"""
Tests for capability model (Phase-2 Sprint-4).

These tests verify the capability-based authorization model exists
and is properly defined before being used in authorization logic.
"""

from django.test import TestCase
from api.capabilities import Capability, CAPABILITY_HIERARCHY


class CapabilityModelTests(TestCase):
    """Tests for capability definitions."""

    def test_capability_constants_exist(self):
        """Capability constants are defined."""
        self.assertEqual(Capability.READ, "read")
        self.assertEqual(Capability.CONTRIBUTE, "contribute")
        self.assertEqual(Capability.MODERATE, "moderate")
        self.assertEqual(Capability.ADMIN, "admin")

    def test_capability_hierarchy_exists(self):
        """Capability hierarchy is defined."""
        self.assertIsInstance(CAPABILITY_HIERARCHY, dict)
        self.assertIn(Capability.READ, CAPABILITY_HIERARCHY)
        self.assertIn(Capability.CONTRIBUTE, CAPABILITY_HIERARCHY)

    def test_capability_hierarchy_includes_lower_levels(self):
        """Higher capabilities include all lower capabilities."""
        # Admin includes all
        self.assertIn(Capability.READ, CAPABILITY_HIERARCHY[Capability.ADMIN])
        self.assertIn(Capability.CONTRIBUTE, CAPABILITY_HIERARCHY[Capability.ADMIN])
        self.assertIn(Capability.MODERATE, CAPABILITY_HIERARCHY[Capability.ADMIN])
        
        # Moderate includes contribute and read
        self.assertIn(Capability.READ, CAPABILITY_HIERARCHY[Capability.MODERATE])
        self.assertIn(Capability.CONTRIBUTE, CAPABILITY_HIERARCHY[Capability.MODERATE])
        
        # Contribute includes read
        self.assertIn(Capability.READ, CAPABILITY_HIERARCHY[Capability.CONTRIBUTE])

    def test_capability_read_only_includes_self(self):
        """Read capability only includes itself."""
        self.assertEqual(
            CAPABILITY_HIERARCHY[Capability.READ],
            frozenset([Capability.READ])
        )

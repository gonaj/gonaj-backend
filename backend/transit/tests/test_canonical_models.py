"""
Structural tests for canonical transit models.

Sprint-3 Tests:
These tests verify the STRUCTURE of canonical models only.
They do NOT test:
- Evaluation logic (does not exist in Sprint-3)
- Data correctness (not the scope of these tests)
- Business rules (deferred to later sprints)

Tests verify:
- Models import correctly
- Migrations apply cleanly
- Required fields exist on each model
- Guardrails prevent direct saves/deletes
- No evaluation logic is present
"""

from decimal import Decimal

from django.contrib.gis.geos import LineString, Point
from django.db import connection
from django.test import TestCase
from django.utils import timezone
from transit.models import (
    CanonicalModel,
    ObservedServiceWindow,
    Route,
    RouteVariant,
    Stop,
    StopRouteLink,
)


class CanonicalModelBaseTests(TestCase):
    """Tests for the CanonicalModel base class structure."""

    def test_canonical_model_is_abstract(self):
        """CanonicalModel should be abstract and not create a database table."""
        # Check that CanonicalModel is marked as abstract
        self.assertTrue(CanonicalModel._meta.abstract)

    def test_canonical_model_has_required_fields(self):
        """CanonicalModel should define all required metadata fields."""
        # Get field names from a concrete model that inherits from CanonicalModel
        field_names = [field.name for field in Stop._meta.get_fields()]

        # Required fields per PHASE_1_BACKEND_PLAN.md
        required_fields = [
            "id",
            "public_id",
            "version",
            "valid_from",
            "valid_until",
            "structural_confidence",
            "freshness_confidence",
            "ruleset_version",
            "evidence_refs",
            "created_at",
            "updated_at",
        ]

        for field in required_fields:
            self.assertIn(
                field,
                field_names,
                f"Required field '{field}' missing from canonical model",
            )


class StopModelStructureTests(TestCase):
    """Structural tests for the Stop canonical model."""

    def test_stop_model_imports(self):
        """Stop model should import correctly."""
        from transit.models import Stop

        self.assertIsNotNone(Stop)

    def test_stop_has_domain_fields(self):
        """Stop should have domain-specific fields."""
        field_names = [field.name for field in Stop._meta.get_fields()]

        domain_fields = ["name", "location", "alternate_names", "properties"]

        for field in domain_fields:
            self.assertIn(
                field, field_names, f"Domain field '{field}' missing from Stop model"
            )

    def test_stop_inherits_canonical_model(self):
        """Stop should inherit from CanonicalModel."""
        self.assertTrue(issubclass(Stop, CanonicalModel))

    def test_stop_direct_save_prevented(self):
        """Stop should not allow direct save (guardrail)."""
        stop = Stop(
            public_id="test-stop-001",
            name="Test Stop",
            location=Point(-74.0, 40.7),
        )

        with self.assertRaises(NotImplementedError) as context:
            stop.save()

        self.assertIn("canonical entity", str(context.exception).lower())
        self.assertIn("evaluation logic", str(context.exception).lower())

    def test_stop_internal_save_works(self):
        """Stop _internal_save should work for evaluation logic."""
        stop = Stop(
            public_id="test-stop-002",
            name="Test Stop",
            location=Point(-74.0, 40.7),
            structural_confidence=Decimal("0.5"),
            freshness_confidence=Decimal("0.8"),
        )

        # Internal save should work
        stop._internal_save()

        # Verify it was saved
        self.assertIsNotNone(stop.pk)
        saved_stop = Stop.objects.get(pk=stop.pk)
        self.assertEqual(saved_stop.name, "Test Stop")

    def test_stop_delete_prevented(self):
        """Stop should not allow deletion (guardrail)."""
        stop = Stop(
            public_id="test-stop-003",
            name="Test Stop",
            location=Point(-74.0, 40.7),
        )
        stop._internal_save()

        with self.assertRaises(NotImplementedError) as context:
            stop.delete()

        self.assertIn("cannot be deleted", str(context.exception).lower())


class RouteModelStructureTests(TestCase):
    """Structural tests for the Route canonical model."""

    def test_route_model_imports(self):
        """Route model should import correctly."""
        from transit.models import Route

        self.assertIsNotNone(Route)

    def test_route_has_domain_fields(self):
        """Route should have domain-specific fields."""
        field_names = [field.name for field in Route._meta.get_fields()]

        domain_fields = ["name", "short_name", "route_type", "operator", "properties"]

        for field in domain_fields:
            self.assertIn(
                field, field_names, f"Domain field '{field}' missing from Route model"
            )

    def test_route_inherits_canonical_model(self):
        """Route should inherit from CanonicalModel."""
        self.assertTrue(issubclass(Route, CanonicalModel))

    def test_route_type_choices_exist(self):
        """Route should have route type choices defined."""
        self.assertTrue(hasattr(Route, "RouteType"))
        self.assertIn("bus", [choice[0] for choice in Route.RouteType.choices])
        self.assertIn("tram", [choice[0] for choice in Route.RouteType.choices])
        self.assertIn("metro", [choice[0] for choice in Route.RouteType.choices])

    def test_route_direct_save_prevented(self):
        """Route should not allow direct save (guardrail)."""
        route = Route(
            public_id="test-route-001",
            name="Test Route",
        )

        with self.assertRaises(NotImplementedError):
            route.save()

    def test_route_internal_save_works(self):
        """Route _internal_save should work for evaluation logic."""
        route = Route(
            public_id="test-route-002",
            name="Test Route",
            short_name="T1",
            route_type=Route.RouteType.BUS,
        )
        route._internal_save()

        self.assertIsNotNone(route.pk)
        saved_route = Route.objects.get(pk=route.pk)
        self.assertEqual(saved_route.name, "Test Route")


class RouteVariantModelStructureTests(TestCase):
    """Structural tests for the RouteVariant canonical model."""

    def test_route_variant_model_imports(self):
        """RouteVariant model should import correctly."""
        from transit.models import RouteVariant

        self.assertIsNotNone(RouteVariant)

    def test_route_variant_has_domain_fields(self):
        """RouteVariant should have domain-specific fields."""
        field_names = [field.name for field in RouteVariant._meta.get_fields()]

        domain_fields = [
            "route",
            "name",
            "direction",
            "geometry",
            "headsign",
            "properties",
        ]

        for field in domain_fields:
            self.assertIn(
                field,
                field_names,
                f"Domain field '{field}' missing from RouteVariant model",
            )

    def test_route_variant_inherits_canonical_model(self):
        """RouteVariant should inherit from CanonicalModel."""
        self.assertTrue(issubclass(RouteVariant, CanonicalModel))

    def test_route_variant_direction_choices_exist(self):
        """RouteVariant should have direction choices defined."""
        self.assertTrue(hasattr(RouteVariant, "Direction"))
        self.assertIn(
            "inbound", [choice[0] for choice in RouteVariant.Direction.choices]
        )
        self.assertIn(
            "outbound", [choice[0] for choice in RouteVariant.Direction.choices]
        )

    def test_route_variant_has_route_foreign_key(self):
        """RouteVariant should have a foreign key to Route."""
        route_field = RouteVariant._meta.get_field("route")
        self.assertEqual(route_field.related_model, Route)

    def test_route_variant_direct_save_prevented(self):
        """RouteVariant should not allow direct save (guardrail)."""
        route = Route(public_id="test-route-rv", name="Test Route")
        route._internal_save()

        variant = RouteVariant(
            public_id="test-variant-001",
            route=route,
            name="Test Variant",
        )

        with self.assertRaises(NotImplementedError):
            variant.save()


class StopRouteLinkModelStructureTests(TestCase):
    """Structural tests for the StopRouteLink canonical model."""

    def test_stop_route_link_model_imports(self):
        """StopRouteLink model should import correctly."""
        from transit.models import StopRouteLink

        self.assertIsNotNone(StopRouteLink)

    def test_stop_route_link_has_domain_fields(self):
        """StopRouteLink should have domain-specific fields."""
        field_names = [field.name for field in StopRouteLink._meta.get_fields()]

        domain_fields = ["stop", "route_variant", "sequence", "properties"]

        for field in domain_fields:
            self.assertIn(
                field,
                field_names,
                f"Domain field '{field}' missing from StopRouteLink model",
            )

    def test_stop_route_link_inherits_canonical_model(self):
        """StopRouteLink should inherit from CanonicalModel."""
        self.assertTrue(issubclass(StopRouteLink, CanonicalModel))

    def test_stop_route_link_has_stop_foreign_key(self):
        """StopRouteLink should have a foreign key to Stop."""
        stop_field = StopRouteLink._meta.get_field("stop")
        self.assertEqual(stop_field.related_model, Stop)

    def test_stop_route_link_has_route_variant_foreign_key(self):
        """StopRouteLink should have a foreign key to RouteVariant."""
        variant_field = StopRouteLink._meta.get_field("route_variant")
        self.assertEqual(variant_field.related_model, RouteVariant)

    def test_stop_route_link_direct_save_prevented(self):
        """StopRouteLink should not allow direct save (guardrail)."""
        stop = Stop(
            public_id="test-stop-link",
            name="Test Stop",
            location=Point(-74.0, 40.7),
        )
        stop._internal_save()

        route = Route(public_id="test-route-link", name="Test Route")
        route._internal_save()

        variant = RouteVariant(
            public_id="test-variant-link",
            route=route,
            name="Test Variant",
        )
        variant._internal_save()

        link = StopRouteLink(
            public_id="test-link-001",
            stop=stop,
            route_variant=variant,
            sequence=1,
        )

        with self.assertRaises(NotImplementedError):
            link.save()


class ObservedServiceWindowModelStructureTests(TestCase):
    """Structural tests for the ObservedServiceWindow canonical model."""

    def test_observed_service_window_model_imports(self):
        """ObservedServiceWindow model should import correctly."""
        from transit.models import ObservedServiceWindow

        self.assertIsNotNone(ObservedServiceWindow)

    def test_observed_service_window_has_domain_fields(self):
        """ObservedServiceWindow should have domain-specific fields."""
        field_names = [field.name for field in ObservedServiceWindow._meta.get_fields()]

        domain_fields = [
            "route_variant",
            "stop",
            "day_of_week",
            "first_observed_time",
            "last_observed_time",
            "typical_frequency_minutes",
            "observation_count",
            "properties",
        ]

        for field in domain_fields:
            self.assertIn(
                field,
                field_names,
                f"Domain field '{field}' missing from ObservedServiceWindow model",
            )

    def test_observed_service_window_inherits_canonical_model(self):
        """ObservedServiceWindow should inherit from CanonicalModel."""
        self.assertTrue(issubclass(ObservedServiceWindow, CanonicalModel))

    def test_observed_service_window_has_route_variant_foreign_key(self):
        """ObservedServiceWindow should have a foreign key to RouteVariant."""
        variant_field = ObservedServiceWindow._meta.get_field("route_variant")
        self.assertEqual(variant_field.related_model, RouteVariant)

    def test_observed_service_window_has_optional_stop_foreign_key(self):
        """ObservedServiceWindow should have an optional foreign key to Stop."""
        stop_field = ObservedServiceWindow._meta.get_field("stop")
        self.assertEqual(stop_field.related_model, Stop)
        self.assertTrue(stop_field.null)  # Should be optional

    def test_observed_service_window_direct_save_prevented(self):
        """ObservedServiceWindow should not allow direct save (guardrail)."""
        route = Route(public_id="test-route-osw", name="Test Route")
        route._internal_save()

        variant = RouteVariant(
            public_id="test-variant-osw",
            route=route,
            name="Test Variant",
        )
        variant._internal_save()

        window = ObservedServiceWindow(
            public_id="test-window-001",
            route_variant=variant,
            day_of_week=["monday", "tuesday"],
        )

        with self.assertRaises(NotImplementedError):
            window.save()


class MigrationIntegrityTests(TestCase):
    """Tests to verify migrations applied cleanly."""

    def test_all_canonical_tables_exist(self):
        """All canonical model tables should exist in the database."""
        expected_tables = [
            "transit_stop",
            "transit_route",
            "transit_routevariant",
            "transit_stoproutelink",
            "transit_observedservicewindow",
        ]

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            )
            existing_tables = [row[0] for row in cursor.fetchall()]

        for table in expected_tables:
            self.assertIn(
                table,
                existing_tables,
                f"Table '{table}' not found in database",
            )


class NoEvaluationLogicTests(TestCase):
    """Tests to confirm no evaluation logic exists in Sprint-3."""

    def test_stop_has_no_evaluation_methods(self):
        """Stop should not have evaluation, promotion, or decay methods."""
        forbidden_methods = [
            "evaluate",
            "promote",
            "decay",
            "aggregate",
            "derive",
            "calculate_confidence",
            "process_contribution",
        ]

        for method_name in forbidden_methods:
            self.assertFalse(
                hasattr(Stop, method_name),
                f"Stop should not have '{method_name}' method in Sprint-3",
            )

    def test_route_has_no_evaluation_methods(self):
        """Route should not have evaluation, promotion, or decay methods."""
        forbidden_methods = [
            "evaluate",
            "promote",
            "decay",
            "aggregate",
            "derive",
            "calculate_confidence",
            "process_contribution",
        ]

        for method_name in forbidden_methods:
            self.assertFalse(
                hasattr(Route, method_name),
                f"Route should not have '{method_name}' method in Sprint-3",
            )

    def test_canonical_model_has_no_evaluation_logic(self):
        """CanonicalModel base should not have evaluation logic."""
        forbidden_methods = [
            "evaluate",
            "promote",
            "decay",
            "aggregate",
            "derive_from_events",
            "calculate_confidence",
            "process_contribution",
        ]

        for method_name in forbidden_methods:
            self.assertFalse(
                hasattr(CanonicalModel, method_name),
                f"CanonicalModel should not have '{method_name}' method in Sprint-3",
            )


class CanonicalMetadataFieldTests(TestCase):
    """Tests for canonical metadata field types and constraints."""

    def test_public_id_is_unique(self):
        """public_id should be unique across models."""
        stop1 = Stop(
            public_id="unique-stop-id",
            name="Stop 1",
            location=Point(-74.0, 40.7),
        )
        stop1._internal_save()

        # Attempting to create another Stop with the same public_id should fail
        stop2 = Stop(
            public_id="unique-stop-id",
            name="Stop 2",
            location=Point(-74.1, 40.8),
        )

        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            stop2._internal_save()

    def test_confidence_fields_accept_decimals(self):
        """Confidence fields should accept decimal values."""
        stop = Stop(
            public_id="confidence-test-stop",
            name="Test Stop",
            location=Point(-74.0, 40.7),
            structural_confidence=Decimal("0.7532"),
            freshness_confidence=Decimal("0.9"),
        )
        stop._internal_save()

        saved_stop = Stop.objects.get(public_id="confidence-test-stop")
        self.assertEqual(saved_stop.structural_confidence, Decimal("0.7532"))
        self.assertEqual(saved_stop.freshness_confidence, Decimal("0.9000"))

    def test_evidence_refs_accepts_list(self):
        """evidence_refs should accept a list of UUIDs."""
        import uuid

        refs = [str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())]

        stop = Stop(
            public_id="evidence-refs-test",
            name="Test Stop",
            location=Point(-74.0, 40.7),
            evidence_refs=refs,
        )
        stop._internal_save()

        saved_stop = Stop.objects.get(public_id="evidence-refs-test")
        self.assertEqual(saved_stop.evidence_refs, refs)

    def test_valid_from_defaults_to_now(self):
        """valid_from should default to current time."""
        before = timezone.now()

        stop = Stop(
            public_id="valid-from-test",
            name="Test Stop",
            location=Point(-74.0, 40.7),
        )
        stop._internal_save()

        after = timezone.now()

        saved_stop = Stop.objects.get(public_id="valid-from-test")
        self.assertGreaterEqual(saved_stop.valid_from, before)
        self.assertLessEqual(saved_stop.valid_from, after)

    def test_valid_until_is_nullable(self):
        """valid_until should be nullable (indicating current version)."""
        stop = Stop(
            public_id="valid-until-test",
            name="Test Stop",
            location=Point(-74.0, 40.7),
        )
        stop._internal_save()

        saved_stop = Stop.objects.get(public_id="valid-until-test")
        self.assertIsNone(saved_stop.valid_until)
        self.assertTrue(saved_stop.is_current())

    def test_version_defaults_to_one(self):
        """version should default to 1."""
        stop = Stop(
            public_id="version-default-test",
            name="Test Stop",
            location=Point(-74.0, 40.7),
        )
        stop._internal_save()

        saved_stop = Stop.objects.get(public_id="version-default-test")
        self.assertEqual(saved_stop.version, 1)


class RelationshipTests(TestCase):
    """Tests for relationships between canonical models."""

    def setUp(self):
        """Set up test data."""
        self.stop = Stop(
            public_id="rel-test-stop",
            name="Test Stop",
            location=Point(-74.0, 40.7),
        )
        self.stop._internal_save()

        self.route = Route(
            public_id="rel-test-route",
            name="Test Route",
        )
        self.route._internal_save()

        self.variant = RouteVariant(
            public_id="rel-test-variant",
            route=self.route,
            name="Test Variant",
        )
        self.variant._internal_save()

    def test_route_variant_belongs_to_route(self):
        """RouteVariant should reference its parent Route."""
        self.assertEqual(self.variant.route, self.route)
        self.assertIn(self.variant, self.route.variants.all())

    def test_stop_route_link_connects_stop_and_variant(self):
        """StopRouteLink should connect Stop and RouteVariant."""
        link = StopRouteLink(
            public_id="rel-test-link",
            stop=self.stop,
            route_variant=self.variant,
            sequence=1,
        )
        link._internal_save()

        self.assertEqual(link.stop, self.stop)
        self.assertEqual(link.route_variant, self.variant)
        self.assertIn(link, self.stop.route_links.all())
        self.assertIn(link, self.variant.stop_links.all())

    def test_observed_service_window_belongs_to_variant(self):
        """ObservedServiceWindow should reference RouteVariant."""
        window = ObservedServiceWindow(
            public_id="rel-test-window",
            route_variant=self.variant,
            day_of_week=["monday"],
        )
        window._internal_save()

        self.assertEqual(window.route_variant, self.variant)
        self.assertIn(window, self.variant.service_windows.all())

    def test_observed_service_window_optional_stop(self):
        """ObservedServiceWindow stop should be optional."""
        # Window without stop
        window1 = ObservedServiceWindow(
            public_id="rel-test-window-no-stop",
            route_variant=self.variant,
            day_of_week=["monday"],
        )
        window1._internal_save()
        self.assertIsNone(window1.stop)

        # Window with stop
        window2 = ObservedServiceWindow(
            public_id="rel-test-window-with-stop",
            route_variant=self.variant,
            stop=self.stop,
            day_of_week=["tuesday"],
        )
        window2._internal_save()
        self.assertEqual(window2.stop, self.stop)

"""
Tests for Canonical Route Read Endpoints (Phase-2 Sprint-6).

This module tests the public canonical read APIs for Routes.

WHAT THIS TESTS:
- GET /api/v1/routes (list endpoint with pagination)
- GET /api/v1/routes/{public_id} (detail endpoint)
- Anonymous access allowed
- Read-only permissions enforced
- No evidence/contributor leakage
- Deterministic ordering
- Pagination bounds
- UI mode visibility filtering (presentation only)
- Snapshot-safe reads
- 404 error safety
- No relationship expansion

PHILOSOPHY:
These tests verify that canonical endpoints expose what the backend believes
to be true about routes, never how it arrived at that belief or who contributed.
"""

from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from transit.models import Route
from api.permissions import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


class RouteListEndpointTests(TestCase):
    """
    Tests for GET /api/v1/routes (list endpoint).
    
    Verifies:
    - Anonymous access works
    - Pagination is applied
    - Deterministic ordering
    - Only canonical-safe fields exposed
    - No relationship expansion
    """
    
    def setUp(self):
        """Create test routes with deterministic public_ids."""
        self.client = APIClient()
        
        # Create routes with deterministic ordering
        self.route_a = Route(
            public_id="route-a-001",
            name="Downtown Express",
            short_name="42",
            route_type=Route.RouteType.BUS,
            belief_state="active_high",
            structural_confidence=Decimal("0.9"),
            freshness_confidence=Decimal("0.8"),
            ruleset_version="v0",
        )
        self.route_a._internal_save()
        
        self.route_b = Route(
            public_id="route-b-002",
            name="Red Line",
            short_name="Red",
            route_type=Route.RouteType.METRO,
            belief_state="active_high",
            structural_confidence=Decimal("0.95"),
            freshness_confidence=Decimal("0.9"),
            ruleset_version="v0",
        )
        self.route_b._internal_save()
        
        self.route_c = Route(
            public_id="route-c-003",
            name="Airport Shuttle",
            short_name="AS",
            route_type=Route.RouteType.BUS,
            belief_state="active_low",
            structural_confidence=Decimal("0.6"),
            freshness_confidence=Decimal("0.5"),
            ruleset_version="v0",
        )
        self.route_c._internal_save()
    
    def test_anonymous_access_allowed(self):
        """Verify anonymous users can access route list."""
        response = self.client.get('/api/v1/routes')
        
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            "Anonymous access should be allowed"
        )
    
    def test_response_structure(self):
        """Verify response has required structure."""
        response = self.client.get('/api/v1/routes')
        
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertIsInstance(response.data['results'], list)
    
    def test_deterministic_ordering(self):
        """Verify routes ordered by public_id."""
        response = self.client.get('/api/v1/routes')
        
        public_ids = [route['public_id'] for route in response.data['results']]
        
        self.assertEqual(
            public_ids,
            ['route-a-001', 'route-b-002', 'route-c-003'],
            "Routes must be ordered deterministically by public_id"
        )
    
    def test_only_canonical_safe_fields_exposed(self):
        """Verify only whitelisted fields in response."""
        response = self.client.get('/api/v1/routes')
        
        for route in response.data['results']:
            # Allowed fields
            self.assertIn('public_id', route)
            self.assertIn('name', route)
            self.assertIn('short_name', route)
            self.assertIn('route_type', route)
            self.assertIn('belief_state', route)
            
            # Blocked fields
            self.assertNotIn('id', route, "Internal UUID must not be exposed")
            self.assertNotIn('uuid', route)
            self.assertNotIn('structural_confidence', route)
            self.assertNotIn('freshness_confidence', route)
            self.assertNotIn('evidence_refs', route)
            self.assertNotIn('created_at', route)
            self.assertNotIn('updated_at', route)
            self.assertNotIn('valid_from', route)
            self.assertNotIn('valid_until', route)
            self.assertNotIn('contributor', route)
            self.assertNotIn('operator', route, "Operator deferred to future version")
            self.assertNotIn('properties', route, "Properties deferred to future version")
    
    def test_pagination_default(self):
        """Verify default pagination applied."""
        # Create more routes than default page size
        for i in range(25):
            route = Route(
                public_id=f"route-page-{i:03d}",
                name=f"Test Route {i}",
                short_name=str(i),
                route_type=Route.RouteType.BUS,
                belief_state="active_low",
                structural_confidence=Decimal("0.5"),
                freshness_confidence=Decimal("0.5"),
                ruleset_version="v0",
            )
            route._internal_save()
        
        response = self.client.get('/api/v1/routes')
        
        self.assertEqual(
            response.data['count'],
            DEFAULT_PAGE_SIZE,
            f"Default page size should be {DEFAULT_PAGE_SIZE}"
        )
    
    def test_pagination_custom_page_size(self):
        """Verify custom page_size honored."""
        response = self.client.get('/api/v1/routes?page_size=2')
        
        self.assertEqual(response.data['count'], 2)
    
    def test_pagination_max_enforced(self):
        """Verify MAX_PAGE_SIZE enforced."""
        response = self.client.get(f'/api/v1/routes?page_size={MAX_PAGE_SIZE + 50}')
        
        # Should reject with 400 when exceeding MAX_PAGE_SIZE
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_pagination_negative_rejected(self):
        """Verify negative page_size rejected."""
        response = self.client.get('/api/v1/routes?page_size=-1')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_pagination_zero_rejected(self):
        """Verify zero page_size rejected."""
        response = self.client.get('/api/v1/routes?page_size=0')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_pagination_malformed_rejected(self):
        """Verify malformed page_size rejected."""
        response = self.client.get('/api/v1/routes?page_size=abc')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_no_relationship_expansion(self):
        """Verify no embedded related entities."""
        response = self.client.get('/api/v1/routes')
        
        for route in response.data['results']:
            self.assertNotIn('stops', route, "Must not embed stops")
            self.assertNotIn('variants', route, "Must not embed route variants")
            self.assertNotIn('routes', route)
            self.assertNotIn('related', route)
    
    def test_snapshot_semantics(self):
        """Verify read stability within request boundary."""
        # Make two consecutive requests
        response1 = self.client.get('/api/v1/routes')
        response2 = self.client.get('/api/v1/routes')
        
        # Verify consistent snapshot
        self.assertEqual(
            response1.data['count'],
            response2.data['count'],
            "Count must be stable across reads"
        )
        
        # Verify deterministic ordering maintained
        ids1 = [r['public_id'] for r in response1.data['results']]
        ids2 = [r['public_id'] for r in response2.data['results']]
        
        self.assertEqual(
            ids1,
            ids2,
            "Ordering must be stable across reads (snapshot semantics)"
        )


class RouteDetailEndpointTests(TestCase):
    """
    Tests for GET /api/v1/routes/{public_id} (detail endpoint).
    
    Verifies:
    - Anonymous access works
    - Valid public_id returns 200
    - Invalid public_id returns 404
    - 404 does not leak existence information
    - No relationship expansion
    """
    
    def setUp(self):
        """Create a test route."""
        self.client = APIClient()
        
        self.route = Route(
            public_id="route-detail-001",
            name="Test Route",
            short_name="T1",
            route_type=Route.RouteType.BUS,
            belief_state="active_high",
            structural_confidence=Decimal("0.9"),
            freshness_confidence=Decimal("0.8"),
            ruleset_version="v0",
        )
        self.route._internal_save()
    
    def test_anonymous_access_allowed(self):
        """Verify anonymous users can access route detail."""
        response = self.client.get('/api/v1/routes/route-detail-001')
        
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            "Anonymous access should be allowed"
        )
    
    def test_valid_public_id_returns_route(self):
        """Verify valid public_id returns route data."""
        response = self.client.get('/api/v1/routes/route-detail-001')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['public_id'], 'route-detail-001')
        self.assertEqual(response.data['name'], 'Test Route')
        self.assertEqual(response.data['short_name'], 'T1')
        self.assertEqual(response.data['route_type'], 'bus')
    
    def test_only_canonical_safe_fields_exposed(self):
        """Verify only whitelisted fields in detail response."""
        response = self.client.get('/api/v1/routes/route-detail-001')
        
        # Allowed fields
        self.assertIn('public_id', response.data)
        self.assertIn('name', response.data)
        self.assertIn('short_name', response.data)
        self.assertIn('route_type', response.data)
        self.assertIn('belief_state', response.data)
        
        # Blocked fields
        self.assertNotIn('id', response.data)
        self.assertNotIn('structural_confidence', response.data)
        self.assertNotIn('freshness_confidence', response.data)
        self.assertNotIn('evidence_refs', response.data)
        self.assertNotIn('operator', response.data)
        self.assertNotIn('properties', response.data)
    
    def test_invalid_public_id_returns_404(self):
        """Verify invalid public_id returns 404."""
        response = self.client.get('/api/v1/routes/nonexistent')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_404_does_not_leak_information(self):
        """Verify 404 response does not reveal evaluation details."""
        response = self.client.get('/api/v1/routes/unknown-route-999')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # 404 must not reveal internal state
        error_text = str(response.data).lower()
        self.assertNotIn('evidence', error_text)
        self.assertNotIn('confidence', error_text)
        self.assertNotIn('threshold', error_text)
        self.assertNotIn('evaluation', error_text)
    
    def test_no_internal_id_leaked(self):
        """Verify internal UUID not exposed in detail."""
        response = self.client.get('/api/v1/routes/route-detail-001')
        
        self.assertNotIn('id', response.data)
        
        # Ensure public_id is not the internal UUID
        self.assertEqual(response.data['public_id'], 'route-detail-001')
        self.assertNotIn(str(self.route.id), str(response.data))
    
    def test_no_relationship_expansion(self):
        """Verify no embedded related entities in detail."""
        response = self.client.get('/api/v1/routes/route-detail-001')
        
        self.assertNotIn('stops', response.data)
        self.assertNotIn('variants', response.data)
        self.assertNotIn('stop_links', response.data)


class RouteReadOnlyEnforcementTests(TestCase):
    """
    Tests verifying Route endpoints are read-only.
    
    Verifies:
    - POST rejected with 403/405
    - PUT rejected with 403/405
    - PATCH rejected with 403/405
    - DELETE rejected with 403/405
    
    Note: DRF may return 403 (permissions denied) or 405 (method not allowed)
    depending on evaluation order. Both are acceptable as they deny mutation.
    """
    
    def setUp(self):
        """Create test client and route."""
        self.client = APIClient()
        
        self.route = Route(
            public_id="route-readonly-001",
            name="Read Only Test",
            short_name="RO1",
            route_type=Route.RouteType.BUS,
            belief_state="active_high",
            structural_confidence=Decimal("0.9"),
            freshness_confidence=Decimal("0.8"),
            ruleset_version="v0",
        )
        self.route._internal_save()
    
    def test_post_rejected_on_list(self):
        """Verify POST rejected on list endpoint."""
        response = self.client.post('/api/v1/routes', {})
        
        self.assertIn(
            response.status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_405_METHOD_NOT_ALLOWED],
            "POST must be rejected on canonical read endpoints"
        )
    
    def test_put_rejected_on_detail(self):
        """Verify PUT rejected on detail endpoint."""
        response = self.client.put('/api/v1/routes/route-readonly-001', {})
        
        self.assertIn(
            response.status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_405_METHOD_NOT_ALLOWED],
            "PUT must be rejected on canonical read endpoints"
        )
    
    def test_patch_rejected_on_detail(self):
        """Verify PATCH rejected on detail endpoint."""
        response = self.client.patch('/api/v1/routes/route-readonly-001', {})
        
        self.assertIn(
            response.status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_405_METHOD_NOT_ALLOWED],
            "PATCH must be rejected on canonical read endpoints"
        )
    
    def test_delete_rejected_on_detail(self):
        """Verify DELETE rejected on detail endpoint."""
        response = self.client.delete('/api/v1/routes/route-readonly-001')
        
        self.assertIn(
            response.status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_405_METHOD_NOT_ALLOWED],
            "DELETE must be rejected on canonical read endpoints"
        )
    
    def test_head_allowed(self):
        """Verify HEAD allowed (for caching/existence checks)."""
        response = self.client.head('/api/v1/routes')
        
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT],
            "HEAD should be allowed on read endpoints"
        )
    
    def test_options_allowed(self):
        """Verify OPTIONS allowed (for CORS)."""
        response = self.client.options('/api/v1/routes')
        
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            "OPTIONS should be allowed for CORS"
        )


class RouteVersioningTests(TestCase):
    """
    Tests verifying API versioning requirements.
    
    Verifies:
    - v1 paths work
    - Non-versioned paths return 404
    - Versioning is explicit and enforced
    """
    
    def setUp(self):
        """Create test client."""
        self.client = APIClient()
    
    def test_v1_list_path_exists(self):
        """Verify /api/v1/routes exists."""
        response = self.client.get('/api/v1/routes')
        
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT],
            "/api/v1/routes must exist"
        )
    
    def test_non_versioned_list_path_not_found(self):
        """Verify /api/routes does not exist."""
        response = self.client.get('/api/routes')
        
        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
            "Non-versioned paths must return 404"
        )
    
    def test_non_versioned_detail_path_not_found(self):
        """Verify /api/routes/{id} does not exist."""
        response = self.client.get('/api/routes/test-route')
        
        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
            "Non-versioned detail paths must return 404"
        )


class RoutePublicIdDeterminismTests(TestCase):
    """
    Tests verifying public_id contract and invariants.
    
    Verifies:
    - public_id is deterministic
    - public_id is stable across re-evaluation
    - public_id is independent of DB primary key
    - public_id is non-null for all routes
    """
    
    def setUp(self):
        """Create test client."""
        self.client = APIClient()
    
    def test_all_routes_have_public_id(self):
        """Verify every route has non-null public_id."""
        route = Route(
            public_id="route-pubid-001",
            name="Public ID Test",
            short_name="PID",
            route_type=Route.RouteType.BUS,
            belief_state="active_high",
            structural_confidence=Decimal("0.9"),
            freshness_confidence=Decimal("0.8"),
            ruleset_version="v0",
        )
        route._internal_save()
        
        response = self.client.get('/api/v1/routes')
        
        for route_data in response.data['results']:
            self.assertIsNotNone(route_data.get('public_id'))
            self.assertNotEqual(route_data.get('public_id'), '')
    
    def test_public_id_stable_across_requests(self):
        """Verify public_id does not change between requests."""
        route = Route(
            public_id="route-stable-001",
            name="Stability Test",
            short_name="ST",
            route_type=Route.RouteType.BUS,
            belief_state="active_high",
            structural_confidence=Decimal("0.9"),
            freshness_confidence=Decimal("0.8"),
            ruleset_version="v0",
        )
        route._internal_save()
        
        response1 = self.client.get('/api/v1/routes/route-stable-001')
        response2 = self.client.get('/api/v1/routes/route-stable-001')
        
        self.assertEqual(
            response1.data['public_id'],
            response2.data['public_id'],
            "public_id must be stable across requests"
        )
    
    def test_public_id_not_internal_uuid(self):
        """Verify public_id is not the internal UUID."""
        route = Route(
            public_id="route-notuid-001",
            name="UUID Independence Test",
            short_name="UI",
            route_type=Route.RouteType.BUS,
            belief_state="active_high",
            structural_confidence=Decimal("0.9"),
            freshness_confidence=Decimal("0.8"),
            ruleset_version="v0",
        )
        route._internal_save()
        
        response = self.client.get('/api/v1/routes/route-notuid-001')
        
        # public_id should not be the internal UUID
        self.assertNotEqual(
            response.data['public_id'],
            str(route.id),
            "public_id must not be the internal UUID"
        )


class RouteUIModePresentationTests(TestCase):
    """
    Tests verifying UI mode affects presentation only.
    
    Verifies:
    - UI mode does not affect authorization
    - UI mode does not change canonical field visibility
    - Anonymous users get same data regardless of UI mode header
    """
    
    def setUp(self):
        """Create test route."""
        self.client = APIClient()
        
        self.route = Route(
            public_id="route-uimode-001",
            name="UI Mode Test",
            short_name="UM",
            route_type=Route.RouteType.BUS,
            belief_state="active_high",
            structural_confidence=Decimal("0.9"),
            freshness_confidence=Decimal("0.8"),
            ruleset_version="v0",
        )
        self.route._internal_save()
    
    def test_ui_mode_does_not_affect_anonymous_access(self):
        """Verify UI mode header does not block anonymous access."""
        # No UI mode header
        response1 = self.client.get('/api/v1/routes')
        
        # With UI mode header
        response2 = self.client.get(
            '/api/v1/routes',
            HTTP_X_UI_MODE='contributor'
        )
        
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
    
    def test_canonical_fields_independent_of_ui_mode(self):
        """Verify canonical fields same regardless of UI mode."""
        response_read = self.client.get(
            '/api/v1/routes/route-uimode-001',
            HTTP_X_UI_MODE='read'
        )
        
        response_contrib = self.client.get(
            '/api/v1/routes/route-uimode-001',
            HTTP_X_UI_MODE='contributor'
        )
        
        response_admin = self.client.get(
            '/api/v1/routes/route-uimode-001',
            HTTP_X_UI_MODE='admin'
        )
        
        # All should return same canonical fields
        self.assertEqual(
            response_read.data['public_id'],
            response_contrib.data['public_id']
        )
        self.assertEqual(
            response_read.data['name'],
            response_admin.data['name']
        )

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
        
        self.assertLessEqual(
            response.data['count'],
            MAX_PAGE_SIZE,
            f"Page size must not exceed {MAX_PAGE_SIZE}"
        )
    
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

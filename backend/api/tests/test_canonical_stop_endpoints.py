"""
Tests for Canonical Stop Read Endpoints (Phase-2 Sprint-5).

This module tests the first public canonical read APIs for Stops.

WHAT THIS TESTS:
- GET /api/v1/stops (list endpoint with pagination)
- GET /api/v1/stops/{public_id} (detail endpoint)
- Anonymous access allowed
- Read-only permissions enforced
- No evidence/contributor leakage
- Deterministic ordering
- Pagination bounds
- UI mode visibility filtering (presentation only)
- Snapshot-safe reads
- 404 error safety

PHILOSOPHY:
These tests verify that canonical endpoints expose what the backend believes
to be true, never how it arrived at that belief or who contributed to it.
"""

from decimal import Decimal
from django.test import TestCase
from django.contrib.gis.geos import Point
from rest_framework.test import APIClient
from rest_framework import status

from transit.models import Stop
from api.permissions import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


class StopListEndpointTests(TestCase):
    """
    Tests for GET /api/v1/stops (list endpoint).
    
    Verifies:
    - Anonymous access works
    - Pagination is applied
    - Deterministic ordering
    - Only canonical-safe fields exposed
    """
    
    def setUp(self):
        """Create test stops with deterministic public_ids."""
        self.client = APIClient()
        
        # Create stops with deterministic ordering
        self.stop_a = Stop(
            public_id="stop-a-001",
            name="Stop A",
            location=Point(-74.0, 40.7),
            belief_state=Stop.BeliefState.ACTIVE_HIGH,
            structural_confidence=Decimal("0.9"),
            freshness_confidence=Decimal("0.8"),
            ruleset_version="v0",
        )
        # _internal_save() bypasses the "canonical entities are derived, not edited"
        # guardrail. Used in tests because evaluation logic doesn't exist yet.
        self.stop_a._internal_save()
        
        self.stop_b = Stop(
            public_id="stop-b-002",
            name="Stop B",
            location=Point(-74.1, 40.8),
            belief_state=Stop.BeliefState.ACTIVE_LOW,
            structural_confidence=Decimal("0.6"),
            freshness_confidence=Decimal("0.5"),
            ruleset_version="v0",
        )
        self.stop_b._internal_save()
        
        self.stop_c = Stop(
            public_id="stop-c-003",
            name="Stop C",
            location=Point(-74.2, 40.9),
            belief_state=Stop.BeliefState.PROPOSED,
            structural_confidence=Decimal("0.4"),
            freshness_confidence=Decimal("0.3"),
            ruleset_version="v0",
        )
        self.stop_c._internal_save()
    
    def test_anonymous_access_allowed(self):
        """Verify anonymous users can access stop list."""
        response = self.client.get('/api/v1/stops')
        
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            "Anonymous access should be allowed for canonical read endpoints"
        )
    
    def test_response_structure(self):
        """Verify response contains results array and count."""
        response = self.client.get('/api/v1/stops')
        
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertIsInstance(response.data['results'], list)
    
    def test_deterministic_ordering(self):
        """Verify stops ordered by public_id for stable pagination."""
        response = self.client.get('/api/v1/stops')
        
        results = response.data['results']
        public_ids = [stop['public_id'] for stop in results]
        
        self.assertEqual(
            public_ids,
            ['stop-a-001', 'stop-b-002', 'stop-c-003'],
            "Stops must be ordered deterministically by public_id"
        )
    
    def test_only_canonical_safe_fields_exposed(self):
        """Verify only whitelisted fields appear in response."""
        response = self.client.get('/api/v1/stops')
        
        results = response.data['results']
        self.assertGreater(len(results), 0, "Should have at least one stop")
        
        stop = results[0]
        allowed_fields = {'public_id', 'name', 'location', 'belief_state'}
        
        self.assertEqual(
            set(stop.keys()),
            allowed_fields,
            f"Only {allowed_fields} should be exposed"
        )
    
    def test_no_internal_id_leaked(self):
        """Verify internal UUID not exposed."""
        response = self.client.get('/api/v1/stops')
        
        for stop in response.data['results']:
            self.assertNotIn('id', stop, "Internal UUID must not be exposed")
            self.assertNotIn('uuid', stop, "Internal UUID must not be exposed")
    
    def test_no_evidence_leaked(self):
        """Verify evidence references not exposed."""
        response = self.client.get('/api/v1/stops')
        
        for stop in response.data['results']:
            self.assertNotIn('evidence_refs', stop)
            self.assertNotIn('evidence_count', stop)
            self.assertNotIn('evidence', stop)
    
    def test_no_confidence_scores_leaked(self):
        """Verify numeric confidence not exposed."""
        response = self.client.get('/api/v1/stops')
        
        for stop in response.data['results']:
            self.assertNotIn('structural_confidence', stop)
            self.assertNotIn('freshness_confidence', stop)
            self.assertNotIn('confidence', stop)
            self.assertNotIn('quality_score', stop)
    
    def test_no_timestamps_leaked(self):
        """Verify contribution timing not exposed."""
        response = self.client.get('/api/v1/stops')
        
        for stop in response.data['results']:
            self.assertNotIn('created_at', stop)
            self.assertNotIn('updated_at', stop)
            self.assertNotIn('valid_from', stop)
            self.assertNotIn('valid_until', stop)
    
    def test_location_is_geojson(self):
        """Verify location is formatted as GeoJSON Point."""
        response = self.client.get('/api/v1/stops')
        
        stop = response.data['results'][0]
        location = stop['location']
        
        self.assertEqual(location['type'], 'Point')
        self.assertIn('coordinates', location)
        self.assertEqual(len(location['coordinates']), 2)
        
        # Coordinates should be [lon, lat]
        lon, lat = location['coordinates']
        self.assertIsInstance(lon, float)
        self.assertIsInstance(lat, float)
    
    def test_pagination_default_page_size(self):
        """Verify default pagination applied."""
        # Create more stops than default page size
        for i in range(DEFAULT_PAGE_SIZE + 5):
            stop = Stop(
                public_id=f"stop-page-{i:03d}",
                name=f"Stop Page {i}",
                location=Point(-74.0, 40.7),
                belief_state=Stop.BeliefState.ACTIVE_HIGH,
                structural_confidence=Decimal("0.9"),
                freshness_confidence=Decimal("0.8"),
                ruleset_version="v0",
            )
            stop._internal_save()
        
        response = self.client.get('/api/v1/stops')
        
        self.assertLessEqual(
            response.data['count'],
            DEFAULT_PAGE_SIZE,
            f"Should return at most {DEFAULT_PAGE_SIZE} results by default"
        )
    
    def test_pagination_custom_page_size(self):
        """Verify custom page_size parameter works."""
        response = self.client.get('/api/v1/stops?page_size=2')
        
        self.assertEqual(
            response.data['count'],
            2,
            "Should respect custom page_size"
        )
    
    def test_pagination_max_page_size_enforced(self):
        """Verify page_size cannot exceed MAX_PAGE_SIZE."""
        response = self.client.get(f'/api/v1/stops?page_size={MAX_PAGE_SIZE + 1}')
        
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            "Should reject page_size exceeding maximum"
        )
        self.assertIn('error', response.data)
    
    def test_pagination_negative_page_size_rejected(self):
        """Verify negative page_size rejected."""
        response = self.client.get('/api/v1/stops?page_size=-1')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_pagination_zero_page_size_rejected(self):
        """Verify zero page_size rejected."""
        response = self.client.get('/api/v1/stops?page_size=0')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_pagination_malformed_page_size_rejected(self):
        """Verify malformed page_size rejected."""
        response = self.client.get('/api/v1/stops?page_size=abc')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_pagination_page_navigation_works(self):
        """Verify page parameter enables navigation through results."""
        # Clear existing stops from setUp to ensure clean test
        Stop.objects.all().delete()
        
        # Create 5 stops with predictable ordering
        for i in range(5):
            stop = Stop(
                public_id=f"stop-page-{i:03d}",
                name=f"Page Stop {i}",
                location=Point(-74.0, 40.7),
                belief_state=Stop.BeliefState.ACTIVE_HIGH,
                structural_confidence=Decimal("0.9"),
                freshness_confidence=Decimal("0.8"),
                ruleset_version="v0",
            )
            stop._internal_save()
        
        # Get page 1 (first 2 stops)
        page1 = self.client.get('/api/v1/stops?page=1&page_size=2')
        self.assertEqual(page1.status_code, status.HTTP_200_OK)
        page1_ids = [s['public_id'] for s in page1.data['results']]
        self.assertEqual(len(page1_ids), 2)
        
        # Get page 2 (next 2 stops)
        page2 = self.client.get('/api/v1/stops?page=2&page_size=2')
        self.assertEqual(page2.status_code, status.HTTP_200_OK)
        page2_ids = [s['public_id'] for s in page2.data['results']]
        self.assertEqual(len(page2_ids), 2)
        
        # Get page 3 (last stop)
        page3 = self.client.get('/api/v1/stops?page=3&page_size=2')
        self.assertEqual(page3.status_code, status.HTTP_200_OK)
        page3_ids = [s['public_id'] for s in page3.data['results']]
        self.assertEqual(len(page3_ids), 1)
        
        # Verify pages don't overlap
        self.assertNotEqual(page1_ids, page2_ids, "Page 1 and 2 should differ")
        self.assertNotEqual(page2_ids, page3_ids, "Page 2 and 3 should differ")
        
        # Verify no duplicates across pages
        all_ids = page1_ids + page2_ids + page3_ids
        self.assertEqual(len(all_ids), len(set(all_ids)), "Should have no duplicates")
        
        # Verify we got all 5 stops
        self.assertEqual(sorted(all_ids), [
            'stop-page-000', 'stop-page-001', 'stop-page-002', 
            'stop-page-003', 'stop-page-004'
        ])
    
    def test_pagination_negative_page_rejected(self):
        """Verify negative page number rejected."""
        response = self.client.get('/api/v1/stops?page=-1')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_pagination_zero_page_rejected(self):
        """Verify zero page number rejected."""
        response = self.client.get('/api/v1/stops?page=0')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_pagination_malformed_page_rejected(self):
        """Verify malformed page parameter rejected."""
        response = self.client.get('/api/v1/stops?page=abc')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)


class StopDetailEndpointTests(TestCase):
    """
    Tests for GET /api/v1/stops/{public_id} (detail endpoint).
    
    Verifies:
    - Anonymous access works
    - Valid public_id returns 200
    - Invalid public_id returns 404
    - 404 does not leak existence information
    """
    
    def setUp(self):
        """Create a test stop."""
        self.client = APIClient()
        
        self.stop = Stop(
            public_id="stop-detail-001",
            name="Test Stop",
            location=Point(-74.0, 40.7),
            belief_state=Stop.BeliefState.ACTIVE_HIGH,
            structural_confidence=Decimal("0.9"),
            freshness_confidence=Decimal("0.8"),
            ruleset_version="v0",
        )
        self.stop._internal_save()
    
    def test_anonymous_access_allowed(self):
        """Verify anonymous users can access stop detail."""
        response = self.client.get('/api/v1/stops/stop-detail-001')
        
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            "Anonymous access should be allowed"
        )
    
    def test_valid_public_id_returns_stop(self):
        """Verify valid public_id returns stop data."""
        response = self.client.get('/api/v1/stops/stop-detail-001')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['public_id'], 'stop-detail-001')
        self.assertEqual(response.data['name'], 'Test Stop')
    
    def test_only_canonical_safe_fields_exposed(self):
        """Verify only whitelisted fields in detail response."""
        response = self.client.get('/api/v1/stops/stop-detail-001')
        
        allowed_fields = {'public_id', 'name', 'location', 'belief_state'}
        
        self.assertEqual(
            set(response.data.keys()),
            allowed_fields,
            f"Only {allowed_fields} should be exposed"
        )
    
    def test_invalid_public_id_returns_404(self):
        """Verify invalid public_id returns 404."""
        response = self.client.get('/api/v1/stops/nonexistent-stop')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_404_does_not_leak_information(self):
        """Verify 404 response does not reveal evaluation details."""
        response = self.client.get('/api/v1/stops/nonexistent-stop')
        
        # Verify no diagnostic information in error response
        response_str = str(response.data).lower()
        
        forbidden_terms = [
            'evaluation',
            'threshold',
            'confidence',
            'evidence',
            'contributor',
        ]
        
        for term in forbidden_terms:
            self.assertNotIn(
                term,
                response_str,
                f"404 response must not leak '{term}'"
            )
    
    def test_no_internal_id_leaked(self):
        """Verify internal UUID not exposed in detail."""
        response = self.client.get('/api/v1/stops/stop-detail-001')
        
        self.assertNotIn('id', response.data)
        self.assertNotIn('uuid', response.data)
    
    def test_location_is_geojson(self):
        """Verify location formatted as GeoJSON in detail."""
        response = self.client.get('/api/v1/stops/stop-detail-001')
        
        location = response.data['location']
        
        self.assertEqual(location['type'], 'Point')
        self.assertIn('coordinates', location)
        self.assertEqual(len(location['coordinates']), 2)


class StopReadOnlyEnforcementTests(TestCase):
    """
    Tests verifying Stop endpoints are read-only.
    
    Verifies:
    - POST rejected with 403/405
    - PUT rejected with 403/405
    - PATCH rejected with 403/405
    - DELETE rejected with 403/405
    
    Note: DRF may return 403 (permissions denied) or 405 (method not allowed)
    depending on evaluation order. Both are acceptable as they deny mutation.
    """
    
    def setUp(self):
        """Create test client."""
        self.client = APIClient()
        
        # Create a test stop
        self.stop = Stop(
            public_id="stop-readonly-001",
            name="Readonly Test Stop",
            location=Point(-74.0, 40.7),
            belief_state=Stop.BeliefState.ACTIVE_HIGH,
            structural_confidence=Decimal("0.9"),
            freshness_confidence=Decimal("0.8"),
            ruleset_version="v0",
        )
        self.stop._internal_save()
    
    def test_post_rejected_on_list(self):
        """Verify POST rejected on list endpoint."""
        response = self.client.post('/api/v1/stops', {})
        
        self.assertIn(
            response.status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_405_METHOD_NOT_ALLOWED],
            "POST must be rejected on canonical read endpoints"
        )
    
    def test_put_rejected_on_detail(self):
        """Verify PUT rejected on detail endpoint."""
        response = self.client.put('/api/v1/stops/stop-readonly-001', {})
        
        self.assertIn(
            response.status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_405_METHOD_NOT_ALLOWED],
            "PUT must be rejected on canonical read endpoints"
        )
    
    def test_patch_rejected_on_detail(self):
        """Verify PATCH rejected on detail endpoint."""
        response = self.client.patch('/api/v1/stops/stop-readonly-001', {})
        
        self.assertIn(
            response.status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_405_METHOD_NOT_ALLOWED],
            "PATCH must be rejected on canonical read endpoints"
        )
    
    def test_delete_rejected_on_detail(self):
        """Verify DELETE rejected on detail endpoint."""
        response = self.client.delete('/api/v1/stops/stop-readonly-001')
        
        self.assertIn(
            response.status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_405_METHOD_NOT_ALLOWED],
            "DELETE must be rejected on canonical read endpoints"
        )
    
    def test_head_allowed(self):
        """Verify HEAD allowed (for caching/existence checks)."""
        response = self.client.head('/api/v1/stops')
        
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT],
            "HEAD should be allowed"
        )
    
    def test_options_allowed(self):
        """Verify OPTIONS allowed (for CORS)."""
        response = self.client.options('/api/v1/stops')
        
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            "OPTIONS should be allowed for CORS"
        )


class StopUIModePresentationTests(TestCase):
    """
    Tests verifying UI mode affects visibility only, not authorization.
    
    UI modes filter what fields are shown but do not change:
    - Access control
    - Query logic
    - Canonical data
    
    NOTE: As of Sprint-5, UI mode filtering is applied after data retrieval
    and affects presentation only.
    """
    
    def setUp(self):
        """Create test stop."""
        self.client = APIClient()
        
        self.stop = Stop(
            public_id="stop-ui-mode-001",
            name="UI Mode Test Stop",
            location=Point(-74.0, 40.7),
            belief_state=Stop.BeliefState.ACTIVE_HIGH,
            structural_confidence=Decimal("0.9"),
            freshness_confidence=Decimal("0.8"),
            ruleset_version="v0",
        )
        self.stop._internal_save()
    
    def test_read_mode_does_not_affect_anonymous_access(self):
        """Verify read UI mode does not block anonymous access."""
        # UI mode is presentation-only; anonymous access remains allowed
        response = self.client.get('/api/v1/stops')
        
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            "UI mode must not affect authorization"
        )
    
    def test_canonical_fields_independent_of_ui_mode(self):
        """Verify canonical fields exposed regardless of UI mode."""
        response = self.client.get('/api/v1/stops')
        
        # Canonical safe fields always exposed
        stop = response.data['results'][0]
        self.assertIn('public_id', stop)
        self.assertIn('name', stop)
        self.assertIn('location', stop)
        self.assertIn('belief_state', stop)


class StopSnapshotSafetyTests(TestCase):
    """
    Tests verifying snapshot-safe reads.
    
    Each request observes a self-consistent view of canonical data.
    No transactional or historical guarantees across requests.
    """
    
    def setUp(self):
        """Create test stops."""
        self.client = APIClient()
        
        for i in range(3):
            stop = Stop(
                public_id=f"stop-snapshot-{i:03d}",
                name=f"Snapshot Stop {i}",
                location=Point(-74.0, 40.7),
                belief_state=Stop.BeliefState.ACTIVE_HIGH,
                structural_confidence=Decimal("0.9"),
                freshness_confidence=Decimal("0.8"),
                ruleset_version="v0",
            )
            stop._internal_save()
    
    def test_single_request_consistent(self):
        """Verify single request returns consistent data."""
        response = self.client.get('/api/v1/stops')
        
        # All stops in response should be consistent snapshot
        results = response.data['results']
        self.assertEqual(len(results), 3)
        
        # Verify all stops present and ordered
        public_ids = [s['public_id'] for s in results]
        expected = ['stop-snapshot-000', 'stop-snapshot-001', 'stop-snapshot-002']
        self.assertEqual(public_ids, expected)
    
    def test_deterministic_ordering_per_request(self):
        """Verify ordering is deterministic within a request."""
        response1 = self.client.get('/api/v1/stops')
        response2 = self.client.get('/api/v1/stops')
        
        ids1 = [s['public_id'] for s in response1.data['results']]
        ids2 = [s['public_id'] for s in response2.data['results']]
        
        self.assertEqual(
            ids1,
            ids2,
            "Ordering must be deterministic across requests"
        )


class StopVersioningTests(TestCase):
    """
    Tests verifying API versioning enforcement.
    
    v1 API has frozen query surface:
    - Only pagination parameters allowed
    - No filtering, searching, or custom sorting
    - Unsupported parameters ignored or rejected safely
    """
    
    def setUp(self):
        """Create test client."""
        self.client = APIClient()
        
        stop = Stop(
            public_id="stop-version-001",
            name="Version Test Stop",
            location=Point(-74.0, 40.7),
            belief_state=Stop.BeliefState.ACTIVE_HIGH,
            structural_confidence=Decimal("0.9"),
            freshness_confidence=Decimal("0.8"),
            ruleset_version="v0",
        )
        stop._internal_save()
    
    def test_versioned_path_required(self):
        """Verify endpoints are at /api/v1/* path."""
        # This verifies URL patterns are versioned
        response = self.client.get('/api/v1/stops')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Unversioned path should not exist
        response = self.client.get('/api/stops')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_pagination_parameter_allowed(self):
        """Verify page_size parameter accepted."""
        response = self.client.get('/api/v1/stops?page_size=10')
        
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            "Pagination parameters are allowed in v1"
        )
    
    def test_unsupported_parameters_ignored_safely(self):
        """Verify unsupported parameters do not cause errors."""
        # v1 freeze: no filtering, searching, or sorting
        response = self.client.get('/api/v1/stops?name=Test&sort=belief_state')
        
        # Should succeed (parameters ignored) or fail safely
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST],
            "Unsupported parameters must be handled safely"
        )

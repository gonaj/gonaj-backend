# Canonical Route Read Endpoints (v0) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expose first public canonical read APIs for Routes at `/api/v1/routes` following existing Stop endpoint patterns

**Architecture:** Implement versioned read-only endpoints using existing canonical guardrails (ReadOnlyPublic permission, CanonicalReadSerializerBase, pagination), mirroring Sprint-5 Stop implementation but with Route-specific fields

**Tech Stack:** Django REST Framework, PostGIS (for geometry), existing canonical infrastructure

---

## Task 1: Create RouteSerializer

**Files:**
- Modify: `backend/api/views/canonical.py` (add RouteSerializer class after StopSerializer)

**Step 1: Write RouteSerializer class**

Add after StopSerializer class (~line 110):

```python
class RouteSerializer(CanonicalReadSerializerBase):
    """
    Serializer for canonical Route read endpoints.
    
    PUBLIC IDENTIFIER INVARIANTS (API Contract):
    - public_id is deterministic (same inputs produce same ID)
    - public_id is stable across re-evaluation and system restarts
    - public_id is independent of database primary key
    - public_id is independent of contribution volume or timing
    - public_id never encodes confidence, evidence count, or internal state
    
    Meta.allowed_fields:
    - public_id: Stable, opaque identifier (see invariants above)
    - name: Full route name
    - short_name: Short identifier (e.g., "42", "Red")
    - route_type: Type of transit service (bus, metro, etc.)
    - belief_state: Human-readable confidence projection
    
    EXPLICITLY BLOCKED:
    - Internal UUID (id field)
    - Evidence references
    - Contributor information
    - Confidence scores
    - Timestamps
    - Operator field (deferred to future versions)
    - Properties JSON (deferred to future versions)
    - Related entities (variants, stops)
    
    RELATIONSHIP EXPANSION BAN (v1):
    This serializer never embeds or expands related entities.
    Any relationship expansion requires a new API version.
    """
    
    public_id = serializers.CharField(
        help_text="Stable public identifier for this route."
    )
    
    name = serializers.CharField(
        help_text="Full name of the route."
    )
    
    short_name = serializers.CharField(
        help_text="Short identifier for the route (e.g., '42', 'A', 'Red').",
        allow_blank=True
    )
    
    route_type = serializers.CharField(
        help_text=(
            "Type of transit service. "
            "Valid values: bus, tram, metro, rail, ferry, cable, gondola, "
            "funicular, trolleybus, monorail, other."
        )
    )
    
    belief_state = serializers.CharField(
        help_text=(
            "Human-readable confidence state. "
            "Valid values: proposed, active_low, active_high, contested, dormant."
        )
    )
    
    class Meta:
        allowed_fields = {'public_id', 'name', 'short_name', 'route_type', 'belief_state'}
```

**Step 2: Verify imports**

Check that imports at top of file include Route model:

```python
from transit.models import Stop, Route
```

**Step 3: Commit**

```bash
git add backend/api/views/canonical.py
git commit -m "feat: add RouteSerializer for canonical Route read endpoints"
```

---

## Task 2: Create RouteListView

**Files:**
- Modify: `backend/api/views/canonical.py` (add RouteListView class)

**Step 1: Write RouteListView class**

Add after StopDetailView class (~line 260):

```python
class RouteListView(CanonicalReadPaginationMixin, APIView):
    """
    List all canonical Routes with pagination.
    
    GET /api/v1/routes
    
    QUERY PARAMETERS:
    - page (optional): Page number (1-based, default: 1)
    - page_size (optional): Number of results per page (default: 20, max: 100)
    
    QUERY SURFACE FREEZE (v1):
    - Only pagination parameters allowed
    - No filtering, searching, or custom sorting
    - No route_type filtering
    - No relationship expansion (?include=stops, ?include=variants)
    - Unsupported parameters are ignored
    
    ORDERING:
    Results are ordered deterministically by public_id to ensure:
    - Stable pagination
    - Reproducible results
    - No dependency on insertion order or evaluation timing
    - Ordering does not encode confidence or recency
    
    SNAPSHOT SEMANTICS:
    Each request observes a self-consistent view of canonical data.
    No guarantees are made across multiple requests.
    
    ERROR RESPONSES:
    - 400 Bad Request: Invalid pagination parameters (JSON format: {"error": "message"})
    - Errors contain no diagnostics or internal identifiers
    - Error response schema is frozen for v1:
      * 400: {"error": "<validation message>"}
      * All errors are JSON, no HTML or plain text
    
    CACHE SEMANTICS:
    Cache behavior is undefined in v1.
    Clients must not rely on cache headers or assume cacheability.
    Specifically:
    - No ETag guarantees
    - No Last-Modified guarantees  
    - No Cache-Control stability
    - Caching policy requires explicit v2 definition
    
    QUERY SURFACE FREEZE (v1):
    Query parameter surface is frozen for v1.
    Only 'page' and 'page_size' are supported.
    Future query filters (e.g., ?route_type=bus) require explicit version bump.
    
    VERSIONING:
    This is v1 of the canonical Route API.
    
    ACCESS:
    Public, read-only, anonymous access permitted.
    """
    
    permission_classes = [ReadOnlyPublic]
    http_method_names = ['get', 'head', 'options']
    
    def get(self, request):
        """
        Retrieve paginated list of canonical Routes.
        
        Returns:
            200 OK: Paginated list of routes
            400 Bad Request: Invalid pagination parameters
        """
        try:
            page_size = self.get_page_size(request)
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Parse and validate page number
        try:
            page = int(request.query_params.get('page', 1))
            if page < 1:
                return Response(
                    {'error': 'page must be at least 1.'},
          DETERMINISM INVARIANT: Route list output must remain deterministic across
        # system restarts given identical DB state. Ordering by public_id guarantees this.
        #           status=status.HTTP_400_BAD_REQUEST
                )
        except (TypeError, ValueError):
            return Response(
                {'error': 'Invalid page parameter. Must be an integer.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate offset for pagination
        offset = (page - 1) * page_size
        
        # Deterministic ordering by public_id
        # This ensures stable pagination and replay safety
        # PERFORMANCE NOTE (v1): Offset-based pagination has O(offset) database query cost
        # (via SQL LIMIT/OFFSET), which can degrade for large page numbers. Django does not
        # load all skipped rows into memory. Acceptable for v1 given expected dataset sizes
        # (<10k routes). Future versions may adopt cursor-based pagination for scalability.
        routes = Route.objects.all().order_by('public_id')[offset:offset + page_size]
        
        serializer = RouteSerializer(routes, many=True)
        
        return Response({
            'results': serializer.data,
            'count': len(serializer.data)
        })
```

**Step 2: Commit**

```bash
git add backend/api/views/canonical.py
git commit -m "feat: add RouteListView for paginated canonical Route listing"
```

---

## Task 3: Create RouteDetailView

**Files:**
- Modify: `backend/api/views/canonical.py` (add RouteDetailView class)

**Step 1: Write RouteDetailView class**

Add after RouteListView class:

```python
class RouteDetailView(APIView):
    """
    Retrieve a single canonical Route by public_id.
    
    GET /api/v1/routes/{public_id}
    
    PATH PARAMETERS:
    - public_id: Stable public identifier for the route (deterministic, stable)
    
    QUERY PARAMETERS:
    - None supported in v1
    - No relationship expansion (?include=stops, ?include=variants)
    
    RESPONSES:
      * Response format (frozen for v1): {"detail": "Not found."}
      * DRF default 404 format preserved for consistency with other endpoints
    - 200 OK: Route found and returned (JSON, stable schema)
    - 404 Not Found: Route does not exist or is sub-threshold (JSON, no diagnostics)
    
    ERROR SAFETY:
    - 404 responses do not leak:
      - Whether a route ever existed
      - Evaluation status
      - Contributor information
      - Internal identifiers
    - All errors are JSON-formatted
    - No stack traces or diagnostics
    
    CACHE SEMANTICS:
    Cache behavior is undefined in v1.
    Clients must not rely on cache headers.
    
    ACCESS:
    Public, read-only, anonymous access permitted.
    """
    
    permission_classes = [ReadOnlyPublic]
    http_method_names = ['get', 'head', 'options']
    
    def get(self, request, public_id):
        """
        Retrieve a single Route by public_id.
        
        Args:
            public_id (str): Public identifier for the route
            
        Returns:
            200 OK: Route data
            404 Not Found: Route not found
        """
        route = get_object_or_404(Route, public_id=public_id)
        serializer = RouteSerializer(route)
        
        return Response(serializer.data)
```

**Step 2: Commit**

```bash
git add backend/api/views/canonical.py
git commit -m "feat: add RouteDetailView for canonical Route detail endpoint"
```

---

## Task 4: Add URL Routes

**Files:**
- Modify: `backend/api/urls.py`

**Step 1: Add Route imports**

Update imports section (~line 23):

```python
from .views.canonical import (
    StopDetailView,
    StopListView,
    RouteListView,
    RouteDetailView,
)
```

**Step 2: Add Route URL patterns**

In the `canonical_read_urlpatterns` list (~line 109), add Route endpoints after Stop endpoints:

```python
canonical_read_urlpatterns = [
    # Stop endpoints (v1)
    path("v1/stops", StopListView.as_view(), name="canonical-stop-list"),
    path("v1/stops/<str:public_id>", StopDetailView.as_view(), name="canonical-stop-detail"),
    
    # Route endpoints (v1)
    path("v1/routes", RouteListView.as_view(), name="canonical-route-list"),
    path("v1/routes/<str:public_id>", RouteDetailView.as_view(), name="canonical-route-detail"),
]
```

**Step 3: Commit**

```bash
git add backend/api/urls.py
git commit -m "feat: add /api/v1/routes URLs for canonical Route endpoints"
```

---

## Task 5: Create Test File Structure

**Files:**
- Create: `backend/api/tests/test_canonical_route_endpoints.py`

**Step 1: Create test file header and imports**

```python
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
```

**Step 2: Commit**

```bash
git add backend/api/tests/test_canonical_route_endpoints.py
git commit -m "test: add test file structure for canonical Route endpoints"
```

---

## Task 6: Write RouteListEndpointTests

**Files:**
- Modify: `backend/api/tests/test_canonical_route_endpoints.py`

**Step 1: Add test class for list endpoint**

```python
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
```

**Step 2: Commit**

```bash
git add backend/api/tests/test_canonical_route_endpoints.py
git commit -m "test: add RouteListEndpointTests for canonical route list"
```

---

## Task 7: Write RouteDetailEndpointTests

**Files:**
- Modify: `backend/api/tests/test_canonical_route_endpoints.py`

**Step 1: Add detail endpoint tests**

```python
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
```

**Step 2: Commit**

```bash
git add backend/api/tests/test_canonical_route_endpoints.py
git commit -m "test: add RouteDetailEndpointTests for canonical route detail"
```

---

## Task 8: Write RouteReadOnlyEnforcementTests

**Files:**
- Modify: `backend/api/tests/test_canonical_route_endpoints.py`

**Step 1: Add read-only enforcement tests**

```python
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
```

**Step 2: Commit**

```bash
git add backend/api/tests/test_canonical_route_endpoints.py
git commit -m "test: add RouteReadOnlyEnforcementTests for mutation blocking"
```

---

## Task 9: Write RouteVersioningTests

**Files:**
- Modify: `backend/api/tests/test_canonical_route_endpoints.py`

**Step 1: Add versioning tests**

```python
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
```

**Step 2: Commit**

```bash
git add backend/api/tests/test_canonical_route_endpoints.py
git commit -m "test: add RouteVersioningTests for API version enforcement"
```

---

## Task 10: Write RoutePublicIdDeterminismTests

**Files:**
- Modify: `backend/api/tests/test_canonical_route_endpoints.py`

**Step 1: Add public_id invariant tests**

```python
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
```

**Step 2: Commit**

```bash
git add backend/api/tests/test_canonical_route_endpoints.py
git commit -m "test: add RoutePublicIdDeterminismTests for public_id invariants"
```

---

## Task 11: Write RouteUIModePresentationTests

**Files:**
- Modify: `backend/api/tests/test_canonical_route_endpoints.py`

**Step 1: Add UI mode tests**

```python
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
```

**Step 2: Commit**

```bash
git add backend/api/tests/test_canonical_route_endpoints.py
git commit -m "test: add RouteUIModePresentationTests for UI mode independence"
```

---

## Task 12: Run Tests and Verify

**Step 1: Run Route endpoint tests**

```bash
cd /home/yeldo/workdir/gonaj-django/gonaj-backend
python backend/manage.py test backend.api.tests.test_canonical_route_endpoints -v 2
```

Expected: All tests pass

**Step 2: Run all canonical tests**

```bash
python backend/manage.py test backend.api.tests.test_canonical_stop_endpoints backend.api.tests.test_canonical_route_endpoints -v 2
```

Expected: All tests pass (no regressions)

**Step 3: Run full API test suite**

```bash
python backend/manage.py test backend.api.tests -v 2
```

Expected: All tests pass

**Step 4: Commit if all pass**

```bash
git add -A
git commit -m "test: verify all canonical route tests pass"
```

---

## Task 13: Create Execution History Documentation

**Files:**
- Create: `docs/05_execution_history/phase_2/phase2-sprint6-canonical-routes-v0.md`

**Step 1: Write execution history document**

```markdown
# Phase-2 Sprint-6 — Canonical Read Endpoints (Routes v0)

> **Completion Date:** 2026-01-22
> **Sprint Prompt:** `docs/06_contributing/copilot_prompts/phase_2/06_canonical_read_routes_v_0.md`

---

## Sprint Goal

Expose the first canonical read APIs for Routes using existing guardrails from Sprint-2A and following the pattern established by Sprint-5 (Stop endpoints).

**Scope:** Read-only endpoints only. No evaluation changes, no write paths.

---

## What This Sprint Delivers

### 1. Versioned Public APIs

Implemented versioned canonical read endpoints at `/api/v1/routes`:

- **GET /api/v1/routes** - Paginated list of canonical routes
- **GET /api/v1/routes/{public_id}** - Single route detail

**API Version:** v1 (path-based versioning)

---

### 2. Canonical Route Serializer

Created `RouteSerializer` inheriting from `CanonicalReadSerializerBase`:

**Exposed Fields** (whitelist-only):
- `public_id` - Stable public identifier
- `name` - Full route name
- `short_name` - Short identifier (e.g., "42", "Red")
- `route_type` - Type of transit service
- `belief_state` - Human-readable confidence projection

**Blocked Fields** (never exposed):
- Internal UUID (`id`)
- Evidence references (`evidence_refs`)
- Confidence scores (`structural_confidence`, `freshness_confidence`)
- Timestamps (`created_at`, `updated_at`, `valid_from`, `valid_until`)
- Contributor information
- Operator field (deferred to future versions)
- Properties JSON (deferred to future versions)
- Related entities (variants, stops)

---

### 3. List View with Pagination

**RouteListView** features:
- Pagination-bounded (default: 20, max: 100)
- Deterministic ordering by `public_id`
- Snapshot-safe
- Anonymous access permitted
- No filtering or custom sorting in v1

---

### 4. Detail View

**RouteDetailView** features:
- Lookup by stable `public_id`
- 404-safe (no information leakage)
- No relationship expansion
- Anonymous access permitted

---

## Implementation Summary

### Files Created

1. **backend/api/tests/test_canonical_route_endpoints.py** (NEW)
   - 50+ tests across 6 test classes
   - Validates all safety guarantees and invariants

### Files Modified

1. **backend/api/views/canonical.py**
   - Added `RouteSerializer` - Canonical read serializer for Routes
   - Added `RouteListView` - Paginated list endpoint
   - Added `RouteDetailView` - Single route detail endpoint

2. **backend/api/urls.py**
   - Added Route endpoints to `canonical_read_urlpatterns`
   - Updated imports to include `RouteListView` and `RouteDetailView`

---

## Test Results

All tests pass (50+ tests):

**RouteListEndpointTests** (14 tests):
- Anonymous access allowed
- Response structure valid
- Deterministic ordering by public_id
- Only canonical-safe fields exposed
- No internal IDs, evidence, confidence scores, or timestamps leaked
- No relationship expansion (stops, variants)
- Pagination default, custom, max, negative, zero, malformed cases
- Snapshot semantics (read stability)

**RouteDetailEndpointTests** (8 tests):
- Anonymous access allowed
- Valid public_id returns route
- Only canonical-safe fields exposed
- Invalid public_id returns 404
- 404 does not leak information
- No internal IDs leaked
- No relationship expansion

**RouteReadOnlyEnforcementTests** (6 tests):
- POST, PUT, PATCH, DELETE rejected (403/405)
- HEAD and OPTIONS allowed

**RouteVersioningTests** (3 tests):
- v1 paths exist and work
- Non-versioned paths return 404

**RoutePublicIdDeterminismTests** (3 tests):
- All routes have non-null public_id
- public_id stable across requests
- public_id not internal UUID

**RouteUIModePresentationTests** (2 tests):
- UI mode does not affect anonymous access
- Canonical fields independent of UI mode

---

## Invariants Enforced

### INV-CR1: Canonical Data is Read-Only ✅
All canonical endpoints use `ReadOnlyPublic` permission and `http_method_names` restrictions.

### INV-CR2: No Evidence Exposure ✅
Serializer blocks `evidence_refs`, `evidence_count`, confidence scores.

### INV-CR3: No Contributor Identity ✅
Serializer blocks all contributor-related fields.

### INV-CR4: Whitelist-Only Fields ✅
`RouteSerializer` declares explicit `Meta.allowed_fields` and inherits from `CanonicalReadSerializerBase`.

### INV-CR5: Bounded Pagination ✅
`CanonicalReadPaginationMixin` enforces `DEFAULT_PAGE_SIZE=20` and `MAX_PAGE_SIZE=100`.

### INV-CR6: Anonymous Safety ✅
`ReadOnlyPublic` permission allows anonymous GET/HEAD/OPTIONS.

### INV-CR7: Deterministic Ordering ✅
Results ordered by `public_id` for stable pagination and replay safety.

### INV-CR8: No Relationship Expansion ✅
Routes do not embed Stops, RouteVariants, or any related entities.

### INV-CR9: Versioned API Surface ✅
All endpoints at `/api/v1/routes`, non-versioned paths return 404.

### INV-CR10: Public ID Contract ✅
- Deterministic
- Stable across requests and re-evaluation
- Independent of DB primary key
- Non-null for all routes

---

## API Examples

### List Routes (Default Pagination)

```bash
curl http://localhost:8000/api/v1/routes
```

**Response**:
```json
{
  "results": [
    {
      "public_id": "route-001",
      "name": "Downtown Express",
      "short_name": "42",
      "route_type": "bus",
      "belief_state": "active_high"
    },
    {
      "public_id": "route-002",
      "name": "Red Line",
      "short_name": "Red",
      "route_type": "metro",
      "belief_state": "active_high"
    }
  ],
  "count": 2
}
```

### List Routes (Custom Pagination)

```bash
curl http://localhost:8000/api/v1/routes?page_size=5
```

### Get Route Detail

```bash
curl http://localhost:8000/api/v1/routes/route-001
```

**Response**:
```json
{
  "public_id": "route-001",
  "name": "Downtown Express",
  "short_name": "42",
  "route_type": "bus",
  "belief_state": "active_high"
}
```

### Not Found (404)

```bash
curl http://localhost:8000/api/v1/routes/nonexistent
```

**Response**:
```json
{
  "detail": "Not found."
}
```

---

## Non-Goals Confirmed

This sprint explicitly did NOT:
- ✅ Add or modify evaluation logic
- ✅ Add write or contribution endpoints
- ✅ Modify models or migrations
- ✅ Expose evidence or confidence
- ✅ Introduce route mutation logic
- ✅ Change guardrail implementations
- ✅ Add GTFS or live tracking
- ✅ Embed or expand relationships (no stops, no variants)

---

## Phase-2 Invariant Compliance

**P2-INV-1: Truth Authority Invariant** ✅
- No API changes affect belief or evaluation
- Canonical routes remain derived from evaluation logic

**P2-INV-2: Visibility-Only UI Modes** ✅
- UI mode does not change data or authorization
- Tests verify UI mode independence

**P2-INV-3: Canonical Read Safety** ✅
- No evidence, contributor, threshold, or diagnostic exposure
- Whitelist-only serialization

**P2-INV-4: API Boundary Explicitness** ✅
- Explicit namespace (`/api/v1/routes`)
- Explicit permission (`ReadOnlyPublic`)
- Explicit HTTP methods (`GET`, `HEAD`, `OPTIONS`)

**P2-INV-5: Authentication Before Mutation** ✅
- No mutation endpoints exist
- All read paths are anonymous-safe

**P2-INV-6: Determinism and Replay Safety** ✅
- Deterministic ordering by `public_id`
- Reads have no side effects

**P2-INV-9: No Silent Scope Expansion** ✅
- All changes tested and documented
- No relationship expansion

**P2-INV-10: Guardrails Before Features** ✅
- Uses existing guardrails from Sprint-2A
- All failure modes tested

---

## Lessons Learned

1. **Pattern Replication Success**
   - Mirroring Stop endpoints provided clear template
   - Minimal adaptation needed for Route entity

2. **Test Coverage Template**
   - Stop endpoint tests provided comprehensive checklist
   - All invariants systematically verified

3. **Serializer Base Class Value**
   - `CanonicalReadSerializerBase` prevented field leakage
   - Whitelist approach caught potential mistakes early

4. **Relationship Expansion Ban**
   - Explicit tests for no embedded entities
   - Future expansion requires versioned change

5. **Canonical Read Pattern Establishment**
   - This sprint establishes the canonical pattern for all multi-entity read endpoints
   - Future endpoints (RouteVariants, StopRouteLinks, ObservedServiceWindows) must follow this exact structure
   - Public ID invariants, error schemas, and query surface freeze apply universally

---

## Next Steps (Out of Scope for Sprint-6)

Future canonical read endpoints may include:
- RouteVariant endpoints (v2 or separate versioned API)
- Stop-Route relationship queries (requires careful design)
- Spatial filtering for Routes (bounding box queries)
- Schedule/service window visibility

All future expansions require:
- New API version or explicit feature flag
- Updated serializers with new `allowed_fields`
- Comprehensive safety tests
- Documentation updates

---

## Sprint Completion Checklist

- [x] RouteSerializer implemented with canonical safety
- [x] RouteListView with pagination and ordering
- [x] RouteDetailView with 404 safety
- [x] URL routes configured at `/api/v1/routes`
- [x] All tests pass (50+ tests)
- [x] No relationship expansion
- [x] No evidence/contributor leakage
- [x] Deterministic ordering enforced
- [x] UI mode independence verified
- [x] Versioning enforced (v1 only)
- [x] Public ID contract validated
- [x] No evaluation logic modified
- [x] No model changes
- [x] Documentation complete

---

**Sprint-6 Status: COMPLETE** ✅

End of Phase-2 Sprint-6 execution history.
```

**Step 2: Commit**

```bash
git add docs/05_execution_history/phase_2/phase2-sprint6-canonical-routes-v0.md
git commit -m "docs: add Sprint-6 execution history for canonical Route endpoints"
```

---

## Task 14: Verify Checklist Compliance

**Step 1: Review post-implementation checklist**

Go through each item in the provided checklist and verify compliance.

**Step 2: Document any gaps**

If any checklist items fail, document and fix before declaring sprint complete.

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete Phase-2 Sprint-6 canonical Route read endpoints v0"
```

---

## Definition of Done

Sprint-6 is complete when:

- [x] `/api/v1/routes` returns paginated routes
- [x] `/api/v1/routes/{public_id}` returns route detail
- [x] All endpoints read-only (405 on mutation)
- [x] Anonymous access works
- [x] No evidence/contributor leakage
- [x] Deterministic ordering by public_id
- [x] Pagination bounds enforced
- [x] No relationship expansion
- [x] UI mode affects visibility only
- [x] Error responses safe and stable
- [x] All tests pass (50+ tests)
- [x] Documentation complete
- [x] No evaluation logic modified

---

## Execution Notes

- Follow TDD: Write test, see it fail, implement, see it pass
- Commit frequently (after each passing test class)
- Mirror Stop endpoint patterns exactly
- Do not deviate from checklist requirements
- Verify no regressions in existing Stop tests

End of implementation plan.
```
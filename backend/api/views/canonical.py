"""
Canonical read-only views for public transit entities (Phase-2 Sprint-5).

This module implements versioned public APIs for canonical data.

VERSIONING:
All canonical read endpoints are versioned at /api/v1/*

SAFETY CONSTRAINTS:
- Read-only (GET, HEAD, OPTIONS only)
- Public access (no authentication required)
- Pagination-bounded
- Snapshot-safe (consistent per request)
- Non-leaky (no evidence, contributor, or diagnostic data)

PUBLIC IDENTIFIER INVARIANTS:
All canonical entities expose a public_id that must be:
- Deterministic (same inputs produce same ID)
- Stable across re-evaluation
- Independent of contribution volume
- Independent of database primary keys

ERROR RESPONSE CONTRACT:
All error responses (4xx, 5xx) must:
- Be JSON-formatted
- Be schema-stable across versions
- Contain no diagnostics or stack traces
- Use standard HTTP semantics only

RELATIONSHIP EXPANSION:
Canonical endpoints do NOT embed or expand related entities.
No ?include=, ?expand=, or similar parameters are supported.

CACHE SEMANTICS:
Cache behavior is undefined in v1.
Clients must not rely on cache headers.

PHILOSOPHY:
These endpoints expose what the backend conservatively believes to be true.
They must never reveal how that truth was derived, who contributed to it,
or what alternatives were considered.

Sprint-5: Implements Stop list and detail endpoints only.
"""

from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from api.permissions import ReadOnlyPublic
from api.serializers.canonical import CanonicalReadSerializerBase, CanonicalReadPaginationMixin
from api.throttling import AnonReadThrottle
from transit.models import Stop, Route


class StopSerializer(CanonicalReadSerializerBase):
    """
    Serializer for canonical Stop read endpoints.
    
    Meta.allowed_fields:
    - public_id: Stable, opaque identifier (deterministic, stable across re-evaluation)
    - name: Primary stop name
    - location: Geographic coordinates (GeoJSON)
    - belief_state: Human-readable confidence projection
    
    EXPLICITLY BLOCKED:
    - Internal UUID (id field)
    - Evidence references
    - Contributor information
    - Confidence scores
    - Timestamps
    - Alternate names (deferred to future versions)
    - Related entities (routes, variants, service windows)
    """
    
    public_id = serializers.CharField(
        help_text="Stable public identifier for this stop."
    )
    
    name = serializers.CharField(
        help_text="Primary name of the stop."
    )
    
    location = serializers.SerializerMethodField(
        help_text="Geographic location in GeoJSON format."
    )
    
    belief_state = serializers.CharField(
        help_text=(
            "Human-readable confidence state. "
            f"Valid values: {', '.join(Stop.BeliefState.values)}."
        )
    )
    
    class Meta:
        allowed_fields = {'public_id', 'name', 'location', 'belief_state'}
    
    def get_location(self, obj):
        """
        Convert PostGIS Point to GeoJSON.
        
        Returns:
            dict: GeoJSON Point geometry with coordinates in [lon, lat] order
        """
        if obj.location:
            return {
                'type': 'Point',
                'coordinates': [obj.location.x, obj.location.y]
            }
        return None


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
            f"Valid values: {', '.join(Route.RouteType.values)}."
        )
    )
    
    belief_state = serializers.CharField(
        help_text=(
            "Human-readable confidence state. "
            f"Valid values: {', '.join(Route.BeliefState.values)}."
        )
    )
    
    class Meta:
        allowed_fields = {'public_id', 'name', 'short_name', 'route_type', 'belief_state'}


class StopListView(CanonicalReadPaginationMixin, APIView):
    """
    List all canonical Stops with pagination.
    
    GET /api/v1/stops
    
    QUERY PARAMETERS:
    - page (optional): Page number (1-based, default: 1)
    - page_size (optional): Number of results per page (default: 20, max: 100)
    
    QUERY SURFACE FREEZE (v1):
    - Only pagination parameters allowed
    - No filtering, searching, or custom sorting
    - No spatial queries (?near=, ?bbox=)
    - No relationship expansion (?include=routes)
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
    - 400 Bad Request: Invalid pagination parameters (JSON format)
    - Errors contain no diagnostics or internal identifiers
    
    CACHE SEMANTICS:
    Cache behavior is undefined in v1.
    Clients must not rely on cache headers or assume cacheability.
    
    VERSIONING:
    This is v1 of the canonical Stop API.
    
    ACCESS:
    Public, read-only, anonymous access permitted.
    """
    
    permission_classes = [ReadOnlyPublic]
    throttle_classes = [AnonReadThrottle]
    http_method_names = ['get', 'head', 'options']
    
    def get(self, request):
        """
        Retrieve paginated list of canonical Stops.
        
        Returns:
            200 OK: Paginated list of stops
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
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (TypeError, ValueError):
            return Response(
                {'error': 'Invalid page parameter. Must be an integer.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate offset for pagination
        offset = (page - 1) * page_size
        
        # Deterministic ordering by public_id
        # This ensures stable pagination and reproducible results
        # PERFORMANCE NOTE (v1): Offset-based pagination has O(offset) database query cost
        # (via SQL LIMIT/OFFSET), which can degrade for large page numbers. Django does not
        # load all skipped rows into memory. Acceptable for v1 given expected dataset sizes
        # (<10k stops). Future versions may adopt cursor-based pagination for scalability.
        stops = Stop.objects.all().order_by('public_id')[offset:offset + page_size]
        
        serializer = StopSerializer(stops, many=True)
        
        return Response({
            'results': serializer.data,
            'count': len(serializer.data)
        })


class StopDetailView(APIView):
    """
    Retrieve a single canonical Stop by public_id.
    
    GET /api/v1/stops/{public_id}
    
    PATH PARAMETERS:
    - public_id: Stable public identifier for the stop (deterministic, stable)
    
    QUERY PARAMETERS:
    - None supported in v1
    - No relationship expansion (?include=routes)
    
    RESPONSES:
    - 200 OK: Stop found and returned (JSON, stable schema)
    - 404 Not Found: Stop does not exist or is sub-threshold (JSON, no diagnostics)
    
    ERROR SAFETY:
    - 404 responses do not leak:
      - Whether a stop ever existed
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
    throttle_classes = [AnonReadThrottle]
    http_method_names = ['get', 'head', 'options']
    
    def get(self, request, public_id):
        """
        Retrieve a single Stop by public_id.
        
        Args:
            public_id (str): Public identifier for the stop
            
        Returns:
            200 OK: Stop data
            404 Not Found: Stop not found
        """
        stop = get_object_or_404(Stop, public_id=public_id)
        serializer = StopSerializer(stop)
        
        return Response(serializer.data)


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
    
    VERSIONING:
    This is v1 of the canonical Route API.
    
    ACCESS:
    Public, read-only, anonymous access permitted.
    """
    
    permission_classes = [ReadOnlyPublic]
    throttle_classes = [AnonReadThrottle]
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
                    status=status.HTTP_400_BAD_REQUEST
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
        # DETERMINISM INVARIANT: Route list output must remain deterministic across
        # system restarts given identical DB state. Ordering by public_id guarantees this.
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
    throttle_classes = [AnonReadThrottle]
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

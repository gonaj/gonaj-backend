"""
Export view for user contributions (Sprint-5C).

This module provides the contribution export endpoint as part of
DATA_RIGHTS_V1 compliance (Right to Data Access).

Endpoint:
- GET /api/me/contributions/export - Export user's own contributions

PHILOSOPHY:
Export is a user right, not system introspection. Users receive only
the data they directly submitted, with no internal identifiers or
evaluation artifacts exposed.

WHAT THIS VIEW PROVIDES:
- User's own contributions in JSON format
- Only user-supplied data (timestamps, payload, geometry, type)
- Deterministic, stable export

WHAT THIS VIEW DOES NOT PROVIDE:
- Other users' data
- Canonical entities (Stops, Routes)
- Confidence values or evaluation artifacts
- Moderation history
- Internal identifiers

INVARIANTS ENFORCED:
- INV-D1: No system-internal identifiers exposed
- INV-D2: No cross-contribution linkage beyond timestamps
- INV-D3: No weakening of post-deletion anonymity
- INV-D4: No leaking contributor_fingerprint

API BOUNDARY (Phase-2 Sprint-1):
- User-scoped access only (IsAuthenticated + own data)
- GET method only (read-only)
- No mutation

CANONICAL READ HARDENING (Phase-2 Sprint-2):
- Pagination enforcement with bounded defaults
- Malformed parameter handling
- Stable output under hostile input
"""

from core.models import ContributionEvent
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from api.serializers.export import ContributionExportListSerializer
from api.views.auth import JWTAuthentication


class ContributionExportView(APIView):
    """
    API endpoint for exporting user's own contributions.

    GET /api/me/contributions/export

    Returns all contributions submitted by the authenticated user
    in a format suitable for data portability.

    REQUIREMENTS:
    - Authentication required
    - Returns 403 if user account is deactivated (deleted)
    - Only user-supplied data is returned
    - No internal identifiers exposed

    Response (200 OK):
    {
        "export_version": "1.0",
        "contribution_count": 42,
        "contributions": [
            {
                "observed_at": "2025-12-23T10:30:00Z",
                "contribution_type": "stop_exists",
                "subject_ref": {"lat": 40.7, "lon": -74.0},
                "payload": {"confidence": "high", ...}
            },
            ...
        ]
    }

    Error Responses:
    - 401 Unauthorized: Authentication required
    - 403 Forbidden: Account is deleted/deactivated
    
    API BOUNDARY (Phase-2 Sprint-1):
    - Permission: IsAuthenticated (user can only export own data)
    - HTTP Methods: GET only
    - Read-only: No mutation
    
    CANONICAL READ HARDENING (Phase-2 Sprint-2):
    - Pagination with bounded page sizes
    - Malformed parameter defaults to safe values
    - Explicit rejection of unbounded queries
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'options']  # Explicit allow-list

    def _parse_pagination_params(self, request):
        """
        Parse and validate pagination parameters from request.
        
        Returns safe defaults for malformed or missing parameters.
        Rejects unbounded queries explicitly.
        
        Phase-2 Sprint-2: Canonical read hardening
        """
        try:
            page = int(request.query_params.get('page', 1))
            if page < 1:
                page = 1
        except (ValueError, TypeError):
            page = 1
        
        try:
            page_size = int(request.query_params.get('page_size', DEFAULT_PAGE_SIZE))
            if page_size < 1:
                page_size = DEFAULT_PAGE_SIZE
            elif page_size > MAX_PAGE_SIZE:
                page_size = MAX_PAGE_SIZE
        except (ValueError, TypeError):
            page_size = DEFAULT_PAGE_SIZE
        
        return page, page_size

    def get(self, request):
        """
        Export user's contributions with pagination.

        Returns ContributionEvents submitted by the authenticated user.
        Only user-supplied fields are included - no internal identifiers.

        The export is deterministic: repeated calls with the same data
        produce identical results (ordered by observed_at).
        
        Query Parameters:
        - page: Page number (default: 1)
        - page_size: Items per page (default: 20, max: 100)
        
        Phase-2 Sprint-2: Added pagination for bounded queries.
        """
        user = request.user

        # Check if account is deactivated (deleted)
        # Sprint-5A: Deleted users have is_active=False
        # Export must not be available post-deletion (Sprint-5C requirement)
        if not user.is_active:
            return Response(
                {"error": "Account is deactivated. Export is not available."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Parse pagination parameters with safe defaults
        page, page_size = self._parse_pagination_params(request)
        
        # Query user's contributions
        # Order by observed_at for deterministic export (INV-B1 principle)
        contributions_qs = ContributionEvent.objects.filter(contributor=user).order_by(
            "observed_at", "id"
        )
        
        # Get total count for pagination metadata
        total_count = contributions_qs.count()
        
        # Apply pagination bounds
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        contributions = list(contributions_qs[start_idx:end_idx])

        # Serialize with export-specific serializer
        # This serializer explicitly excludes internal identifiers
        serializer = ContributionExportListSerializer()
        export_data = serializer.to_representation(contributions)
        
        # Add pagination metadata
        export_data["pagination"] = {
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": (total_count + page_size - 1) // page_size if total_count > 0 else 1,
            "has_next": end_idx < total_count,
            "has_previous": page > 1,
        }

        return Response(export_data, status=status.HTTP_200_OK)

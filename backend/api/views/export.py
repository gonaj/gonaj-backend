"""
User data export view (Sprint-9, Phase-2).

This module provides the contribution export endpoint as part of
DATA_RIGHTS_V1 compliance (Right to Data Access).

Endpoint:
- GET /api/v1/me/contributions/export

PHILOSOPHY:
Export is a user right, not system introspection. Users receive only
their own data in a deterministic, reproducible format.

EXPORT V1 SEMANTICS (FROZEN):
- Atomic: Complete dataset in single response
- Non-paginated: All contributions returned at once
- Non-filterable: No query parameters alter output
- Deterministic: Same data produces identical output (except generated_at)
- Ordering: By submitted_at ASC (for reproducibility only, no semantic meaning)

Any change to these semantics requires a new export version.

WHAT THIS VIEW PROVIDES:
- User's own contributions in JSON format
- User metadata (user_id, account creation date)
- Deterministic, stable export

WHAT THIS VIEW DOES NOT PROVIDE:
- Other users' data
- Canonical entities (Stops, Routes)
- Confidence values or evaluation artifacts
- Moderation history
- Internal identifiers (except user-generated contribution_id)

INVARIANTS ENFORCED:
- P2-INV-8: User data rights preserved
- INV-D1: No system-internal identifiers exposed
- INV-D4: No leaking contributor_fingerprint

AUTHORIZATION:
- Requires authentication
- Requires Capability.CONTRIBUTE
- User can only export own data
"""

from core.models import ContributionEvent
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.authz import require_capability
from api.capabilities import Capability
from api.serializers.export import ContributionExportListSerializer
from api.views.auth import JWTAuthentication


class ContributionExportView(APIView):
    """
    API endpoint for exporting user's own contributions.

    GET /api/v1/me/contributions/export

    Returns all contributions submitted by the authenticated user
    in a format suitable for GDPR-style data portability.

    EXPORT V1 CHARACTERISTICS:
    - Complete: All contributions in single response
    - Non-paginated: No page/limit parameters
    - Non-filterable: No query parameters affect output
    - Deterministic: Repeated calls return same data (except generated_at)
    - Ordered: By submitted_at ASC for reproducibility

    Response (200 OK):
    {
        "export_version": "v1",
        "generated_at": "2025-12-23T10:30:00Z",
        "user": {
            "user_id": "...",
            "created_at": "2025-01-01T00:00:00Z"
        },
        "contributions": [
            {
                "contribution_id": "...",
                "contribution_type": "stop_exists",
                "observed_at": "2025-12-23T10:30:00Z",
                "submitted_at": "2025-12-23T10:31:00Z",
                "subject_ref": {"lat": 40.7, "lon": -74.0},
                "payload": {"confidence": "high", ...}
            },
            ...
        ]
    }

    Error Responses:
    - 401 Unauthorized: Authentication required
    - 403 Forbidden: Account is deleted/deactivated or lacks capability

    AUTHORIZATION:
    - Permission: IsAuthenticated
    - Capability: Capability.CONTRIBUTE required
    - Scope: User can only export own data
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "options"]  # Explicit allow-list

    def get(self, request):
        """
        Export user's contributions (complete, non-paginated).

        Returns all ContributionEvents submitted by the authenticated user.
        Only user-facing fields are included - no internal identifiers.

        The export is deterministic: repeated calls with the same data
        produce identical results (ordered by submitted_at ASC).

        Ordering by submitted_at is for reproducibility only and has
        no semantic meaning.
        """
        # Authorization: require contribute capability
        require_capability(request, Capability.CONTRIBUTE)

        user = request.user

        # Query user's contributions
        # Order by submitted_at ASC for reproducibility (frozen v1 behavior)
        # Secondary order by id for determinism when submitted_at is equal
        contributions = ContributionEvent.objects.filter(
            contributor=user
        ).order_by("submitted_at", "id")

        # Serialize with export envelope
        serializer = ContributionExportListSerializer()
        export_data = serializer.to_representation({
            "contributions": contributions,
            "user": user,
        })

        return Response(export_data, status=status.HTTP_200_OK)

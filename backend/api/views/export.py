"""
Export view for user contributions (Sprint-5C).

This module provides the contribution export endpoint as part of
DATA_RIGHTS_V1 compliance (Right to Data Access).

Endpoint:
- GET /api/auth/me/contributions/export - Export user's own contributions

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
"""

from core.models import ContributionEvent
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers.export import ContributionExportListSerializer
from api.views.auth import JWTAuthentication


class ContributionExportView(APIView):
    """
    API endpoint for exporting user's own contributions.

    GET /api/auth/me/contributions/export

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
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Export user's contributions.

        Returns all ContributionEvents submitted by the authenticated user.
        Only user-supplied fields are included - no internal identifiers.

        The export is deterministic: repeated calls with the same data
        produce identical results (ordered by observed_at).
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

        # Query user's contributions
        # Order by observed_at for deterministic export (INV-B1 principle)
        contributions = ContributionEvent.objects.filter(contributor=user).order_by(
            "observed_at", "id"
        )

        # Serialize with export-specific serializer
        # This serializer explicitly excludes internal identifiers
        serializer = ContributionExportListSerializer()
        export_data = serializer.to_representation(list(contributions))

        return Response(export_data, status=status.HTTP_200_OK)

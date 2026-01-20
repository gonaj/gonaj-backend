"""
API views for contribution submission (Sprint-2).

This module provides authenticated write-only endpoints for submitting evidence
as ContributionEvent records.

PHILOSOPHY:
"Users submit what they saw, where they were, when it happened.
The backend decides what it means."

SCOPE (Sprint-2):
- POST /v1/contributions/ - Submit evidence (authenticated only)
- No read endpoints
- No canonical data exposure
- No evaluation or truth determination

API BOUNDARY (Phase-2 Sprint-1):
- Contributor capability required (IsContributor permission)
- POST method only (write-only endpoint)
- No anonymous mutation
"""

from api.authz import require_capability
from api.capabilities import Capability
from api.permissions import IsContributor
from api.serializers.contributions import ContributionSubmissionSerializer
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


class ContributionSubmissionView(APIView):
    """
    API endpoint for submitting contribution evidence.

    POST /v1/contributions/

    Accepts evidence from authenticated users and stores it as an immutable
    ContributionEvent record. This is a write-only endpoint that does NOT:
    - Evaluate truth or correctness
    - Update canonical entities
    - Return canonical data
    - Allow anonymous submissions

    Authentication: Required (any authenticated user may contribute)

    Idempotency: Submissions with the same client_generated_id return the
    existing event without creating a duplicate.

    Request Body:
    {
        "client_generated_id": "uuid",
        "device_id": "uuid" (optional),
        "contribution_type": "stop_exists|stop_name|...",
        "subject_ref": {"lat": 40.7, "lon": -74.0, ...},
        "payload": {"confidence": "high", ...},
        "observed_at": "2025-12-23T10:30:00Z",
        "context": {"gps_accuracy": 5.0, "app_version": "1.0.0", ...}
    }

    Response (201 Created or 200 OK for idempotent retry):
    {
        "id": "uuid",
        "client_generated_id": "uuid",
        "contribution_type": "stop_exists",
        "observed_at": "2025-12-23T10:30:00Z",
        "submitted_at": "2025-12-23T10:31:00Z",
        "created": true
    }

    Error Responses:
    - 401 Unauthorized: Authentication required
    - 403 Forbidden: Contributor capability required
    - 400 Bad Request: Invalid payload structure or validation failure
    
    API BOUNDARY (Phase-2 Sprint-1):
    - Permission: IsContributor (authenticated + contributor capability)
    - HTTP Methods: POST only
    - Mutation: Creates ContributionEvent (intentional for evidence submission)
    """

    permission_classes = [IsContributor]
    serializer_class = ContributionSubmissionSerializer
    http_method_names = ['post', 'options']  # Explicit allow-list

    def post(self, request):
        """
        Submit a contribution event.

        Validates the submission, creates an immutable ContributionEvent,
        and returns a confirmation. Supports idempotent retries.
        
        AUTHORIZATION (Phase-2 Sprint-4):
        Explicitly requires contribute capability via centralized authz module.
        """
        # Explicit capability check (centralized authorization)
        require_capability(request, Capability.CONTRIBUTE)
        
        serializer = self.serializer_class(data=request.data)

        if not serializer.is_valid():
            return Response(
                {"error": "Invalid contribution data", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Add the authenticated user as the contributor
        # This ensures contributions are always attributed
        validated_data = serializer.validated_data
        validated_data["contributor"] = request.user

        # Create the event (idempotent)
        event = serializer.create(validated_data)

        # Return appropriate status code
        # 201 Created for new events, 200 OK for idempotent retries
        response_status = (
            status.HTTP_201_CREATED
            if getattr(event, "_was_created", True)
            else status.HTTP_200_OK
        )

        return Response(serializer.to_representation(event), status=response_status)

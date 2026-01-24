"""
User self-service views for /api/me/* namespace.

This module provides views for user data rights as defined in DATA_RIGHTS_V1.
These are thin wrappers around existing services - no business logic here.

Endpoints:
- DELETE /api/me - Delete user account (AccountDeletionService)
- GET /api/me/contributions/export - Export contributions (reuses ContributionExportView)

PHILOSOPHY:
These endpoints represent user rights over their own data.
The views are routing/presentation layer only - all logic lives in services.

API BOUNDARY (Phase-2 Sprint-1):
- User-scoped access only (IsAuthenticated + own data)
- Explicit HTTP method restrictions per endpoint
- No cross-user access possible
"""

from accounts.services.account_deletion import AccountDeletionService
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.authz import require_capability
from api.capabilities import Capability
from api.idempotency import IdempotencyMixin
from api.throttling import UserWriteThrottle
from api.views.auth import JWTAuthentication, get_client_ip, get_user_agent


class AccountDeletionView(IdempotencyMixin, APIView):
    """
    API endpoint for irreversible account deletion.

    DELETE /api/me

    Permanently deletes the authenticated user's account per DATA_RIGHTS_V1:
    - Removes all identity and profile data
    - Revokes all sessions and tokens immediately
    - De-identifies contributions (preserves evidence, removes attribution)

    This action is FINAL and cannot be undone.

    Rate Limiting:
    - User-based throttling (30/minute default, configurable)
    - Returns HTTP 429 when limit exceeded

    Idempotency:
    - Idempotency-Key header provides replay protection for retries
    - Multiple DELETE requests with same key return cached response

    Response (200 OK):
    {
        "success": true,
        "deleted_at": "2025-12-30T10:30:00Z",
        "tokens_revoked": 3
    }

    Error Responses:
    - 401 Unauthorized: Authentication required
    - 409 Conflict: Idempotency-Key reused with different context
    - 429 Too Many Requests: Rate limit exceeded
    - 500 Internal Server Error: Deletion failed (should be rare)

    INVARIANTS ENFORCED:
    - Deletion is explicit and intentional
    - Deletion is immediate
    - Deletion is final
    - Evidence is preserved (de-identified, not deleted)
    
    API BOUNDARY (Phase-2 Sprint-1):
    - Permission: IsAuthenticated (user can only delete own account)
    - HTTP Methods: DELETE only
    - Mutation: Deletes user account (intentional for data rights)
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserWriteThrottle]
    http_method_names = ['delete', 'options']  # Explicit allow-list

    def delete(self, request):
        """
        Delete the authenticated user's account.

        This is a thin wrapper around AccountDeletionService.
        All deletion logic is in the service.
        
        AUTHORIZATION (Phase-2 Sprint-4):
        Requires contribute capability (authenticated user can mutate own data).
        Note: This is self-service deletion, user can only delete own account.
        
        IDEMPOTENCY (Phase-2 Sprint-7):
        Idempotency-Key header provides replay protection.
        """
        # Check for cached idempotent response (transport-level)
        cached_response = self.get_idempotent_response(request)
        if cached_response is not None:
            return cached_response
        
        # Explicit capability check (centralized authorization)
        require_capability(request, Capability.CONTRIBUTE)
        
        user = request.user

        # Already deleted users handled by service (idempotent)
        service = AccountDeletionService()
        result = service.delete_account(
            user=user,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            reason="user_initiated",
        )

        if result.success:
            response = Response(result.to_dict(), status=status.HTTP_200_OK)
        else:
            response = Response(
                result.to_dict(),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
        # Store response for transport-level idempotency
        self.store_idempotent_response(request, response)
        
        return response

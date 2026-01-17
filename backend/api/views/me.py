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

from api.views.auth import JWTAuthentication, get_client_ip, get_user_agent


class AccountDeletionView(APIView):
    """
    API endpoint for irreversible account deletion.

    DELETE /api/me

    Permanently deletes the authenticated user's account per DATA_RIGHTS_V1:
    - Removes all identity and profile data
    - Revokes all sessions and tokens immediately
    - De-identifies contributions (preserves evidence, removes attribution)

    This action is FINAL and cannot be undone.

    Response (200 OK):
    {
        "success": true,
        "deleted_at": "2025-12-30T10:30:00Z",
        "tokens_revoked": 3
    }

    Error Responses:
    - 401 Unauthorized: Authentication required
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
    http_method_names = ['delete', 'options']  # Explicit allow-list

    def delete(self, request):
        """
        Delete the authenticated user's account.

        This is a thin wrapper around AccountDeletionService.
        All deletion logic is in the service.
        """
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
            return Response(result.to_dict(), status=status.HTTP_200_OK)
        else:
            return Response(
                result.to_dict(),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

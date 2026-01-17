# API Surface Boundary Lockdown - Phase-2 Sprint-1

This document summarizes the changes made in Phase-2 Sprint-1 to lock down the API surface boundaries.

## Changes Made

### 1. New Permission Classes (`backend/api/permissions.py`)

Created three custom permission classes:

- **`DenyByDefault`**: Denies all access by default (base for future deny-by-default patterns)
- **`IsContributor`**: Requires authentication for contribution submissions (currently equivalent to `IsAuthenticated`, can be extended in future sprints)
- **`ReadOnlyPublic`**: Allows only safe (GET, HEAD, OPTIONS) methods for public read endpoints

### 2. HTTP Method Restrictions

Added `http_method_names` to all API views to explicitly allow only supported HTTP methods:

**Authentication Endpoints:**
- `MagicLinkRequestView`: POST only
- `MagicLinkVerifyView`: POST only
- `LoginView`: POST only
- `LogoutView`: POST only
- `TokenRefreshView`: POST only
- `TokenRevokeView`: POST only
- `MeView`: GET only
- `SocialCallbackView`: POST only

**User Self-Service Endpoints:**
- `AccountDeletionView`: DELETE only
- `ContributionExportView`: GET only

**Contributor Endpoints:**
- `ContributionSubmissionView`: POST only (now uses `IsContributor` permission)

### 3. URL Reorganization (`backend/api/urls.py`)

Added comprehensive documentation and namespace organization:
- **Auth Namespace** (`/api/auth/*`): Session lifecycle management
- **User Self-Service Namespace** (`/api/me/*`): User data rights (access, deletion, export)
- **Contributor Namespace** (`/api/v1/contributions/*`): Evidence submission
- **Reserved Namespaces**: Documented future endpoints for public read, admin, and third-party apps

### 4. Comprehensive Tests (`backend/api/tests/test_api_surface_boundaries.py`)

Added 483 lines of boundary enforcement tests:

**Test Classes:**
1. `AnonymousMutationTests`: Ensures anonymous users cannot mutate state
2. `HttpMethodRestrictionTests`: Validates unsupported HTTP methods return 405
3. `ReadOnlyEndpointTests`: Ensures read-only endpoints cannot be mutated
4. `PermissionBoundaryTests`: Validates permission boundaries are enforced
5. `AccessFailureSecurityTests`: Ensures access failures don't leak internal details

## Security Guarantees

After these changes, the following guarantees hold:

✅ No state-changing endpoint is accessible without authentication
✅ No endpoint accepts unintended HTTP methods (405 for unsupported)
✅ No permission ambiguity exists (all permissions explicitly declared)
✅ Access failures do not leak internal details
✅ Mutation endpoints are isolated from read endpoints

## What Was NOT Changed

In compliance with the sprint constraints:

❌ No models modified
❌ No migrations added
❌ No serializers modified (except imports)
❌ No evaluation logic changed
❌ No business logic altered
❌ No new endpoints added
❌ No request/response payload shapes changed

## Future Work

This sprint establishes the foundation for:
- Public read-only API endpoints for canonical transit data
- Third-party app OAuth scoped access
- Rate limiting and abuse prevention
- More granular contributor permissions

## Testing

All changes are covered by new tests in `test_api_surface_boundaries.py`. Run tests with:

```bash
# Using Docker (recommended)
make test

# Or directly
docker compose exec web uv run python -m pytest backend/api/tests/test_api_surface_boundaries.py -v
```

## Files Changed

- `backend/api/permissions.py` (NEW)
- `backend/api/tests/test_api_surface_boundaries.py` (NEW)
- `backend/api/urls.py` (documentation added)
- `backend/api/views/auth.py` (http_method_names added)
- `backend/api/views/contributions.py` (IsContributor permission, http_method_names)
- `backend/api/views/export.py` (http_method_names added)
- `backend/api/views/me.py` (http_method_names added)

Total: 716 lines added, 8 lines removed

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

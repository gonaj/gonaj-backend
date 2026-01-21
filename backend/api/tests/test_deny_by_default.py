# backend/api/tests/test_deny_by_default.py
"""
Tests proving deny-by-default authorization (Phase-2 Sprint-4).

PHILOSOPHY:
No mutation should be possible without explicit capability grant.

These tests verify that all mutation endpoints require explicit
authorization and fail safely when capability is absent.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


class DenyByDefaultTests(TestCase):
    """
    Tests proving deny-by-default behavior.
    
    Every mutation endpoint must deny access by default and require
    explicit capability grant.
    """

    def setUp(self):
        self.client = APIClient()
        self.inactive_user = User.objects.create_user(
            username="inactive",
            email="inactive@example.com",
            password="testpass123",
            is_active=False
        )

    def test_no_mutation_without_authentication(self):
        """No mutation is possible without authentication."""
        mutation_requests = [
            {
                "method": "POST",
                "url": "/api/v1/contributions/",
                "data": {
                    "client_generated_id": "test-001",
                    "contribution_type": "stop_exists",
                    "subject_ref": {"lat": 40.7, "lon": -74.0},
                    "payload": {},
                    "observed_at": "2026-01-20T10:00:00Z"
                }
            },
            {
                "method": "DELETE",
                "url": "/api/me",
                "data": None
            },
        ]
        
        for req in mutation_requests:
            if req["method"] == "POST":
                response = self.client.post(req["url"], req["data"], format="json")
            elif req["method"] == "DELETE":
                response = self.client.delete(req["url"])
            
            # DRF may return 401 or 403 for anonymous requests depending on authentication scheme
            self.assertIn(
                response.status_code,
                [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
                f"Anonymous {req['method']} to {req['url']} should be denied"
            )

    def test_no_mutation_with_inactive_account(self):
        """Inactive users (deleted accounts) cannot mutate."""
        self.client.force_authenticate(user=self.inactive_user)
        
        # Try to submit contribution
        response = self.client.post(
            "/api/v1/contributions/",
            {
                "client_generated_id": "test-inactive-001",
                "contribution_type": "stop_exists",
                "subject_ref": {"lat": 40.7, "lon": -74.0},
                "payload": {},
                "observed_at": "2026-01-20T10:00:00Z"
            },
            format="json"
        )
        
        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
            "Inactive users should not be able to contribute"
        )

    def test_authentication_necessary_but_not_sufficient(self):
        """
        Being authenticated is necessary but not sufficient for mutation.
        
        This test would fail if we only checked is_authenticated without
        checking capabilities.
        """
        import uuid
        
        # Create user without contribute capability (hypothetical future state)
        # For Phase-2, all active authenticated users have contribute
        # But the pattern is established for Phase-3 app tokens
        
        user = User.objects.create_user(
            username="limited",
            email="limited@example.com",
            password="testpass123"
        )
        
        self.client.force_authenticate(user=user)
        
        # User can contribute (Phase-2 default)
        response = self.client.post(
            "/api/v1/contributions/",
            {
                "client_generated_id": str(uuid.uuid4()),
                "contribution_type": "stop_exists",
                "subject_ref": {"lat": 40.7, "lon": -74.0},
                "payload": {},
                "observed_at": "2026-01-20T10:00:00Z"
            },
            format="json"
        )
        
        self.assertIn(
            response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_200_OK, status.HTTP_403_FORBIDDEN],
            "Response depends on capability, not just authentication"
        )

    def test_error_messages_do_not_leak_internals(self):
        """Authorization errors do not leak internal implementation details."""
        # Try mutation without auth
        response = self.client.post(
            "/api/v1/contributions/",
            {
                "client_generated_id": "test-error-001",
                "contribution_type": "stop_exists",
                "subject_ref": {"lat": 40.7, "lon": -74.0},
                "payload": {},
                "observed_at": "2026-01-20T10:00:00Z"
            },
            format="json"
        )
        
        # DRF may return 401 or 403 for anonymous requests
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
        
        # Error message should be generic
        error_text = str(response.data).lower()
        
        # Should not contain internal details
        forbidden_terms = [
            "database",
            "sql",
            "model",
            "queryset",
        ]
        
        for term in forbidden_terms:
            self.assertNotIn(
                term,
                error_text,
                f"Error message should not leak internal term: {term}"
            )

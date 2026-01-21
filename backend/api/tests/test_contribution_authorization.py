"""
Tests for contribution submission authorization (Phase-2 Sprint-4).

These tests verify that contribution submission requires explicit
contribute capability, independent of UI mode.
"""

import uuid
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


class ContributionAuthorizationTests(TestCase):
    """Tests for contribution submission authorization."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="contributor",
            email="contributor@example.com",
            password="testpass123"
        )
        self.inactive_user = User.objects.create_user(
            username="deleted",
            email="deleted@example.com",
            password="testpass123",
            is_active=False
        )
        
        self.contribution_data = {
            "client_generated_id": str(uuid.uuid4()),
            "contribution_type": "stop_exists",
            "subject_ref": {"lat": 40.7128, "lon": -74.0060},
            "payload": {"confidence": "high"},
            "observed_at": timezone.now().isoformat()
        }

    def test_anonymous_cannot_submit_contribution(self):
        """Anonymous users cannot submit contributions."""
        response = self.client.post(
            "/api/v1/contributions/",
            self.contribution_data,
            format="json"
        )
        
        # DRF returns 403 for IsContributor permission, which is acceptable
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
        )

    def test_authenticated_user_can_submit_contribution(self):
        """Authenticated users can submit contributions."""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.post(
            "/api/v1/contributions/",
            self.contribution_data,
            format="json"
        )
        
        self.assertIn(
            response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_200_OK]
        )

    def test_inactive_user_cannot_submit_contribution(self):
        """Inactive users (deleted accounts) cannot submit contributions."""
        self.client.force_authenticate(user=self.inactive_user)
        
        response = self.client.post(
            "/api/v1/contributions/",
            self.contribution_data,
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_ui_mode_does_not_affect_authorization(self):
        """UI mode parameter does not affect authorization outcome."""
        self.client.force_authenticate(user=self.user)
        
        # Try with different UI modes
        for ui_mode in ["read", "contributor", "admin"]:
            # Use unique ID for each submission
            test_data = self.contribution_data.copy()
            test_data["client_generated_id"] = str(uuid.uuid4())
            
            response = self.client.post(
                f"/api/v1/contributions/?ui_mode={ui_mode}",
                test_data,
                format="json"
            )
            
            # Should succeed regardless of UI mode
            self.assertIn(
                response.status_code,
                [status.HTTP_201_CREATED, status.HTTP_200_OK],
                f"Authorization should not depend on UI mode: {ui_mode}"
            )
        
        # Try without authentication and different UI modes
        self.client.force_authenticate(user=None)
        
        for ui_mode in ["contributor", "admin"]:
            # Use unique ID for each submission
            test_data = self.contribution_data.copy()
            test_data["client_generated_id"] = str(uuid.uuid4())
            
            response = self.client.post(
                f"/api/v1/contributions/?ui_mode={ui_mode}",
                test_data,
                format="json"
            )
            
            # Should fail regardless of UI mode
            self.assertIn(
                response.status_code,
                [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
                f"UI mode {ui_mode} should not grant mutation rights"
            )

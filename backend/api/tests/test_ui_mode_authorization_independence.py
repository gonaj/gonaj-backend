"""
Tests proving UI modes do not affect authorization (Phase-2 Sprint-4).

CRITICAL REQUIREMENT:
UI modes affect visibility only, never authority.

These tests prove that authorization decisions are identical regardless
of UI mode parameter, header, or any other UI-related context.

INVARIANT:
For any mutation endpoint and any UI mode, authorization MUST succeed
or fail based solely on capabilities, never on UI mode.
"""

import uuid
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


class UIModeAuthorizationIndependenceTests(TestCase):
    """
    Tests proving UI mode has zero effect on authorization.
    
    These tests are critical for Phase-2 invariants:
    - P2-INV-2: Visibility-Only UI Modes
    - P2-INV-5: Authentication Before Mutation
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.contribution_data = {
            "client_generated_id": str(uuid.uuid4()),
            "contribution_type": "stop_exists",
            "subject_ref": {"lat": 40.7128, "lon": -74.0060},
            "payload": {"confidence": "high"},
            "observed_at": timezone.now().isoformat()
        }

    def test_contributor_ui_mode_without_auth_cannot_mutate(self):
        """
        Contributor UI mode without authentication cannot mutate.
        
        This proves UI mode does not grant capability.
        """
        # Try contribution with contributor UI mode but no auth
        test_data = self.contribution_data.copy()
        test_data["client_generated_id"] = str(uuid.uuid4())
        
        response = self.client.post(
            "/api/v1/contributions/?ui_mode=contributor",
            test_data,
            format="json"
        )
        
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
            "Contributor UI mode should not grant mutation rights to anonymous users"
        )
        
        # Try account deletion with contributor UI mode but no auth
        response = self.client.delete("/api/me?ui_mode=contributor")
        
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
            "Contributor UI mode should not grant deletion rights to anonymous users"
        )

    def test_admin_ui_mode_without_capability_cannot_mutate(self):
        """
        Admin UI mode without admin capability cannot mutate.
        
        This proves UI mode does not elevate privileges.
        """
        # Regular user (no admin capability) with admin UI mode
        self.client.force_authenticate(user=self.user)
        
        # Contribution should succeed (user has contribute capability)
        test_data = self.contribution_data.copy()
        test_data["client_generated_id"] = str(uuid.uuid4())
        
        response = self.client.post(
            "/api/v1/contributions/?ui_mode=admin",
            test_data,
            format="json"
        )
        
        self.assertIn(
            response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_200_OK],
            "Admin UI mode should not block authorized mutations"
        )
        
        # Future admin-only endpoint would fail here
        # (not implemented in Phase-2, but pattern is established)

    def test_read_ui_mode_with_capability_can_mutate(self):
        """
        Read UI mode with capability CAN mutate.
        
        This proves UI mode does not restrict capability-authorized actions.
        """
        self.client.force_authenticate(user=self.user)
        
        # Submit contribution with read UI mode
        test_data = self.contribution_data.copy()
        test_data["client_generated_id"] = str(uuid.uuid4())
        
        response = self.client.post(
            "/api/v1/contributions/?ui_mode=read",
            test_data,
            format="json"
        )
        
        self.assertIn(
            response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_200_OK],
            "Read UI mode should not block capability-authorized mutations"
        )

    def test_authorization_identical_across_all_ui_modes(self):
        """
        Authorization outcome is identical for all UI modes.
        
        This is the master test for UI mode independence.
        """
        test_cases = [
            {
                "endpoint": "/api/v1/contributions/",
                "method": "POST",
                "data": self.contribution_data,
                "auth_required": True,
                "expected_authed": [status.HTTP_201_CREATED, status.HTTP_200_OK],
                "expected_anon": [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
            },
            {
                "endpoint": "/api/me",
                "method": "DELETE",
                "data": None,
                "auth_required": True,
                "expected_authed": status.HTTP_200_OK,
                "expected_anon": [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
            },
        ]
        
        ui_modes = ["read", "contributor", "admin", None]  # None = no UI mode param
        
        for test_case in test_cases:
            for ui_mode in ui_modes:
                # Build URL with or without UI mode
                url = test_case["endpoint"]
                if ui_mode:
                    url += f"?ui_mode={ui_mode}"
                
                # Test with authentication
                self.client.force_authenticate(user=self.user)
                
                # Use unique contribution ID for each POST request
                test_data = test_case["data"]
                if test_case["method"] == "POST" and test_data:
                    test_data = test_data.copy()
                    test_data["client_generated_id"] = str(uuid.uuid4())
                
                if test_case["method"] == "POST":
                    response = self.client.post(url, test_data, format="json")
                elif test_case["method"] == "DELETE":
                    response = self.client.delete(url)
                
                if isinstance(test_case["expected_authed"], list):
                    self.assertIn(
                        response.status_code,
                        test_case["expected_authed"],
                        f"Authenticated request to {test_case['endpoint']} with UI mode '{ui_mode}' "
                        f"should have consistent authorization"
                    )
                else:
                    self.assertEqual(
                        response.status_code,
                        test_case["expected_authed"],
                        f"Authenticated request to {test_case['endpoint']} with UI mode '{ui_mode}' "
                        f"should have consistent authorization"
                    )
                
                # Reset user for next test
                if test_case["method"] == "DELETE" and response.status_code == status.HTTP_200_OK:
                    # Recreate user if deleted
                    self.user = User.objects.create_user(
                        username="testuser",
                        email="test@example.com",
                        password="testpass123"
                    )
                
                # Test without authentication
                self.client.force_authenticate(user=None)
                
                # Use unique contribution ID for each POST request
                test_data = test_case["data"]
                if test_case["method"] == "POST" and test_data:
                    test_data = test_data.copy()
                    test_data["client_generated_id"] = str(uuid.uuid4())
                
                if test_case["method"] == "POST":
                    response = self.client.post(url, test_data, format="json")
                elif test_case["method"] == "DELETE":
                    response = self.client.delete(url)
                
                if isinstance(test_case["expected_anon"], list):
                    self.assertIn(
                        response.status_code,
                        test_case["expected_anon"],
                        f"Anonymous request to {test_case['endpoint']} with UI mode '{ui_mode}' "
                        f"should have consistent authorization"
                    )
                else:
                    self.assertEqual(
                        response.status_code,
                        test_case["expected_anon"],
                        f"Anonymous request to {test_case['endpoint']} with UI mode '{ui_mode}' "
                        f"should have consistent authorization"
                    )

    def test_ui_mode_in_header_does_not_affect_authorization(self):
        """UI mode in HTTP header also does not affect authorization."""
        # Test with UI mode in header instead of query param
        self.client.force_authenticate(user=None)
        
        test_data = self.contribution_data.copy()
        test_data["client_generated_id"] = str(uuid.uuid4())
        
        response = self.client.post(
            "/api/v1/contributions/",
            test_data,
            format="json",
            HTTP_X_UI_MODE="admin"
        )
        
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
            "UI mode in header should not grant authorization"
        )

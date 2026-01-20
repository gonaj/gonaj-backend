"""
Tests for capability-based permission classes (Phase-2 Sprint-4).

These tests verify that DRF permission classes correctly enforce
capability requirements.
"""

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from api.capabilities import Capability
from api.permissions import RequiresCapability
from rest_framework.views import APIView

User = get_user_model()


class RequiresCapabilityPermissionTests(TestCase):
    """Tests for RequiresCapability permission class."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.staff_user = User.objects.create_user(
            username="staffuser",
            email="staff@example.com",
            password="testpass123",
            is_staff=True
        )

    def test_read_capability_allows_anonymous(self):
        """Read capability allows anonymous users."""
        permission = RequiresCapability(Capability.READ)
        request = self.factory.get("/")
        request.user = None
        
        view = APIView()
        
        self.assertTrue(permission.has_permission(request, view))

    def test_contribute_capability_denies_anonymous(self):
        """Contribute capability denies anonymous users."""
        permission = RequiresCapability(Capability.CONTRIBUTE)
        request = self.factory.post("/")
        request.user = None
        
        view = APIView()
        
        self.assertFalse(permission.has_permission(request, view))

    def test_contribute_capability_allows_authenticated(self):
        """Contribute capability allows authenticated users."""
        permission = RequiresCapability(Capability.CONTRIBUTE)
        request = self.factory.post("/")
        request.user = self.user
        
        view = APIView()
        
        self.assertTrue(permission.has_permission(request, view))

    def test_admin_capability_denies_regular_user(self):
        """Admin capability denies non-staff users."""
        permission = RequiresCapability(Capability.ADMIN)
        request = self.factory.post("/")
        request.user = self.user
        
        view = APIView()
        
        self.assertFalse(permission.has_permission(request, view))

    def test_admin_capability_allows_staff(self):
        """Admin capability allows staff users."""
        permission = RequiresCapability(Capability.ADMIN)
        request = self.factory.post("/")
        request.user = self.staff_user
        
        view = APIView()
        
        self.assertTrue(permission.has_permission(request, view))

    def test_permission_with_custom_error_message(self):
        """Permission can have custom error message."""
        permission = RequiresCapability(
            Capability.MODERATE,
            message="Moderation access required"
        )
        
        self.assertEqual(permission.message, "Moderation access required")

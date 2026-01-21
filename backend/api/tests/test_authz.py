"""
Tests for centralized authorization logic (Phase-2 Sprint-4).

These tests verify authorization checks work correctly and independently
of UI mode or other presentation concerns.
"""

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from api.authz import get_user_capabilities, has_capability, require_capability
from api.capabilities import Capability
from rest_framework.exceptions import PermissionDenied

User = get_user_model()


class GetUserCapabilitiesTests(TestCase):
    """Tests for get_user_capabilities()."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_anonymous_user_has_read_only(self):
        """Anonymous users have only read capability."""
        request = self.factory.get("/")
        request.user = None
        
        caps = get_user_capabilities(request)
        
        self.assertIn(Capability.READ, caps)
        self.assertNotIn(Capability.CONTRIBUTE, caps)
        self.assertNotIn(Capability.MODERATE, caps)
        self.assertNotIn(Capability.ADMIN, caps)

    def test_authenticated_user_has_contribute(self):
        """Authenticated users have contribute capability."""
        user = User.objects.create_user(
            username="contributor",
            email="contributor@example.com",
            password="testpass123"
        )
        request = self.factory.get("/")
        request.user = user
        
        caps = get_user_capabilities(request)
        
        self.assertIn(Capability.READ, caps)
        self.assertIn(Capability.CONTRIBUTE, caps)
        self.assertNotIn(Capability.MODERATE, caps)
        self.assertNotIn(Capability.ADMIN, caps)

    def test_staff_user_has_admin(self):
        """Staff users have admin capability."""
        user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            is_staff=True
        )
        request = self.factory.get("/")
        request.user = user
        
        caps = get_user_capabilities(request)
        
        # Admin includes all capabilities
        self.assertIn(Capability.READ, caps)
        self.assertIn(Capability.CONTRIBUTE, caps)
        self.assertIn(Capability.MODERATE, caps)
        self.assertIn(Capability.ADMIN, caps)

    def test_inactive_user_has_read_only(self):
        """Inactive users (deleted accounts) have only read capability."""
        user = User.objects.create_user(
            username="deleted",
            email="deleted@example.com",
            password="testpass123",
            is_active=False
        )
        request = self.factory.get("/")
        request.user = user
        
        caps = get_user_capabilities(request)
        
        self.assertIn(Capability.READ, caps)
        self.assertNotIn(Capability.CONTRIBUTE, caps)


class HasCapabilityTests(TestCase):
    """Tests for has_capability()."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

    def test_has_capability_returns_true_when_present(self):
        """has_capability returns True when capability is present."""
        request = self.factory.get("/")
        request.user = self.user
        
        self.assertTrue(has_capability(request, Capability.CONTRIBUTE))

    def test_has_capability_returns_false_when_absent(self):
        """has_capability returns False when capability is absent."""
        request = self.factory.get("/")
        request.user = self.user
        
        self.assertFalse(has_capability(request, Capability.ADMIN))

    def test_has_capability_handles_anonymous(self):
        """has_capability works with anonymous users."""
        request = self.factory.get("/")
        request.user = None
        
        self.assertTrue(has_capability(request, Capability.READ))
        self.assertFalse(has_capability(request, Capability.CONTRIBUTE))


class RequireCapabilityTests(TestCase):
    """Tests for require_capability()."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

    def test_require_capability_passes_when_present(self):
        """require_capability does not raise when capability is present."""
        request = self.factory.get("/")
        request.user = self.user
        
        # Should not raise
        require_capability(request, Capability.CONTRIBUTE)

    def test_require_capability_raises_403_when_absent(self):
        """require_capability raises PermissionDenied when capability is absent."""
        request = self.factory.get("/")
        request.user = self.user
        
        with self.assertRaises(PermissionDenied) as cm:
            require_capability(request, Capability.ADMIN)
        
        # Error message should be generic (not leak capability name)
        self.assertIn("permission", str(cm.exception.detail).lower())

    def test_require_capability_raises_401_for_anonymous(self):
        """require_capability raises NotAuthenticated for anonymous users needing auth."""
        request = self.factory.get("/")
        request.user = None
        
        from rest_framework.exceptions import NotAuthenticated
        
        with self.assertRaises(NotAuthenticated):
            require_capability(request, Capability.CONTRIBUTE)

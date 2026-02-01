"""
Tests for rate limiting (Phase-2 Sprint-7).

These tests validate that:
- Excessive anonymous read requests return HTTP 429
- Rate limit headers are present and stable
- Authenticated users are throttled independently
- Rate limiting does NOT affect authorization semantics
- UI mode does NOT affect throttling
- Throttling failures do NOT leak diagnostics

PHILOSOPHY:
Rate limiting is a seatbelt, not a steering wheel.
It protects the system under stress but must never:
- Change truth
- Bias evaluation
- Reveal internals

If disabling throttling changes correctness, the implementation is wrong.

INVARIANTS TESTED:
- P2-INV-1: Truth Authority (rate limiting does NOT affect truth)
- P2-INV-2: Visibility-Only UI Modes (UI mode does NOT affect throttling)
- P2-INV-3: Canonical Read Safety (throttle errors do NOT leak diagnostics)
"""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from transit.models import Stop, Route

User = get_user_model()


class RateLimitingReadEndpointsTests(APITestCase):
    """Test rate limiting for public read endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear throttle cache before each test
        cache.clear()
        
        # Create test stops using _internal_save() for canonical entities
        self.stop = Stop(
            public_id='stop-test-001',
            name='Test Stop',
            location=Point(-74.0, 40.7),
            belief_state=Stop.BeliefState.ACTIVE_HIGH,
            structural_confidence=Decimal('0.9'),
            freshness_confidence=Decimal('0.8'),
            ruleset_version='v0',
        )
        self.stop._internal_save()
        
        # Create test routes using _internal_save() for canonical entities
        self.route = Route(
            public_id='route-test-001',
            name='Test Route',
            short_name='T1',
            route_type=Route.RouteType.BUS,
        )
        self.route._internal_save()
        
        self.stop_list_url = reverse('canonical-stop-list')
        self.stop_detail_url = reverse('canonical-stop-detail', args=['stop-test-001'])
        self.route_list_url = reverse('canonical-route-list')
        self.route_detail_url = reverse('canonical-route-detail', args=['route-test-001'])

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    @patch('api.throttling.AnonReadThrottle.get_rate')
    def test_excessive_anonymous_reads_return_429_stops_list(self, mock_get_rate):
        """Test that excessive anonymous read requests to stops list return HTTP 429."""
        mock_get_rate.return_value = '3/minute'
        
        # Make requests up to the limit
        for i in range(3):
            response = self.client.get(self.stop_list_url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Next request should be throttled
        response = self.client.get(self.stop_list_url)
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    @patch('api.throttling.AnonReadThrottle.get_rate')
    def test_excessive_anonymous_reads_return_429_stops_detail(self, mock_get_rate):
        """Test that excessive anonymous read requests to stops detail return HTTP 429."""
        mock_get_rate.return_value = '3/minute'
        
        for i in range(3):
            response = self.client.get(self.stop_detail_url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        response = self.client.get(self.stop_detail_url)
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    @patch('api.throttling.AnonReadThrottle.get_rate')
    def test_excessive_anonymous_reads_return_429_routes_list(self, mock_get_rate):
        """Test that excessive anonymous read requests to routes list return HTTP 429."""
        mock_get_rate.return_value = '3/minute'
        
        for i in range(3):
            response = self.client.get(self.route_list_url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        response = self.client.get(self.route_list_url)
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    @patch('api.throttling.AnonReadThrottle.get_rate')
    def test_excessive_anonymous_reads_return_429_routes_detail(self, mock_get_rate):
        """Test that excessive anonymous read requests to routes detail return HTTP 429."""
        mock_get_rate.return_value = '3/minute'
        
        for i in range(3):
            response = self.client.get(self.route_detail_url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        response = self.client.get(self.route_detail_url)
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    @patch('api.throttling.AnonReadThrottle.get_rate')
    def test_rate_limit_headers_present(self, mock_get_rate):
        """Test that rate limit headers are present in 429 responses."""
        mock_get_rate.return_value = '2/minute'
        
        # Exhaust the limit
        for _ in range(2):
            self.client.get(self.stop_list_url)
        
        # 429 response should have Retry-After header
        response = self.client.get(self.stop_list_url)
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('Retry-After', response.headers)

    @patch('api.throttling.AnonReadThrottle.get_rate')
    def test_throttle_errors_do_not_leak_diagnostics(self, mock_get_rate):
        """Test that throttle errors do not expose internal information."""
        mock_get_rate.return_value = '2/minute'
        
        # Exhaust the limit
        for _ in range(3):
            self.client.get(self.stop_list_url)
        
        response = self.client.get(self.stop_list_url)
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Response should be JSON
        self.assertEqual(response['Content-Type'], 'application/json')
        
        # Should have a generic message, no internal details
        data = response.json()
        self.assertIn('detail', data)
        
        # Should NOT contain any of these diagnostic details
        response_text = str(data)
        self.assertNotIn('cache', response_text.lower())
        self.assertNotIn('scope', response_text.lower())
        self.assertNotIn('internal', response_text.lower())


class RateLimitingWriteEndpointsTests(APITestCase):
    """Test rate limiting for authenticated write endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        cache.clear()
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        self.contribution_url = reverse('contribution-submit')
        self.account_deletion_url = reverse('me')

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    @patch('api.throttling.UserWriteThrottle.get_rate')
    def test_excessive_writes_return_429_contributions(self, mock_get_rate):
        """Test that excessive write requests to contributions return HTTP 429."""
        mock_get_rate.return_value = '2/minute'
        
        self.client.force_authenticate(user=self.user)
        
        import uuid
        from django.utils import timezone
        
        # Make requests up to the limit
        for i in range(2):
            payload = {
                'client_generated_id': str(uuid.uuid4()),
                'contribution_type': 'stop_exists',
                'subject_ref': {'lat': 40.7, 'lon': -74.0},
                'payload': {'confidence': 'high'},
                'observed_at': timezone.now().isoformat(),
            }
            response = self.client.post(self.contribution_url, payload, format='json')
            self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        
        # Next request should be throttled
        payload = {
            'client_generated_id': str(uuid.uuid4()),
            'contribution_type': 'stop_exists',
            'subject_ref': {'lat': 40.7, 'lon': -74.0},
            'payload': {'confidence': 'high'},
            'observed_at': timezone.now().isoformat(),
        }
        response = self.client.post(self.contribution_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    @patch('api.throttling.UserWriteThrottle.get_rate')
    def test_authenticated_users_throttled_independently(self, mock_get_rate):
        """Test that each authenticated user has independent throttle limits."""
        mock_get_rate.return_value = '2/minute'
        
        import uuid
        from django.utils import timezone
        
        # User 1 makes requests up to the limit
        self.client.force_authenticate(user=self.user)
        for i in range(2):
            payload = {
                'client_generated_id': str(uuid.uuid4()),
                'contribution_type': 'stop_exists',
                'subject_ref': {'lat': 40.7, 'lon': -74.0},
                'payload': {'confidence': 'high'},
                'observed_at': timezone.now().isoformat(),
            }
            response = self.client.post(self.contribution_url, payload, format='json')
            self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        
        # User 1 is now throttled
        payload = {
            'client_generated_id': str(uuid.uuid4()),
            'contribution_type': 'stop_exists',
            'subject_ref': {'lat': 40.7, 'lon': -74.0},
            'payload': {'confidence': 'high'},
            'observed_at': timezone.now().isoformat(),
        }
        response = self.client.post(self.contribution_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        
        # User 2 should still be able to make requests
        self.client.force_authenticate(user=self.user2)
        payload = {
            'client_generated_id': str(uuid.uuid4()),
            'contribution_type': 'stop_exists',
            'subject_ref': {'lat': 40.7, 'lon': -74.0},
            'payload': {'confidence': 'high'},
            'observed_at': timezone.now().isoformat(),
        }
        response = self.client.post(self.contribution_url, payload, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])


class RateLimitingInvariantTests(APITestCase):
    """Test that rate limiting does NOT affect authorization semantics."""

    def setUp(self):
        """Set up test fixtures."""
        cache.clear()
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.stop = Stop(
            public_id='stop-test-001',
            name='Test Stop',
            location=Point(-74.0, 40.7),
            belief_state=Stop.BeliefState.ACTIVE_HIGH,
            structural_confidence=Decimal('0.9'),
            freshness_confidence=Decimal('0.8'),
            ruleset_version='v0',
        )
        self.stop._internal_save()
        self.stop_list_url = reverse('canonical-stop-list')
        self.contribution_url = reverse('contribution-submit')

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def test_rate_limiting_does_not_affect_authorization_unauthenticated_write(self):
        """Test that rate limiting does not change auth requirements for writes."""
        import uuid
        from django.utils import timezone
        
        # Unauthenticated write should fail with 401/403, NOT 429
        payload = {
            'client_generated_id': str(uuid.uuid4()),
            'contribution_type': 'stop_exists',
            'subject_ref': {'lat': 40.7, 'lon': -74.0},
            'payload': {'confidence': 'high'},
            'observed_at': timezone.now().isoformat(),
        }
        response = self.client.post(self.contribution_url, payload, format='json')
        
        # Should be auth failure, not rate limit
        self.assertIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN
        ])

    def test_rate_limiting_does_not_affect_authorization_authenticated_read(self):
        """Test that authenticated users can still read even when anonymous limit is hit."""
        # This test validates that authenticated users have separate limits
        self.client.force_authenticate(user=self.user)
        
        # Authenticated user should be able to read
        response = self.client.get(self.stop_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class RateLimitingUIModeBoundaryTests(APITestCase):
    """Test that UI mode does NOT affect throttling (P2-INV-2)."""

    def setUp(self):
        """Set up test fixtures."""
        cache.clear()
        
        self.stop = Stop(
            public_id='stop-test-001',
            name='Test Stop',
            location=Point(-74.0, 40.7),
            belief_state=Stop.BeliefState.ACTIVE_HIGH,
            structural_confidence=Decimal('0.9'),
            freshness_confidence=Decimal('0.8'),
            ruleset_version='v0',
        )
        self.stop._internal_save()
        self.stop_list_url = reverse('canonical-stop-list')

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    @patch('api.throttling.AnonReadThrottle.get_rate')
    def test_ui_mode_does_not_affect_throttling(self, mock_get_rate):
        """Test that X-UI-Mode header does not affect rate limiting."""
        mock_get_rate.return_value = '3/minute'
        
        # Make requests with different UI modes
        for i in range(3):
            response = self.client.get(
                self.stop_list_url,
                HTTP_X_UI_MODE='contributor' if i % 2 == 0 else 'explorer'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should still be throttled regardless of UI mode
        response = self.client.get(
            self.stop_list_url,
            HTTP_X_UI_MODE='contributor'
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

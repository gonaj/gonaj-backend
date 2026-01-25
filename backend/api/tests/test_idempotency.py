"""
Tests for idempotency keys (Phase-2 Sprint-7).

These tests validate that:
- Same Idempotency-Key with same payload is safe (returns cached response)
- Same Idempotency-Key with different payload fails (409 Conflict)
- Missing Idempotency-Key behaves as non-idempotent
- Idempotency does NOT leak internal state

SCOPE:
Idempotency applies ONLY to the following mutation endpoints:
- POST /api/v1/contributions
- DELETE /api/me

No other endpoints may implement idempotency behavior in this sprint.

PHILOSOPHY:
Idempotency-Key is transport-level replay protection.
client_generated_id is domain-level deduplication.
Both coexist as layered protection (Stripe/AWS pattern).

INVARIANTS TESTED:
- P2-INV-3: Canonical Read Safety (idempotency does NOT leak internal state)
- P2-INV-5: Authentication Before Mutation (idempotency does NOT bypass auth)
"""

import uuid

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class IdempotencyKeyContributionTests(APITestCase):
    """Test idempotency key behavior for POST /api/v1/contributions."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.contribution_url = reverse('contribution-submit')
        # Clear cache before each test
        cache.clear()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def test_same_key_same_payload_returns_cached_response(self):
        """Test that replaying same Idempotency-Key with same payload returns cached response.
        
        NOTE: This tests layered protection. Either:
        - Transport-level (Idempotency-Key cache) returns cached 201
        - Domain-level (client_generated_id) returns existing 200
        
        Both are valid idempotent outcomes. We verify the second request
        does NOT create a duplicate and returns the same event ID.
        """
        self.client.force_authenticate(user=self.user)
        
        idempotency_key = str(uuid.uuid4())
        payload = {
            'client_generated_id': str(uuid.uuid4()),
            'contribution_type': 'stop_exists',
            'subject_ref': {'lat': 40.7, 'lon': -74.0},
            'payload': {'confidence': 'high'},
            'observed_at': timezone.now().isoformat(),
        }
        
        # First request
        response1 = self.client.post(
            self.contribution_url,
            payload,
            format='json',
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        
        # Second request with same key and same payload
        response2 = self.client.post(
            self.contribution_url,
            payload,
            format='json',
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )
        
        # Should return idempotent response (200 OK from either layer)
        # Transport-level cache OR domain-level client_generated_id
        self.assertIn(response2.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        
        # Critical: Response data should match original (same event ID)
        self.assertEqual(response1.data['id'], response2.data['id'])

    def test_same_key_different_payload_returns_409(self):
        """Test that replaying same Idempotency-Key with different payload returns 409."""
        self.client.force_authenticate(user=self.user)
        
        idempotency_key = str(uuid.uuid4())
        
        payload1 = {
            'client_generated_id': str(uuid.uuid4()),
            'contribution_type': 'stop_exists',
            'subject_ref': {'lat': 40.7, 'lon': -74.0},
            'payload': {'confidence': 'high'},
            'observed_at': timezone.now().isoformat(),
        }
        
        # First request
        response1 = self.client.post(
            self.contribution_url,
            payload1,
            format='json',
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        
        # Second request with same key but different payload
        payload2 = {
            'client_generated_id': str(uuid.uuid4()),  # Different!
            'contribution_type': 'route_exists',        # Different!
            'subject_ref': {'route': 'Bus 42'},         # Different!
            'payload': {'different': 'data'},           # Different!
            'observed_at': timezone.now().isoformat(),
        }
        
        response2 = self.client.post(
            self.contribution_url,
            payload2,
            format='json',
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )
        
        # Should return 409 Conflict
        self.assertEqual(response2.status_code, status.HTTP_409_CONFLICT)

    def test_missing_key_is_non_idempotent(self):
        """Test that requests without Idempotency-Key behave as non-idempotent."""
        self.client.force_authenticate(user=self.user)
        
        # Same payload submitted twice without Idempotency-Key
        payload = {
            'client_generated_id': str(uuid.uuid4()),
            'contribution_type': 'stop_exists',
            'subject_ref': {'lat': 40.7, 'lon': -74.0},
            'payload': {'confidence': 'high'},
            'observed_at': timezone.now().isoformat(),
        }
        
        # First request (no Idempotency-Key)
        response1 = self.client.post(
            self.contribution_url,
            payload,
            format='json'
        )
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        
        # Second request with different client_generated_id (no Idempotency-Key)
        payload['client_generated_id'] = str(uuid.uuid4())
        response2 = self.client.post(
            self.contribution_url,
            payload,
            format='json'
        )
        
        # Should create new contribution (normal non-idempotent behavior)
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(response1.data['id'], response2.data['id'])

    def test_idempotency_does_not_leak_internal_state(self):
        """Test that idempotency responses do not expose internal state."""
        self.client.force_authenticate(user=self.user)
        
        idempotency_key = str(uuid.uuid4())
        payload = {
            'client_generated_id': str(uuid.uuid4()),
            'contribution_type': 'stop_exists',
            'subject_ref': {'lat': 40.7, 'lon': -74.0},
            'payload': {'confidence': 'high'},
            'observed_at': timezone.now().isoformat(),
        }
        
        # First request
        self.client.post(
            self.contribution_url,
            payload,
            format='json',
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )
        
        # Second request (replay)
        response = self.client.post(
            self.contribution_url,
            payload,
            format='json',
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )
        
        # Response should NOT contain internal details
        response_text = str(response.data)
        self.assertNotIn('cache', response_text.lower())
        self.assertNotIn('idempotency', response_text.lower())
        self.assertNotIn('hash', response_text.lower())
        self.assertNotIn('replay', response_text.lower())

    def test_different_users_have_separate_idempotency_namespaces(self):
        """Test that different users can use the same Idempotency-Key."""
        user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        
        idempotency_key = str(uuid.uuid4())
        
        # User 1 creates with key
        self.client.force_authenticate(user=self.user)
        payload1 = {
            'client_generated_id': str(uuid.uuid4()),
            'contribution_type': 'stop_exists',
            'subject_ref': {'lat': 40.7, 'lon': -74.0},
            'payload': {'confidence': 'high'},
            'observed_at': timezone.now().isoformat(),
        }
        response1 = self.client.post(
            self.contribution_url,
            payload1,
            format='json',
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        
        # User 2 creates with same key, different payload (should succeed)
        self.client.force_authenticate(user=user2)
        payload2 = {
            'client_generated_id': str(uuid.uuid4()),
            'contribution_type': 'route_exists',
            'subject_ref': {'route': 'Bus 42'},
            'payload': {'different': 'data'},
            'observed_at': timezone.now().isoformat(),
        }
        response2 = self.client.post(
            self.contribution_url,
            payload2,
            format='json',
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )
        
        # Should succeed (different user = different namespace)
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)


class IdempotencyKeyAccountDeletionTests(APITestCase):
    """Test idempotency key behavior for DELETE /api/me."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.account_deletion_url = reverse('me')
        cache.clear()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def test_different_users_can_reuse_key_for_deletion(self):
        """Test that different users can use the same Idempotency-Key (namespaces)."""
        self.client.force_authenticate(user=self.user)
        
        idempotency_key = str(uuid.uuid4())
        
        # First request (User 1)
        response1 = self.client.delete(
            self.account_deletion_url,
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        # Create new user for second test (original is deleted)
        user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=user2)
        
        # Different user with same key should be able to delete
        response2 = self.client.delete(
            self.account_deletion_url,
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

    def test_same_user_replay_deletion_returns_cached_response(self):
        """Test that replaying DELETE with same user and key returns cached response."""
        self.client.force_authenticate(user=self.user)
        idempotency_key = str(uuid.uuid4())

        # First request
        response1 = self.client.delete(
            self.account_deletion_url,
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # This tests that if a user sends a DELETE request with an Idempotency-Key,
        # and then sends the exact same request again (replay), the system recognizes
        # the duplicate key and returns the stored response from the first successful
        # deletion, rather than trying to delete the account again.
        #
        # The "Magic" in the Test:
        # In a real-world scenario (using JWTs):
        # 1. First Request: Deletes account. User becomes inactive (is_active=False).
        #    Tokens are revoked.
        # 2. Second Request (Replay):
        #    Authentication Layer runs.
        #    It sees the token is invalid (revoked) OR the user is inactive.
        #    Request fails with 401 Unauthorized. The Idempotency check (which runs
        #    after Auth) is never reached.
        #
        # However, in the test environment using force_authenticate(user=user):
        # - Django's test client forces the request.user to be the user object you
        #   provided, bypassing the standard token/database checks that would normally
        #   block an inactive user.
        # - This allows the request to pass Authentication and reach the Idempotency
        #   Middleware.
        # - The middleware sees the Idempotency-Key and returns the cached 200 OK response.
        
        # Second request (Replay)
        response2 = self.client.delete(
            self.account_deletion_url,
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )
        
        # Should return cached response
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

class IdempotencyKeyAuthorizationTests(APITestCase):
    """Test that idempotency does NOT bypass authorization."""

    def setUp(self):
        """Set up test fixtures."""
        self.contribution_url = reverse('contribution-submit')
        cache.clear()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def test_idempotency_key_does_not_bypass_auth(self):
        """Test that unauthenticated requests are rejected even with Idempotency-Key."""
        idempotency_key = str(uuid.uuid4())
        payload = {
            'client_generated_id': str(uuid.uuid4()),
            'contribution_type': 'stop_exists',
            'subject_ref': {'lat': 40.7, 'lon': -74.0},
            'payload': {'confidence': 'high'},
            'observed_at': timezone.now().isoformat(),
        }
        
        # Unauthenticated request with Idempotency-Key
        response = self.client.post(
            self.contribution_url,
            payload,
            format='json',
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )
        
        # Should still require authentication
        self.assertIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN
        ])


class IdempotencyKeyConflictMessageTests(APITestCase):
    """Test that 409 conflict messages are safe and informative."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.contribution_url = reverse('contribution-submit')
        cache.clear()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def test_conflict_response_is_json(self):
        """Test that 409 response is JSON formatted."""
        self.client.force_authenticate(user=self.user)
        
        idempotency_key = str(uuid.uuid4())
        
        # First request
        payload1 = {
            'client_generated_id': str(uuid.uuid4()),
            'contribution_type': 'stop_exists',
            'subject_ref': {'lat': 40.7, 'lon': -74.0},
            'payload': {'confidence': 'high'},
            'observed_at': timezone.now().isoformat(),
        }
        self.client.post(
            self.contribution_url,
            payload1,
            format='json',
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )
        
        # Second request with different payload
        payload2 = {
            'client_generated_id': str(uuid.uuid4()),
            'contribution_type': 'route_exists',
            'subject_ref': {'route': 'Bus 42'},
            'payload': {'different': 'data'},
            'observed_at': timezone.now().isoformat(),
        }
        response = self.client.post(
            self.contribution_url,
            payload2,
            format='json',
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )
        
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response['Content-Type'], 'application/json')

    def test_conflict_response_does_not_leak_payload_hash(self):
        """Test that 409 response does not expose original payload hash."""
        self.client.force_authenticate(user=self.user)
        
        idempotency_key = str(uuid.uuid4())
        
        payload1 = {
            'client_generated_id': str(uuid.uuid4()),
            'contribution_type': 'stop_exists',
            'subject_ref': {'lat': 40.7, 'lon': -74.0},
            'payload': {'confidence': 'high'},
            'observed_at': timezone.now().isoformat(),
        }
        self.client.post(
            self.contribution_url,
            payload1,
            format='json',
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )
        
        payload2 = {
            'client_generated_id': str(uuid.uuid4()),
            'contribution_type': 'route_exists',
            'subject_ref': {'route': 'Bus 42'},
            'payload': {'different': 'data'},
            'observed_at': timezone.now().isoformat(),
        }
        response = self.client.post(
            self.contribution_url,
            payload2,
            format='json',
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )
        
        # Should NOT expose internal hashing details
        response_text = str(response.data)
        self.assertNotIn('sha', response_text.lower())
        self.assertNotIn('md5', response_text.lower())
        self.assertNotIn('hash', response_text.lower())

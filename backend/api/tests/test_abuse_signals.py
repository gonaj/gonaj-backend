"""
Tests for abuse signal collection (Phase-2 Sprint-8).

TESTING PHILOSOPHY (Sprint-8):
- Mandatory tests ensure:
  - Cache counter increments correctly
  - AbuseSignalCollector failures do not affect contribution success
  - No exceptions propagate to the API layer
- Observational logic (log emission) is NOT strictly tested via TDD

These tests verify that abuse signal collection is:
- Non-blocking
- Non-authoritative
- Failure-tolerant
"""

import uuid
from unittest.mock import MagicMock, patch

from api.abuse_signals import (
    AbuseSignalCollector,
    _compute_payload_signature,
    record_contribution_signals,
)
from core.models import ContributionEvent
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class PayloadSignatureTests(TestCase):
    """Tests for the payload signature computation."""

    def test_signature_is_deterministic(self):
        """Same inputs produce same signature."""
        sig1 = _compute_payload_signature(
            'stop_exists',
            {'lat': 40.7, 'lon': -74.0},
            {'confidence': 'high'}
        )
        sig2 = _compute_payload_signature(
            'stop_exists',
            {'lat': 40.7, 'lon': -74.0},
            {'confidence': 'high'}
        )
        self.assertEqual(sig1, sig2)

    def test_different_types_produce_different_signatures(self):
        """Different contribution types produce different signatures."""
        sig1 = _compute_payload_signature(
            'stop_exists',
            {'lat': 40.7, 'lon': -74.0},
            {'confidence': 'high'}
        )
        sig2 = _compute_payload_signature(
            'route_exists',
            {'lat': 40.7, 'lon': -74.0},
            {'confidence': 'high'}
        )
        self.assertNotEqual(sig1, sig2)

    def test_signature_uses_keys_not_values(self):
        """Signature is based on structure (keys), not exact values."""
        sig1 = _compute_payload_signature(
            'stop_exists',
            {'lat': 40.7, 'lon': -74.0},
            {'confidence': 'high'}
        )
        sig2 = _compute_payload_signature(
            'stop_exists',
            {'lat': 99.9, 'lon': -99.9},
            {'confidence': 'low'}
        )
        self.assertEqual(sig1, sig2)


class AbuseSignalCollectorTests(TestCase):
    """Unit tests for AbuseSignalCollector."""

    def setUp(self):
        self.collector = AbuseSignalCollector()
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass'
        )
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_record_submission_does_not_raise(self):
        """record_submission never raises exceptions."""
        request = MagicMock()
        request.user = self.user

        validated_data = {
            'contribution_type': 'stop_exists',
            'subject_ref': {'lat': 40.7, 'lon': -74.0},
            'payload': {'confidence': 'high'},
        }
        fingerprint = uuid.uuid4()

        # Should not raise
        self.collector.record_submission(request, validated_data, fingerprint)

    @patch('api.abuse_signals.cache')
    def test_cache_failure_is_silently_tolerated(self, mock_cache):
        """Cache failures do not propagate exceptions."""
        mock_cache.incr.side_effect = Exception('Cache down')
        mock_cache.set.side_effect = Exception('Cache down')

        request = MagicMock()
        request.user = self.user

        validated_data = {
            'contribution_type': 'stop_exists',
            'subject_ref': {'lat': 40.7, 'lon': -74.0},
            'payload': {'confidence': 'high'},
        }
        fingerprint = uuid.uuid4()

        # Should not raise even with cache failures
        self.collector.record_submission(request, validated_data, fingerprint)

    def test_velocity_counter_increments(self):
        """Velocity counters increment correctly."""
        request = MagicMock()
        request.user = self.user

        validated_data = {
            'contribution_type': 'stop_exists',
            'subject_ref': {'lat': 40.7, 'lon': -74.0},
            'payload': {'confidence': 'high'},
        }
        fingerprint = uuid.uuid4()

        # First submission
        self.collector.record_submission(request, validated_data, fingerprint)

        # Check user velocity counter
        user_key = f'abuse:velocity:user:{self.user.id}'
        user_count = cache.get(user_key)
        self.assertEqual(user_count, 1)

        # Second submission
        self.collector.record_submission(request, validated_data, fingerprint)

        user_count = cache.get(user_key)
        self.assertEqual(user_count, 2)

    def test_fingerprint_velocity_tracked_separately(self):
        """Fingerprint velocity is tracked separately from user velocity."""
        request = MagicMock()
        request.user = self.user

        validated_data = {
            'contribution_type': 'stop_exists',
            'subject_ref': {'lat': 40.7, 'lon': -74.0},
            'payload': {'confidence': 'high'},
        }
        fingerprint = uuid.uuid4()

        self.collector.record_submission(request, validated_data, fingerprint)

        user_key = f'abuse:velocity:user:{self.user.id}'
        fp_key = f'abuse:velocity:fp:{fingerprint}'

        # Both should be tracked
        self.assertEqual(cache.get(user_key), 1)
        self.assertEqual(cache.get(fp_key), 1)


class AbuseSignalNonInterferenceTests(APITestCase):
    """
    Integration tests ensuring abuse signals do not affect contributions.
    
    These tests verify the critical invariant:
    Signal collection does NOT affect evaluation outcomes.
    """

    def setUp(self):
        self.url = reverse('contribution-submit')
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass'
        )
        self.client.force_authenticate(user=self.user)
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_contribution_succeeds_with_cache_failure(self):
        """Contributions succeed even when cache fails completely."""
        with patch('api.abuse_signals.cache') as mock_cache:
            mock_cache.incr.side_effect = Exception('Cache down')
            mock_cache.set.side_effect = Exception('Cache down')

            payload = {
                'client_generated_id': str(uuid.uuid4()),
                'contribution_type': 'stop_exists',
                'subject_ref': {'lat': 40.7, 'lon': -74.0},
                'payload': {'confidence': 'high'},
                'observed_at': timezone.now().isoformat(),
            }

            response = self.client.post(self.url, payload, format='json')

            # Contribution MUST succeed despite cache failure
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(ContributionEvent.objects.count(), 1)

    def test_contribution_data_unchanged_by_signals(self):
        """Signal collection does not modify contribution data."""
        payload = {
            'client_generated_id': str(uuid.uuid4()),
            'contribution_type': 'stop_exists',
            'subject_ref': {'lat': 40.7, 'lon': -74.0},
            'payload': {'confidence': 'high'},
            'observed_at': timezone.now().isoformat(),
        }

        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify contribution data is unchanged
        event = ContributionEvent.objects.get(id=response.data['id'])
        self.assertEqual(event.contribution_type, 'stop_exists')
        self.assertEqual(event.subject_ref, {'lat': 40.7, 'lon': -74.0})
        self.assertEqual(event.payload, {'confidence': 'high'})

    def test_no_new_identifiers_created(self):
        """Signal collection does not create new identifiers."""
        initial_user_count = User.objects.count()

        payload = {
            'client_generated_id': str(uuid.uuid4()),
            'contribution_type': 'stop_exists',
            'subject_ref': {'lat': 40.7, 'lon': -74.0},
            'payload': {'confidence': 'high'},
            'observed_at': timezone.now().isoformat(),
        }

        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # No new users created
        self.assertEqual(User.objects.count(), initial_user_count)

        # No new contribution events beyond the one submitted
        self.assertEqual(ContributionEvent.objects.count(), 1)

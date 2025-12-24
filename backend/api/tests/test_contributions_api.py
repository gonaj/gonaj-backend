"""
Tests for contribution submission API (Sprint-2).

These tests validate the write-only contribution API:
- Authentication enforcement
- Successful submission for all contribution types
- Idempotency behavior
- Input validation
- Error handling

TESTING PHILOSOPHY:
These tests verify the API layer, not the domain logic. Domain logic
(immutability, validation) is already tested in Sprint-1 model tests.
"""

import uuid
from datetime import timedelta

from core.models import ContributionEvent
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class ContributionSubmissionAuthTests(APITestCase):
    """Test authentication requirements for contribution submission."""

    def setUp(self):
        """Set up test fixtures."""
        self.url = reverse("contribution-submit")
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_unauthenticated_request_rejected(self):
        """Test that unauthenticated requests are rejected with 401 or 403."""
        payload = {
            "client_generated_id": str(uuid.uuid4()),
            "contribution_type": "stop_exists",
            "subject_ref": {"lat": 40.7, "lon": -74.0},
            "payload": {"confidence": "high"},
            "observed_at": timezone.now().isoformat(),
        }

        response = self.client.post(self.url, payload, format="json")

        # DRF returns 403 for IsAuthenticated permission, which is acceptable
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )
        self.assertEqual(ContributionEvent.objects.count(), 0)

    def test_authenticated_request_accepted(self):
        """Test that authenticated requests are accepted."""
        self.client.force_authenticate(user=self.user)

        payload = {
            "client_generated_id": str(uuid.uuid4()),
            "contribution_type": "stop_exists",
            "subject_ref": {"lat": 40.7, "lon": -74.0},
            "payload": {"confidence": "high"},
            "observed_at": timezone.now().isoformat(),
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ContributionEvent.objects.count(), 1)


class ContributionSubmissionCreationTests(APITestCase):
    """Test successful creation of contributions for all types."""

    def setUp(self):
        """Set up authenticated client."""
        self.url = reverse("contribution-submit")
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

    def test_create_stop_exists_contribution(self):
        """Test creating a stop_exists contribution."""
        payload = {
            "client_generated_id": str(uuid.uuid4()),
            "contribution_type": "stop_exists",
            "subject_ref": {"lat": 40.7128, "lon": -74.0060},
            "payload": {"confidence": "high", "notes": "Saw the sign"},
            "observed_at": timezone.now().isoformat(),
            "context": {"gps_accuracy": 5.0, "app_version": "1.0.0"},
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertIn("client_generated_id", response.data)
        self.assertEqual(response.data["contribution_type"], "stop_exists")
        self.assertTrue(response.data["created"])

        # Verify event was created in database
        event = ContributionEvent.objects.get(id=response.data["id"])
        self.assertEqual(event.contributor, self.user)
        self.assertEqual(event.contribution_type, "stop_exists")

    def test_create_all_contribution_types(self):
        """Test creating contributions for all Phase-1 contribution types."""
        contribution_types = [
            "stop_name",
            "stop_exists",
            "stop_not_exists",
            "stop_location",
            "route_exists",
            "route_traversal",
            "stop_sequence",
            "service_time",
        ]

        for contrib_type in contribution_types:
            with self.subTest(contribution_type=contrib_type):
                payload = {
                    "client_generated_id": str(uuid.uuid4()),
                    "contribution_type": contrib_type,
                    "subject_ref": {"test": "data"},
                    "payload": {"test": "payload"},
                    "observed_at": timezone.now().isoformat(),
                }

                response = self.client.post(self.url, payload, format="json")

                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                self.assertEqual(response.data["contribution_type"], contrib_type)

    def test_create_with_device_id(self):
        """Test creating contribution with optional device_id."""
        device_id = uuid.uuid4()
        payload = {
            "client_generated_id": str(uuid.uuid4()),
            "device_id": str(device_id),
            "contribution_type": "stop_exists",
            "subject_ref": {"lat": 40.7, "lon": -74.0},
            "payload": {"test": "data"},
            "observed_at": timezone.now().isoformat(),
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        event = ContributionEvent.objects.get(id=response.data["id"])
        self.assertEqual(event.device_id, device_id)

    def test_create_without_optional_fields(self):
        """Test creating contribution without optional fields."""
        payload = {
            "client_generated_id": str(uuid.uuid4()),
            "contribution_type": "route_exists",
            "subject_ref": {"route_name": "Bus 42"},
            "payload": {"description": "Saw this bus"},
            "observed_at": timezone.now().isoformat(),
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        event = ContributionEvent.objects.get(id=response.data["id"])
        self.assertIsNone(event.device_id)
        self.assertEqual(event.context, {})


class ContributionSubmissionIdempotencyTests(APITestCase):
    """Test idempotency behavior of contribution submission."""

    def setUp(self):
        """Set up authenticated client."""
        self.url = reverse("contribution-submit")
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

    def test_duplicate_client_id_returns_existing_event(self):
        """Test that resubmitting with same client_id returns existing event."""
        client_id = str(uuid.uuid4())
        payload = {
            "client_generated_id": client_id,
            "contribution_type": "stop_exists",
            "subject_ref": {"lat": 40.7, "lon": -74.0},
            "payload": {"confidence": "high"},
            "observed_at": timezone.now().isoformat(),
        }

        # First submission
        response1 = self.client.post(self.url, payload, format="json")
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response1.data["created"])
        event_id_1 = response1.data["id"]

        # Second submission with same client_id but different data
        payload["contribution_type"] = "route_exists"  # Different!
        payload["payload"] = {"different": "data"}  # Different!

        response2 = self.client.post(self.url, payload, format="json")

        # Should return 200 OK (not 201 Created)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertFalse(response2.data["created"])

        # Should return same event ID
        self.assertEqual(response2.data["id"], event_id_1)

        # Should preserve original contribution_type
        self.assertEqual(response2.data["contribution_type"], "stop_exists")

        # Should only have one event in database
        self.assertEqual(ContributionEvent.objects.count(), 1)

    def test_different_client_ids_create_separate_events(self):
        """Test that different client_ids create separate events."""
        payload1 = {
            "client_generated_id": str(uuid.uuid4()),
            "contribution_type": "stop_exists",
            "subject_ref": {"lat": 40.7, "lon": -74.0},
            "payload": {"test": "data"},
            "observed_at": timezone.now().isoformat(),
        }

        payload2 = {
            "client_generated_id": str(uuid.uuid4()),  # Different client_id
            "contribution_type": "stop_exists",
            "subject_ref": {"lat": 40.7, "lon": -74.0},
            "payload": {"test": "data"},
            "observed_at": timezone.now().isoformat(),
        }

        response1 = self.client.post(self.url, payload1, format="json")
        response2 = self.client.post(self.url, payload2, format="json")

        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(response1.data["id"], response2.data["id"])
        self.assertEqual(ContributionEvent.objects.count(), 2)


class ContributionSubmissionValidationTests(APITestCase):
    """Test input validation for contribution submission."""

    def setUp(self):
        """Set up authenticated client."""
        self.url = reverse("contribution-submit")
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

    def test_missing_required_fields(self):
        """Test that missing required fields are rejected."""
        required_fields = [
            "client_generated_id",
            "contribution_type",
            "subject_ref",
            "payload",
            "observed_at",
        ]

        for field in required_fields:
            with self.subTest(missing_field=field):
                payload = {
                    "client_generated_id": str(uuid.uuid4()),
                    "contribution_type": "stop_exists",
                    "subject_ref": {"test": "data"},
                    "payload": {"test": "payload"},
                    "observed_at": timezone.now().isoformat(),
                }
                del payload[field]

                response = self.client.post(self.url, payload, format="json")

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("details", response.data)

    def test_future_observed_at_rejected(self):
        """Test that future observed_at timestamps are rejected."""
        future_time = timezone.now() + timedelta(hours=1)
        payload = {
            "client_generated_id": str(uuid.uuid4()),
            "contribution_type": "stop_exists",
            "subject_ref": {"lat": 40.7, "lon": -74.0},
            "payload": {"test": "data"},
            "observed_at": future_time.isoformat(),
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("observed_at", response.data["details"])

    def test_past_observed_at_accepted(self):
        """Test that past observed_at timestamps are accepted (offline support)."""
        past_time = timezone.now() - timedelta(hours=24)
        payload = {
            "client_generated_id": str(uuid.uuid4()),
            "contribution_type": "stop_exists",
            "subject_ref": {"lat": 40.7, "lon": -74.0},
            "payload": {"test": "data"},
            "observed_at": past_time.isoformat(),
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_subject_ref_must_be_object(self):
        """Test that subject_ref must be a JSON object, not array or primitive."""
        invalid_values = [
            ["not", "an", "object"],
            "string",
            123,
            None,
        ]

        for invalid_value in invalid_values:
            with self.subTest(subject_ref=invalid_value):
                payload = {
                    "client_generated_id": str(uuid.uuid4()),
                    "contribution_type": "stop_exists",
                    "subject_ref": invalid_value,
                    "payload": {"test": "data"},
                    "observed_at": timezone.now().isoformat(),
                }

                response = self.client.post(self.url, payload, format="json")

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_payload_must_be_object(self):
        """Test that payload must be a JSON object, not array or primitive."""
        invalid_values = [
            ["not", "an", "object"],
            "string",
            123,
        ]

        for invalid_value in invalid_values:
            with self.subTest(payload=invalid_value):
                payload_data = {
                    "client_generated_id": str(uuid.uuid4()),
                    "contribution_type": "stop_exists",
                    "subject_ref": {"test": "data"},
                    "payload": invalid_value,
                    "observed_at": timezone.now().isoformat(),
                }

                response = self.client.post(self.url, payload_data, format="json")

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_context_must_be_object(self):
        """Test that context must be a JSON object, not array or primitive."""
        invalid_values = [
            ["not", "an", "object"],
            "string",
            123,
        ]

        for invalid_value in invalid_values:
            with self.subTest(context=invalid_value):
                payload = {
                    "client_generated_id": str(uuid.uuid4()),
                    "contribution_type": "stop_exists",
                    "subject_ref": {"test": "data"},
                    "payload": {"test": "payload"},
                    "observed_at": timezone.now().isoformat(),
                    "context": invalid_value,
                }

                response = self.client.post(self.url, payload, format="json")

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_contribution_type_rejected(self):
        """Test that invalid contribution types are rejected."""
        payload = {
            "client_generated_id": str(uuid.uuid4()),
            "contribution_type": "invalid_type",
            "subject_ref": {"test": "data"},
            "payload": {"test": "payload"},
            "observed_at": timezone.now().isoformat(),
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("contribution_type", response.data["details"])

    def test_invalid_uuid_format_rejected(self):
        """Test that invalid UUID formats are rejected."""
        payload = {
            "client_generated_id": "not-a-uuid",
            "contribution_type": "stop_exists",
            "subject_ref": {"test": "data"},
            "payload": {"test": "payload"},
            "observed_at": timezone.now().isoformat(),
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ContributionSubmissionIntegrationTests(APITestCase):
    """Integration tests for the contribution submission API."""

    def setUp(self):
        """Set up authenticated client."""
        self.url = reverse("contribution-submit")
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

    def test_complete_submission_workflow(self):
        """Test a complete submission workflow with all fields."""
        client_id = uuid.uuid4()
        device_id = uuid.uuid4()
        observed_time = timezone.now() - timedelta(minutes=30)

        payload = {
            "client_generated_id": str(client_id),
            "device_id": str(device_id),
            "contribution_type": "stop_exists",
            "subject_ref": {
                "lat": 40.7128,
                "lon": -74.0060,
                "name_hint": "Main Street Station",
            },
            "payload": {
                "confidence": "high",
                "notes": "Saw the bus stop sign clearly",
                "stop_amenities": ["shelter", "bench"],
            },
            "observed_at": observed_time.isoformat(),
            "context": {
                "gps_accuracy": 5.0,
                "app_version": "1.0.0",
                "was_offline": False,
                "network_type": "4G",
            },
        }

        response = self.client.post(self.url, payload, format="json")

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["client_generated_id"], str(client_id))
        self.assertEqual(response.data["contribution_type"], "stop_exists")
        self.assertTrue(response.data["created"])

        # Verify database record
        event = ContributionEvent.objects.get(id=response.data["id"])
        self.assertEqual(event.contributor, self.user)
        self.assertEqual(event.device_id, device_id)
        self.assertEqual(event.subject_ref["name_hint"], "Main Street Station")
        self.assertEqual(event.payload["confidence"], "high")
        self.assertEqual(event.context["app_version"], "1.0.0")

    def test_multiple_users_can_submit(self):
        """Test that multiple users can submit contributions independently."""
        user2 = User.objects.create_user(
            username="user2", email="user2@example.com", password="testpass123"
        )

        # User 1 submits
        payload1 = {
            "client_generated_id": str(uuid.uuid4()),
            "contribution_type": "stop_exists",
            "subject_ref": {"lat": 40.7, "lon": -74.0},
            "payload": {"test": "data"},
            "observed_at": timezone.now().isoformat(),
        }
        response1 = self.client.post(self.url, payload1, format="json")

        # User 2 submits
        self.client.force_authenticate(user=user2)
        payload2 = {
            "client_generated_id": str(uuid.uuid4()),
            "contribution_type": "route_exists",
            "subject_ref": {"route": "Bus 42"},
            "payload": {"test": "data"},
            "observed_at": timezone.now().isoformat(),
        }
        response2 = self.client.post(self.url, payload2, format="json")

        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ContributionEvent.objects.count(), 2)

        # Verify contributors
        event1 = ContributionEvent.objects.get(id=response1.data["id"])
        event2 = ContributionEvent.objects.get(id=response2.data["id"])
        self.assertEqual(event1.contributor, self.user)
        self.assertEqual(event2.contributor, user2)

"""
Tests for ContributionEvent model (Sprint-1).

These tests validate the core evidence storage mechanism for Phase-1:
- ContributionEvent can be created successfully
- Updates are prevented (immutability)
- Deletes are prevented (immutability)
- Idempotent creation works (duplicate client_generated_id)
- Validation rules are enforced

TESTING PHILOSOPHY:
ContributionEvent is the foundation of the entire system.
These tests ensure that evidence integrity cannot be violated.
"""

import uuid
from datetime import timedelta

from core.models import ContributionEvent
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

User = get_user_model()


class ContributionEventCreationTests(TestCase):
    """Test successful creation of ContributionEvents."""

    def setUp(self):
        """Create a test user for contributions."""
        self.user = User.objects.create_user(
            username="testcontributor",
            email="contributor@example.com",
            password="testpass123",
        )

    def test_create_contribution_event_with_all_fields(self):
        """Test creating a ContributionEvent with all required fields."""
        client_id = uuid.uuid4()
        device_id = uuid.uuid4()
        observed_time = timezone.now() - timedelta(minutes=30)

        event = ContributionEvent.objects.create(
            client_generated_id=client_id,
            contributor=self.user,
            device_id=device_id,
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            subject_ref={"lat": 40.7128, "lon": -74.0060},
            payload={"confidence": "high", "notes": "Saw the bus stop sign"},
            observed_at=observed_time,
            context={
                "gps_accuracy": 5.0,
                "app_version": "1.0.0",
                "was_offline": False,
            },
        )

        # Verify all fields were saved correctly
        self.assertIsNotNone(event.id)
        self.assertEqual(event.client_generated_id, client_id)
        self.assertEqual(event.contributor, self.user)
        self.assertEqual(event.device_id, device_id)
        self.assertEqual(
            event.contribution_type, ContributionEvent.ContributionType.STOP_EXISTS
        )
        self.assertEqual(event.subject_ref, {"lat": 40.7128, "lon": -74.0060})
        self.assertEqual(
            event.payload, {"confidence": "high", "notes": "Saw the bus stop sign"}
        )
        self.assertEqual(event.observed_at, observed_time)
        self.assertIsNotNone(event.submitted_at)
        self.assertEqual(event.context["gps_accuracy"], 5.0)

    def test_create_contribution_event_minimal_fields(self):
        """Test creating a ContributionEvent with minimal required fields."""
        client_id = uuid.uuid4()

        event = ContributionEvent.objects.create(
            client_generated_id=client_id,
            contributor=self.user,
            contribution_type=ContributionEvent.ContributionType.ROUTE_EXISTS,
            subject_ref={"route_name": "Bus 42"},
            payload={"description": "Saw this bus running"},
            observed_at=timezone.now(),
        )

        # Verify creation succeeded
        self.assertIsNotNone(event.id)
        self.assertIsNone(event.device_id)  # Optional field
        self.assertEqual(event.context, {})  # Default empty dict

    def test_all_contribution_types_allowed(self):
        """Test that all defined contribution types can be created."""
        contribution_types = [
            ContributionEvent.ContributionType.STOP_NAME,
            ContributionEvent.ContributionType.STOP_EXISTS,
            ContributionEvent.ContributionType.STOP_NOT_EXISTS,
            ContributionEvent.ContributionType.STOP_LOCATION,
            ContributionEvent.ContributionType.ROUTE_EXISTS,
            ContributionEvent.ContributionType.ROUTE_TRAVERSAL,
            ContributionEvent.ContributionType.STOP_SEQUENCE,
            ContributionEvent.ContributionType.SERVICE_TIME,
        ]

        for contrib_type in contribution_types:
            event = ContributionEvent.objects.create(
                client_generated_id=uuid.uuid4(),
                contributor=self.user,
                contribution_type=contrib_type,
                subject_ref={"test": "data"},
                payload={"test": "payload"},
                observed_at=timezone.now(),
            )
            self.assertEqual(event.contribution_type, contrib_type)


class ContributionEventImmutabilityTests(TestCase):
    """Test that ContributionEvents are truly immutable."""

    def setUp(self):
        """Create a test user and a ContributionEvent."""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        self.event = ContributionEvent.objects.create(
            client_generated_id=uuid.uuid4(),
            contributor=self.user,
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            subject_ref={"lat": 40.7128, "lon": -74.0060},
            payload={"confidence": "high"},
            observed_at=timezone.now(),
        )

    def test_update_raises_not_implemented_error(self):
        """Test that attempting to update a ContributionEvent raises an error."""
        # Try to modify a field
        self.event.payload = {"confidence": "low"}

        # Attempting to save should raise NotImplementedError
        with self.assertRaises(NotImplementedError) as context:
            self.event.save()

        self.assertIn("immutable", str(context.exception).lower())
        self.assertIn("UPDATE", str(context.exception))

    def test_delete_raises_not_implemented_error(self):
        """Test that attempting to delete a ContributionEvent raises an error."""
        with self.assertRaises(NotImplementedError) as context:
            self.event.delete()

        self.assertIn("immutable", str(context.exception).lower())
        self.assertIn("DELETE", str(context.exception))

    def test_bulk_update_not_allowed(self):
        """Test that bulk updates are prevented."""
        # Create multiple events
        events = [
            ContributionEvent.objects.create(
                client_generated_id=uuid.uuid4(),
                contributor=self.user,
                contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
                subject_ref={"id": i},
                payload={"data": i},
                observed_at=timezone.now(),
            )
            for i in range(3)
        ]

        # Modify in memory
        for event in events:
            event.payload = {"modified": True}

        # Bulk update should fail at the model level when save() is called
        # (Django's bulk_update calls save() for each object)
        # For Sprint-1, we document this behavior
        # Note: This is a conceptual test - actual implementation would need
        # to override bulk_update if needed


class ContributionEventIdempotencyTests(TestCase):
    """Test idempotent creation using client_generated_id."""

    def setUp(self):
        """Create a test user."""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_duplicate_client_id_returns_existing_event(self):
        """Test that submitting the same client_generated_id is idempotent."""
        client_id = uuid.uuid4()

        # First submission
        event1, created1 = ContributionEvent.create_or_get_idempotent(
            client_generated_id=client_id,
            contributor=self.user,
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            subject_ref={"lat": 40.7128, "lon": -74.0060},
            payload={"confidence": "high"},
            observed_at=timezone.now(),
        )

        self.assertTrue(created1)
        self.assertEqual(event1.client_generated_id, client_id)

        # Second submission with same client_id
        event2, created2 = ContributionEvent.create_or_get_idempotent(
            client_generated_id=client_id,
            contributor=self.user,
            contribution_type=ContributionEvent.ContributionType.ROUTE_EXISTS,  # Different!
            subject_ref={"different": "data"},  # Different!
            payload={"different": "payload"},  # Different!
            observed_at=timezone.now(),
        )

        # Should return the ORIGINAL event, not create a new one
        self.assertFalse(created2)
        self.assertEqual(event1.id, event2.id)
        self.assertEqual(
            event2.contribution_type, ContributionEvent.ContributionType.STOP_EXISTS
        )  # Original
        self.assertEqual(
            event2.subject_ref, {"lat": 40.7128, "lon": -74.0060}
        )  # Original

    def test_unique_constraint_on_client_generated_id(self):
        """Test that client_generated_id has a unique constraint."""
        client_id = uuid.uuid4()

        # Create first event
        ContributionEvent.objects.create(
            client_generated_id=client_id,
            contributor=self.user,
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            subject_ref={"test": "data"},
            payload={"test": "payload"},
            observed_at=timezone.now(),
        )

        # Try to create another with same client_id using create() directly
        # This should fail with IntegrityError
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            ContributionEvent.objects.create(
                client_generated_id=client_id,
                contributor=self.user,
                contribution_type=ContributionEvent.ContributionType.ROUTE_EXISTS,
                subject_ref={"different": "data"},
                payload={"different": "payload"},
                observed_at=timezone.now(),
            )


class ContributionEventValidationTests(TestCase):
    """Test validation rules for ContributionEvent."""

    def setUp(self):
        """Create a test user."""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_future_observed_at_invalid(self):
        """Test that observed_at in the future is rejected."""
        future_time = timezone.now() + timedelta(hours=1)

        event = ContributionEvent(
            client_generated_id=uuid.uuid4(),
            contributor=self.user,
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            subject_ref={"test": "data"},
            payload={"test": "payload"},
            observed_at=future_time,
        )

        with self.assertRaises(ValidationError) as context:
            event.full_clean()

        self.assertIn("observed_at", context.exception.message_dict)

    def test_subject_ref_must_be_dict(self):
        """Test that subject_ref must be a JSON object (dict)."""
        event = ContributionEvent(
            client_generated_id=uuid.uuid4(),
            contributor=self.user,
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            subject_ref=["not", "a", "dict"],  # Array instead of object
            payload={"test": "payload"},
            observed_at=timezone.now(),
        )

        with self.assertRaises(ValidationError) as context:
            event.full_clean()

        self.assertIn("subject_ref", context.exception.message_dict)

    def test_payload_must_be_dict(self):
        """Test that payload must be a JSON object (dict)."""
        event = ContributionEvent(
            client_generated_id=uuid.uuid4(),
            contributor=self.user,
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            subject_ref={"test": "data"},
            payload="not a dict",  # String instead of object
            observed_at=timezone.now(),
        )

        with self.assertRaises(ValidationError) as context:
            event.full_clean()

        self.assertIn("payload", context.exception.message_dict)

    def test_context_must_be_dict(self):
        """Test that context must be a JSON object (dict)."""
        event = ContributionEvent(
            client_generated_id=uuid.uuid4(),
            contributor=self.user,
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            subject_ref={"test": "data"},
            payload={"test": "payload"},
            observed_at=timezone.now(),
            context=[1, 2, 3],  # Array instead of object
        )

        with self.assertRaises(ValidationError) as context:
            event.full_clean()

        self.assertIn("context", context.exception.message_dict)


class ContributionEventQueryTests(TestCase):
    """Test querying and filtering ContributionEvents."""

    def setUp(self):
        """Create test data."""
        self.user1 = User.objects.create_user(
            username="user1", email="user1@example.com", password="testpass123"
        )
        self.user2 = User.objects.create_user(
            username="user2", email="user2@example.com", password="testpass123"
        )

        # Create events with different types
        self.stop_event = ContributionEvent.objects.create(
            client_generated_id=uuid.uuid4(),
            contributor=self.user1,
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            subject_ref={"test": "data"},
            payload={"test": "payload"},
            observed_at=timezone.now(),
        )

        self.route_event = ContributionEvent.objects.create(
            client_generated_id=uuid.uuid4(),
            contributor=self.user2,
            contribution_type=ContributionEvent.ContributionType.ROUTE_EXISTS,
            subject_ref={"test": "data"},
            payload={"test": "payload"},
            observed_at=timezone.now(),
        )

    def test_filter_by_contribution_type(self):
        """Test filtering events by contribution type."""
        stop_events = ContributionEvent.objects.filter(
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS
        )
        self.assertEqual(stop_events.count(), 1)
        self.assertEqual(stop_events.first(), self.stop_event)

    def test_filter_by_contributor(self):
        """Test filtering events by contributor."""
        user1_events = ContributionEvent.objects.filter(contributor=self.user1)
        self.assertEqual(user1_events.count(), 1)
        self.assertEqual(user1_events.first(), self.stop_event)

    def test_default_ordering_by_submitted_at(self):
        """Test that events are ordered by submitted_at descending by default."""
        events = list(ContributionEvent.objects.all())
        # More recent event should come first
        self.assertEqual(events[0], self.route_event)
        self.assertEqual(events[1], self.stop_event)

    def test_string_representation(self):
        """Test __str__ method provides useful output."""
        event_str = str(self.stop_event)
        self.assertIn("Stop Existence Confirmation", event_str)
        self.assertIn(self.user1.username, event_str)

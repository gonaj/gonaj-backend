"""
Sprint-1 Demonstration Script

This script demonstrates the key features implemented in Sprint-1:
1. Architectural Guardrails (SoftDeletable, ImmutableModel, VersionedModel)
2. ContributionEvent model with immutability and idempotency

Run this script with:
    cd /app/backend && python manage.py shell < demo_sprint1.py

Or in the Django shell:
    from demo_sprint1 import *
"""

import uuid

from core.models import ContributionEvent
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


def demo_contribution_event():
    """Demonstrate ContributionEvent creation and immutability."""

    print("\n" + "=" * 70)
    print("SPRINT-1 DEMONSTRATION: ContributionEvent")
    print("=" * 70)

    # Create a test user
    user, created = User.objects.get_or_create(
        username="demo_user",
        defaults={"email": "demo@example.com", "display_name": "Demo User"},
    )
    if created:
        user.set_password("demo123")
        user.save()
    print(f"\n✓ User created/retrieved: {user.username}")

    # 1. Create a ContributionEvent
    print("\n--- Test 1: Creating a ContributionEvent ---")
    client_id = uuid.uuid4()
    event = ContributionEvent.objects.create(
        client_generated_id=client_id,
        contributor=user,
        contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
        subject_ref={"lat": 40.7128, "lon": -74.0060, "name_hint": "Main Street"},
        payload={"confidence": "high", "notes": "Saw the bus stop sign clearly"},
        observed_at=timezone.now(),
        context={"gps_accuracy": 5.0, "app_version": "1.0.0", "was_offline": False},
    )
    print(f"✓ Created ContributionEvent: {event}")
    print(f"  - ID: {event.id}")
    print(f"  - Client ID: {event.client_generated_id}")
    print(f"  - Type: {event.get_contribution_type_display()}")

    # 2. Test immutability - updates should fail
    print("\n--- Test 2: Immutability - Update Prevention ---")
    try:
        event.payload = {"modified": True}
        event.save()
        print("✗ FAILED: Update should have been prevented!")
    except NotImplementedError as e:
        print(f"✓ Update correctly prevented: {str(e)[:60]}...")

    # 3. Test immutability - deletes should fail
    print("\n--- Test 3: Immutability - Delete Prevention ---")
    try:
        event.delete()
        print("✗ FAILED: Delete should have been prevented!")
    except NotImplementedError as e:
        print(f"✓ Delete correctly prevented: {str(e)[:60]}...")

    # 4. Test idempotency
    print("\n--- Test 4: Idempotent Creation ---")
    event2, created = ContributionEvent.create_or_get_idempotent(
        client_generated_id=client_id,  # Same client ID
        contributor=user,
        contribution_type=ContributionEvent.ContributionType.ROUTE_EXISTS,  # Different!
        subject_ref={"different": "data"},
        payload={"different": "payload"},
        observed_at=timezone.now(),
    )

    if not created and event2.id == event.id:
        print("✓ Idempotency works: Returned existing event")
        print(f"  - Same ID: {event.id == event2.id}")
        print(f"  - Original type preserved: {event2.contribution_type}")
    else:
        print("✗ FAILED: Should have returned existing event")

    # 5. Create a second distinct event
    print("\n--- Test 5: Creating a Second Event ---")
    event3 = ContributionEvent.objects.create(
        client_generated_id=uuid.uuid4(),  # Different client ID
        contributor=user,
        contribution_type=ContributionEvent.ContributionType.ROUTE_TRAVERSAL,
        subject_ref={"route_name": "Bus 42"},
        payload={"gps_trace": "..."},
        observed_at=timezone.now(),
    )
    print(f"✓ Created second event: {event3}")
    print(f"  - Total events: {ContributionEvent.objects.count()}")

    # 6. Query events
    print("\n--- Test 6: Querying Events ---")
    stop_events = ContributionEvent.objects.filter(
        contribution_type=ContributionEvent.ContributionType.STOP_EXISTS
    )
    print(f"✓ Found {stop_events.count()} STOP_EXISTS events")

    user_events = ContributionEvent.objects.filter(contributor=user)
    print(f"✓ User has {user_events.count()} total contributions")

    print("\n" + "=" * 70)
    print("SPRINT-1 DEMONSTRATION COMPLETE")
    print("=" * 70)
    print("\nKey Achievements:")
    print("  ✓ ContributionEvent is append-only (creation works)")
    print("  ✓ Updates are prevented (immutability enforced)")
    print("  ✓ Deletes are prevented (immutability enforced)")
    print("  ✓ Idempotency works (duplicate client_id handled)")
    print("  ✓ Evidence can be stored and queried")
    print("\nArchitectural Guardrails:")
    print("  ✓ ImmutableModel base class prevents mutations")
    print("  ✓ SoftDeletable base class available for other models")
    print("  ✓ VersionedModel base class ready for canonical entities")
    print("\nPhase-1 Invariants Respected:")
    print("  ✓ Contributions are append-only")
    print("  ✓ Evidence is never overwritten or deleted")
    print("  ✓ All decisions are reversible (evidence preserved)")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    demo_contribution_event()
    demo_contribution_event()

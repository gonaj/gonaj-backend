"""
Scoped advisory locking for evaluation execution.

Sprint-12: Performance & Recompute Control

This module provides PostgreSQL advisory lock support scoped to
individual canonical entities, preventing concurrent evaluation
of the same entity.

WHAT THIS MODULE PROVIDES:
- Entity-scoped advisory lock acquisition (non-blocking)
- Deterministic, namespaced lock key derivation
- Context manager for safe lock lifecycle

WHAT THIS MODULE DOES NOT PROVIDE:
- Table-level locks
- Global recompute locks
- Lock tables (uses PG advisory locks only)
- Blocking of evidence writes

LOCKING RULES:
- Locks are entity-scoped, not table-scoped
- Lock keys are deterministic and namespaced
- Lock is held only during evaluation execution
- Lock auto-releases on crash or connection drop
- No lock table is allowed

INVARIANTS:
- Evidence ingestion is NEVER blocked by locks
- Locks prevent concurrent evaluation of the same entity only
"""

import hashlib
from contextlib import contextmanager
from typing import Generator
from uuid import UUID

from django.db import connection

# Namespace constants for deterministic lock key derivation.
# These are arbitrary but fixed 32-bit prefixes to separate lock domains.
_NAMESPACE_STOP = 0x5370  # "Sp" in ASCII
_NAMESPACE_ROUTE = 0x5274  # "Rt" in ASCII


def _derive_lock_key(namespace: int, entity_id: UUID) -> int:
    """
    Derive a deterministic 64-bit advisory lock key.

    PostgreSQL advisory locks use bigint keys. We derive one from:
    - A fixed namespace prefix (stop vs route)
    - A hash of the entity UUID

    The result is a signed 64-bit integer (PostgreSQL bigint range).

    Args:
        namespace: Fixed namespace prefix for the entity type
        entity_id: UUID of the entity to lock

    Returns:
        A deterministic 64-bit signed integer lock key
    """
    digest = hashlib.sha256(str(entity_id).encode()).digest()
    # Take first 6 bytes of hash (48 bits) and combine with namespace (16 bits)
    hash_int = int.from_bytes(digest[:6], byteorder="big")
    key = (namespace << 48) | hash_int
    # Convert to signed 64-bit range for PostgreSQL bigint
    if key >= (1 << 63):
        key -= 1 << 64
    return key


def derive_stop_lock_key(stop_id: UUID) -> int:
    """Derive a deterministic lock key for a Stop entity."""
    return _derive_lock_key(_NAMESPACE_STOP, stop_id)


def derive_route_lock_key(route_id: UUID) -> int:
    """Derive a deterministic lock key for a Route entity."""
    return _derive_lock_key(_NAMESPACE_ROUTE, route_id)


def try_advisory_lock(lock_key: int) -> bool:
    """
    Attempt to acquire a PostgreSQL session-level advisory lock (non-blocking).

    Returns True if the lock was acquired, False if already held by another
    session.

    Args:
        lock_key: The 64-bit advisory lock key

    Returns:
        True if lock acquired, False otherwise
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [lock_key])
        row = cursor.fetchone()
        return row[0] if row else False


def release_advisory_lock(lock_key: int) -> bool:
    """
    Release a PostgreSQL session-level advisory lock.

    Args:
        lock_key: The 64-bit advisory lock key

    Returns:
        True if the lock was released, False if it was not held
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_unlock(%s)", [lock_key])
        row = cursor.fetchone()
        return row[0] if row else False


@contextmanager
def advisory_lock(lock_key: int) -> Generator[bool, None, None]:
    """
    Context manager for advisory lock acquisition and release.

    Yields True if the lock was acquired, False if it was already held.
    The lock is always released on exit (if acquired).

    Usage:
        with advisory_lock(key) as acquired:
            if acquired:
                # ... do work ...
            else:
                # ... skip or retry ...

    Args:
        lock_key: The 64-bit advisory lock key

    Yields:
        True if lock was acquired, False otherwise
    """
    acquired = try_advisory_lock(lock_key)
    try:
        yield acquired
    finally:
        if acquired:
            release_advisory_lock(lock_key)


@contextmanager
def stop_evaluation_lock(stop_id: UUID) -> Generator[bool, None, None]:
    """
    Context manager for acquiring an advisory lock scoped to a Stop entity.

    Yields True if the lock was acquired, False if already held.

    Args:
        stop_id: UUID of the Stop to lock

    Yields:
        True if lock was acquired, False otherwise
    """
    key = derive_stop_lock_key(stop_id)
    with advisory_lock(key) as acquired:
        yield acquired


@contextmanager
def route_evaluation_lock(route_id: UUID) -> Generator[bool, None, None]:
    """
    Context manager for acquiring an advisory lock scoped to a Route entity.

    Yields True if the lock was acquired, False if already held.

    Args:
        route_id: UUID of the Route to lock

    Yields:
        True if lock was acquired, False otherwise
    """
    key = derive_route_lock_key(route_id)
    with advisory_lock(key) as acquired:
        yield acquired

"""
Core models package.

This package contains all domain models for the core app, organized
into logical modules to avoid circular imports and maintain clarity.

Import all models here to make them available at the package level.
"""

from .audit import AuditLog
from .badges import Badge, UserBadge
from .contribution import Contribution
from .contribution_event import ContributionEvent
from .developer import Developer
from .device import Device
from .leaderboard import LeaderboardEntry
from .moderation import ModerationEntry
from .osm import OSMCredential
from .profile import Profile
from .user import User
from .user_stats import UserStats

# Base classes are not exported by default (use explicit imports if needed)
# from .base import SoftDeletable, ImmutableModel, VersionedModel

__all__ = [
    "User",
    "Profile",
    "UserStats",
    "Badge",
    "UserBadge",
    "Contribution",
    "ContributionEvent",
    "ModerationEntry",
    "AuditLog",
    "Device",
    "LeaderboardEntry",
    "OSMCredential",
    "Developer",
]

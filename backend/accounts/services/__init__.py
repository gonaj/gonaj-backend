"""
Account services package.

This package contains service classes for account-related operations
that don't fit into models or views.
"""

from .account_deletion import AccountDeletionService

__all__ = ["AccountDeletionService"]

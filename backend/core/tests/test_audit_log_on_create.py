"""
Tests for AuditLog model.

Verifies:
- Audit log entry creation via log() classmethod
- Actor attribution (user and developer)
- Object tracking
- Request context capture
"""

from django.test import TestCase

from core.models import AuditLog, Developer, User


class AuditLogTestCase(TestCase):
    """Test cases for the AuditLog model."""

    def setUp(self):
        """Create test user and developer for audit log tests."""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        self.developer = Developer.objects.create(
            name="Test Developer", contact_email="dev@example.com", verified=True
        )

    def test_create_audit_log_with_user(self):
        """Test creating an audit log entry with user actor."""
        log_entry = AuditLog.log(
            action="user.login",
            actor_user=self.user,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            detail={"method": "password"},
        )

        self.assertIsNotNone(log_entry.id)
        self.assertEqual(log_entry.action, "user.login")
        self.assertEqual(log_entry.actor_user, self.user)
        self.assertIsNone(log_entry.actor_developer)
        self.assertEqual(log_entry.ip_address, "192.168.1.1")
        self.assertEqual(log_entry.user_agent, "Mozilla/5.0")
        self.assertEqual(log_entry.detail["method"], "password")

    def test_create_audit_log_with_developer(self):
        """Test creating an audit log entry with developer actor."""
        log_entry = AuditLog.log(
            action="api.contribution.create",
            actor_developer=self.developer,
            object_type="Contribution",
            object_id="abc-123-def-456",
            detail={"api_version": "v1"},
        )

        self.assertEqual(log_entry.action, "api.contribution.create")
        self.assertIsNone(log_entry.actor_user)
        self.assertEqual(log_entry.actor_developer, self.developer)
        self.assertEqual(log_entry.object_type, "Contribution")
        self.assertEqual(log_entry.object_id, "abc-123-def-456")

    def test_create_audit_log_with_object_tracking(self):
        """Test audit log with object type and ID tracking."""
        contribution_id = "contribution-uuid-here"

        log_entry = AuditLog.log(
            action="contribution.update",
            actor_user=self.user,
            object_type="Contribution",
            object_id=contribution_id,
            detail={"field": "status", "old": "pending", "new": "approved"},
        )

        self.assertEqual(log_entry.object_type, "Contribution")
        self.assertEqual(log_entry.object_id, contribution_id)
        self.assertEqual(log_entry.detail["field"], "status")

    def test_create_audit_log_minimal(self):
        """Test creating audit log with minimal fields."""
        log_entry = AuditLog.log(action="system.startup")

        self.assertEqual(log_entry.action, "system.startup")
        self.assertIsNone(log_entry.actor_user)
        self.assertIsNone(log_entry.actor_developer)
        self.assertEqual(log_entry.detail, {})

    def test_audit_log_str_representation(self):
        """Test string representation of audit log entry."""
        log_entry = AuditLog.log(action="user.logout", actor_user=self.user)

        str_repr = str(log_entry)
        self.assertIn("testuser", str_repr)
        self.assertIn("user.logout", str_repr)

    def test_audit_log_ordering(self):
        """Test that audit logs are ordered by creation time descending."""
        # Create multiple log entries
        log1 = AuditLog.log(action="action.one", actor_user=self.user)
        log2 = AuditLog.log(action="action.two", actor_user=self.user)
        log3 = AuditLog.log(action="action.three", actor_user=self.user)

        # Query all logs
        logs = AuditLog.objects.all()

        # Should be in reverse chronological order
        self.assertEqual(logs[0].id, log3.id)
        self.assertEqual(logs[1].id, log2.id)
        self.assertEqual(logs[2].id, log1.id)

    def test_audit_log_with_ipv6(self):
        """Test audit log with IPv6 address."""
        log_entry = AuditLog.log(
            action="user.login",
            actor_user=self.user,
            ip_address="2001:0db8:85a3:0000:0000:8a2e:0370:7334",
        )

        self.assertEqual(
            log_entry.ip_address, "2001:0db8:85a3:0000:0000:8a2e:0370:7334"
        )

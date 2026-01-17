"""
Tests for Canonical Read Guardrails (Phase-2 Sprint-2A).

CRITICAL CONTEXT:
As of Phase-2 Sprint-2A, NO canonical read endpoints exist yet.
These tests validate the GUARDRAILS that future canonical endpoints must follow.

These are FUTURE-FACING tests that ensure:
- Permission patterns reject unsafe methods
- Serializer contracts prevent field leakage
- Pagination bounds are enforced
- Malformed parameters are rejected

Tests use dummy views and serializers created ONLY for testing purposes.
"""

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import serializers

from api.permissions import ReadOnlyPublic, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from api.serializers.canonical import (
    CanonicalReadSerializerBase,
    CANONICAL_BLOCKED_FIELDS,
    CanonicalReadPaginationMixin,
)


User = get_user_model()


class CanonicalReadPermissionTests(TestCase):
    """
    Test that ReadOnlyPublic permission enforces read-only canonical access.
    
    FUTURE-FACING: These tests ensure the permission pattern is correct
    before any canonical endpoints are implemented.
    """
    
    def setUp(self):
        self.factory = RequestFactory()
        self.permission = ReadOnlyPublic()
        
        # Dummy view for testing (not exposed via URL)
        class DummyCanonicalView(APIView):
            permission_classes = [ReadOnlyPublic]
            
            def get(self, request):
                return Response({"status": "ok"})
        
        self.view = DummyCanonicalView.as_view()
    
    def test_get_allowed_anonymous(self):
        """Verify GET requests allowed for anonymous users."""
        request = self.factory.get('/dummy')
        self.assertTrue(
            self.permission.has_permission(request, None),
            "GET should be allowed for anonymous users"
        )
    
    def test_head_allowed_anonymous(self):
        """Verify HEAD requests allowed for anonymous users."""
        request = self.factory.head('/dummy')
        self.assertTrue(
            self.permission.has_permission(request, None),
            "HEAD should be allowed for anonymous users"
        )
    
    def test_options_allowed_anonymous(self):
        """Verify OPTIONS requests allowed (CORS preflight)."""
        request = self.factory.options('/dummy')
        self.assertTrue(
            self.permission.has_permission(request, None),
            "OPTIONS should be allowed for CORS"
        )
    
    def test_post_denied(self):
        """Verify POST requests denied."""
        request = self.factory.post('/dummy', {})
        self.assertFalse(
            self.permission.has_permission(request, None),
            "POST must be denied on canonical read endpoints"
        )
    
    def test_put_denied(self):
        """Verify PUT requests denied."""
        request = self.factory.put('/dummy', {})
        self.assertFalse(
            self.permission.has_permission(request, None),
            "PUT must be denied on canonical read endpoints"
        )
    
    def test_patch_denied(self):
        """Verify PATCH requests denied."""
        request = self.factory.patch('/dummy', {})
        self.assertFalse(
            self.permission.has_permission(request, None),
            "PATCH must be denied on canonical read endpoints"
        )
    
    def test_delete_denied(self):
        """Verify DELETE requests denied."""
        request = self.factory.delete('/dummy')
        self.assertFalse(
            self.permission.has_permission(request, None),
            "DELETE must be denied on canonical read endpoints"
        )
    
    def test_authenticated_user_same_rules(self):
        """Verify authenticated users follow same rules (no special access)."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # GET still allowed
        request = self.factory.get('/dummy')
        request.user = user
        self.assertTrue(
            self.permission.has_permission(request, None),
            "GET allowed for authenticated users"
        )
        
        # POST still denied
        request = self.factory.post('/dummy', {})
        request.user = user
        self.assertFalse(
            self.permission.has_permission(request, None),
            "POST denied even for authenticated users"
        )


class CanonicalSerializerContractTests(TestCase):
    """
    Test that CanonicalReadSerializerBase enforces the mandatory contract.
    
    FUTURE-FACING: These tests ensure serializer guardrails work before
    any canonical serializers are implemented.
    """
    
    def test_blocked_fields_defined(self):
        """Verify CANONICAL_BLOCKED_FIELDS contains critical exclusions."""
        required_blocks = {
            'contributor', 'contributor_id', 'contributor_fingerprint',
            'id', 'uuid', 'evidence_count', 'created_at'
        }
        
        self.assertTrue(
            required_blocks.issubset(CANONICAL_BLOCKED_FIELDS),
            f"CANONICAL_BLOCKED_FIELDS missing required blocks: "
            f"{required_blocks - CANONICAL_BLOCKED_FIELDS}"
        )
    
    def test_compliant_serializer_allowed(self):
        """Verify compliant serializer with allowed_fields works correctly."""
        
        class CompliantSerializer(CanonicalReadSerializerBase):
            name = serializers.CharField()
            location = serializers.JSONField()
            
            class Meta:
                allowed_fields = {'name', 'location'}
        
        # Should initialize without error
        serializer = CompliantSerializer()
        self.assertIn('name', serializer.fields)
        self.assertIn('location', serializer.fields)
    
    def test_missing_allowed_fields_raises_error(self):
        """Verify serializer without allowed_fields raises ValueError."""
        
        class NonCompliantSerializer(CanonicalReadSerializerBase):
            name = serializers.CharField()
            
            # Missing Meta.allowed_fields
        
        with self.assertRaises(ValueError) as cm:
            NonCompliantSerializer()
        
        self.assertIn('allowed_fields', str(cm.exception))
    
    def test_undeclared_field_raises_error(self):
        """Verify fields not in allowed_fields raise ValueError."""
        
        class UndeclaredFieldSerializer(CanonicalReadSerializerBase):
            name = serializers.CharField()
            secret = serializers.CharField()
            
            class Meta:
                allowed_fields = {'name'}  # 'secret' not whitelisted
        
        with self.assertRaises(ValueError) as cm:
            UndeclaredFieldSerializer()
        
        self.assertIn('secret', str(cm.exception))
    
    def test_blocked_field_removed_in_debug(self):
        """Verify blocked fields raise AssertionError in DEBUG mode."""
        from django.conf import settings
        
        # Force DEBUG mode for this test
        original_debug = settings.DEBUG
        settings.DEBUG = True
        
        try:
            class LeakySerializer(CanonicalReadSerializerBase):
                name = serializers.CharField()
                contributor_id = serializers.IntegerField()
                
                class Meta:
                    allowed_fields = {'name', 'contributor_id'}
            
            # Initialize should work (validation happens at instantiation)
            serializer = LeakySerializer()
            
            # But to_representation should fail in DEBUG
            test_obj = type('obj', (), {'name': 'Test', 'contributor_id': 123})()
            
            with self.assertRaises(AssertionError) as cm:
                serializer.to_representation(test_obj)
            
            self.assertIn('contributor_id', str(cm.exception))
            self.assertIn('leaked', str(cm.exception).lower())
        
        finally:
            settings.DEBUG = original_debug
    
    def test_blocked_field_sanitized_in_production(self):
        """Verify blocked fields silently removed in production mode."""
        from django.conf import settings
        
        # Force production mode for this test
        original_debug = settings.DEBUG
        settings.DEBUG = False
        
        try:
            class LeakySerializer(CanonicalReadSerializerBase):
                name = serializers.CharField()
                contributor_id = serializers.IntegerField()
                
                class Meta:
                    allowed_fields = {'name', 'contributor_id'}
            
            serializer = LeakySerializer()
            
            # Create test object
            test_obj = type('obj', (), {'name': 'Test', 'contributor_id': 123})()
            
            # Should not raise, but sanitize output
            result = serializer.to_representation(test_obj)
            
            self.assertIn('name', result)
            self.assertNotIn('contributor_id', result,
                           "Blocked field should be removed in production")
        
        finally:
            settings.DEBUG = original_debug


class CanonicalPaginationGuardTests(TestCase):
    """
    Test pagination bounding utilities for canonical read endpoints.
    
    FUTURE-FACING: These tests ensure pagination works before any
    canonical list endpoints are implemented.
    """
    
    def setUp(self):
        self.factory = RequestFactory()
        
        # Dummy view using pagination mixin (not exposed via URL)
        class DummyPaginatedView(CanonicalReadPaginationMixin, APIView):
            def get(self, request):
                try:
                    page_size = self.get_page_size(request)
                    return Response({"page_size": page_size})
                except ValueError as e:
                    return Response({"error": str(e)}, status=400)
        
        self.view = DummyPaginatedView()
    
    def test_default_page_size(self):
        """Verify default page size used when not specified."""
        request = self.factory.get('/dummy')
        page_size = self.view.get_page_size(request)
        self.assertEqual(page_size, DEFAULT_PAGE_SIZE)
    
    def test_custom_page_size(self):
        """Verify custom page size accepted within bounds."""
        request = self.factory.get('/dummy?page_size=10')
        page_size = self.view.get_page_size(request)
        self.assertEqual(page_size, 10)
    
    def test_max_page_size_enforced(self):
        """Verify page size exceeding MAX_PAGE_SIZE rejected."""
        request = self.factory.get(f'/dummy?page_size={MAX_PAGE_SIZE + 1}')
        
        with self.assertRaises(ValueError) as cm:
            self.view.get_page_size(request)
        
        self.assertIn('exceeds maximum', str(cm.exception))
        self.assertIn(str(MAX_PAGE_SIZE), str(cm.exception))
    
    def test_negative_page_size_rejected(self):
        """Verify negative page size rejected."""
        request = self.factory.get('/dummy?page_size=-5')
        
        with self.assertRaises(ValueError) as cm:
            self.view.get_page_size(request)
        
        self.assertIn('at least 1', str(cm.exception))
    
    def test_zero_page_size_rejected(self):
        """Verify zero page size rejected."""
        request = self.factory.get('/dummy?page_size=0')
        
        with self.assertRaises(ValueError) as cm:
            self.view.get_page_size(request)
        
        self.assertIn('at least 1', str(cm.exception))
    
    def test_malformed_page_size_rejected(self):
        """Verify non-integer page size rejected."""
        request = self.factory.get('/dummy?page_size=abc')
        
        with self.assertRaises(ValueError) as cm:
            self.view.get_page_size(request)
        
        self.assertIn('integer', str(cm.exception).lower())
    
    def test_float_page_size_rejected(self):
        """Verify float page size rejected."""
        request = self.factory.get('/dummy?page_size=10.5')
        
        # Float strings should be rejected as invalid integers
        with self.assertRaises(ValueError) as cm:
            self.view.get_page_size(request)
        
        self.assertIn('integer', str(cm.exception).lower())


class CanonicalReadInvariantTests(TestCase):
    """
    Test that canonical read guardrails enforce critical invariants.
    
    FUTURE-FACING: These tests document invariants that must hold
    for all canonical read endpoints.
    """
    
    def setUp(self):
        self.factory = RequestFactory()
    
    def test_no_evidence_data_exposure(self):
        """Verify evidence-related fields are in blocked list."""
        evidence_fields = {
            'evidence_count', 'evidence', 'confidence',
            'quality_score', 'reliability'
        }
        
        self.assertTrue(
            evidence_fields.issubset(CANONICAL_BLOCKED_FIELDS),
            "Evidence fields must be blocked in canonical serializers"
        )
    
    def test_no_contributor_identity_exposure(self):
        """Verify contributor identity fields are in blocked list."""
        identity_fields = {
            'contributor', 'contributor_id', 'contributor_fingerprint',
            'user', 'user_id', 'device_id'
        }
        
        self.assertTrue(
            identity_fields.issubset(CANONICAL_BLOCKED_FIELDS),
            "Contributor identity must be blocked in canonical serializers"
        )
    
    def test_no_internal_ids_exposure(self):
        """Verify internal identifier fields are in blocked list."""
        id_fields = {
            'id', 'uuid', 'internal_id', 'server_id',
            'client_generated_id'
        }
        
        self.assertTrue(
            id_fields.issubset(CANONICAL_BLOCKED_FIELDS),
            "Internal IDs must be blocked in canonical serializers"
        )
    
    def test_no_timing_pattern_exposure(self):
        """Verify contribution timing fields are in blocked list."""
        timing_fields = {
            'created_at', 'updated_at', 'last_modified',
            'submitted_at', 'first_seen', 'last_seen'
        }
        
        self.assertTrue(
            timing_fields.issubset(CANONICAL_BLOCKED_FIELDS),
            "Timing patterns must be blocked in canonical serializers"
        )
    
    def test_pagination_constants_defined(self):
        """Verify pagination constants exist and are reasonable."""
        self.assertIsInstance(DEFAULT_PAGE_SIZE, int)
        self.assertIsInstance(MAX_PAGE_SIZE, int)
        self.assertGreater(DEFAULT_PAGE_SIZE, 0)
        self.assertGreater(MAX_PAGE_SIZE, DEFAULT_PAGE_SIZE)
        self.assertLessEqual(MAX_PAGE_SIZE, 1000,
                            "MAX_PAGE_SIZE should prevent scraping")
    
    def test_readonly_public_denies_all_mutations(self):
        """Verify ReadOnlyPublic denies all unsafe methods."""
        unsafe_methods = ['POST', 'PUT', 'PATCH', 'DELETE']
        permission = ReadOnlyPublic()
        
        for method in unsafe_methods:
            request = self.factory.generic(method, '/dummy')
            self.assertFalse(
                permission.has_permission(request, None),
                f"{method} must be denied by ReadOnlyPublic"
            )

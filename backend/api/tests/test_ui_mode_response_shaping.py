"""
Tests for UI Mode-Aware Response Shaping (Phase-2 Sprint-3).

This test module validates that UI modes affect visibility only, never truth.

TESTED INVARIANTS:
1. Visibility-Only Invariant: Same request, same data, different modes -> only fields differ
2. Truth Invariance: Evaluation results unchanged regardless of mode
3. Non-Canonical Safety: No evidence promoted due to mode
4. Reversibility: Switching modes does not permanently remove data
5. Default Safety: Missing or invalid mode behaves as 'read'
6. Contributor Threshold Secrecy: Contributor mode never exposes thresholds

PHILOSOPHY:
UI modes control WHAT IS SHOWN, never WHAT IS TRUE.
These tests prove that UI mode changes are purely presentational.
"""

from copy import deepcopy
from django.test import TestCase, RequestFactory
from api.visibility import (
    parse_ui_mode,
    get_visible_fields,
    apply_visibility,
    validate_contributor_mode_safety,
    UI_MODE_READ,
    UI_MODE_CONTRIBUTOR,
    UI_MODE_ADMIN,
    DEFAULT_UI_MODE,
    CANONICAL_SAFE_FIELDS,
    CONTRIBUTOR_VISIBLE_FIELDS,
    ADMIN_VISIBLE_FIELDS,
    ALWAYS_BLOCKED_FIELDS,
    THRESHOLD_RELATED_FIELDS,
)


class UIModeParsingTests(TestCase):
    """Test UI mode parsing from requests."""
    
    def setUp(self):
        self.factory = RequestFactory()
    
    def test_parse_mode_from_query_parameter(self):
        """UI mode can be provided via query parameter."""
        request = self.factory.get("/api/test?ui_mode=contributor")
        mode = parse_ui_mode(request)
        self.assertEqual(mode, UI_MODE_CONTRIBUTOR)
    
    def test_parse_mode_from_header(self):
        """UI mode can be provided via HTTP header."""
        request = self.factory.get("/api/test", HTTP_X_UI_MODE="admin")
        mode = parse_ui_mode(request)
        self.assertEqual(mode, UI_MODE_ADMIN)
    
    def test_query_parameter_takes_precedence_over_header(self):
        """Query parameter takes precedence when both are present."""
        request = self.factory.get(
            "/api/test?ui_mode=contributor",
            HTTP_X_UI_MODE="admin"
        )
        mode = parse_ui_mode(request)
        self.assertEqual(mode, UI_MODE_CONTRIBUTOR)
    
    def test_invalid_mode_defaults_to_read(self):
        """Invalid mode values default to 'read' for safety."""
        request = self.factory.get("/api/test?ui_mode=invalid")
        mode = parse_ui_mode(request)
        self.assertEqual(mode, UI_MODE_READ)
    
    def test_missing_mode_defaults_to_read(self):
        """Missing mode defaults to 'read' for safety."""
        request = self.factory.get("/api/test")
        mode = parse_ui_mode(request)
        self.assertEqual(mode, UI_MODE_READ)
    
    def test_mode_is_case_insensitive(self):
        """Mode parsing is case-insensitive."""
        request = self.factory.get("/api/test?ui_mode=CONTRIBUTOR")
        mode = parse_ui_mode(request)
        self.assertEqual(mode, UI_MODE_CONTRIBUTOR)
    
    def test_mode_whitespace_is_stripped(self):
        """Whitespace in mode values is stripped."""
        request = self.factory.get("/api/test?ui_mode= admin ")
        mode = parse_ui_mode(request)
        self.assertEqual(mode, UI_MODE_ADMIN)


class VisibilityRulesTests(TestCase):
    """Test visibility rule definitions for each UI mode."""
    
    def test_read_mode_shows_only_canonical_safe_fields(self):
        """Read mode shows only canonical-safe fields."""
        visible = get_visible_fields(UI_MODE_READ)
        self.assertEqual(visible, CANONICAL_SAFE_FIELDS)
    
    def test_contributor_mode_adds_candidate_metadata(self):
        """Contributor mode includes canonical + candidate metadata."""
        visible = get_visible_fields(UI_MODE_CONTRIBUTOR)
        expected = CANONICAL_SAFE_FIELDS | CONTRIBUTOR_VISIBLE_FIELDS
        self.assertEqual(visible, expected)
    
    def test_admin_mode_adds_diagnostics(self):
        """Admin mode includes canonical + candidate + diagnostics."""
        visible = get_visible_fields(UI_MODE_ADMIN)
        expected = (
            CANONICAL_SAFE_FIELDS 
            | CONTRIBUTOR_VISIBLE_FIELDS 
            | ADMIN_VISIBLE_FIELDS
        )
        self.assertEqual(visible, expected)
    
    def test_visibility_rules_are_hierarchical(self):
        """Each mode is a superset of the previous mode."""
        read_fields = get_visible_fields(UI_MODE_READ)
        contributor_fields = get_visible_fields(UI_MODE_CONTRIBUTOR)
        admin_fields = get_visible_fields(UI_MODE_ADMIN)
        
        # Contributor includes all of read
        self.assertTrue(read_fields.issubset(contributor_fields))
        
        # Admin includes all of contributor
        self.assertTrue(contributor_fields.issubset(admin_fields))
    
    def test_always_blocked_fields_never_visible(self):
        """Always-blocked fields never appear in any mode."""
        for mode in [UI_MODE_READ, UI_MODE_CONTRIBUTOR, UI_MODE_ADMIN]:
            visible = get_visible_fields(mode)
            # No intersection between visible and blocked
            self.assertEqual(
                visible & ALWAYS_BLOCKED_FIELDS, 
                set(),
                f"Mode {mode} exposes blocked fields"
            )


class VisibilityFilteringTests(TestCase):
    """Test visibility filtering application."""
    
    def setUp(self):
        # Sample response data with fields for all modes
        self.sample_data = {
            # Canonical-safe fields (visible in all modes)
            "name": "Main Street Stop",
            "location": {"lat": 40.7128, "lon": -74.0060},
            "belief_state": "Active (High Confidence)",
            
            # Contributor-visible fields
            "candidate_status": "under_review",
            "last_observed_date": "2026-01-15",
            "observation_count_category": "many",
            
            # Admin-visible fields
            "confidence_score": 0.95,
            "evidence_count": 42,
            "evaluation_version": "v0",
            "created_at": "2025-12-01T00:00:00Z",
            "diagnostic": {"reason": "high_confidence"},
            
            # Always-blocked fields (never visible)
            "contributor": "user123",
            "contributor_fingerprint": "abc123",
            "device_id": "device456",
        }
    
    def test_read_mode_filters_to_canonical_safe_only(self):
        """Read mode shows only canonical-safe fields."""
        filtered = apply_visibility(self.sample_data, UI_MODE_READ)
        
        # Should include canonical-safe fields
        self.assertIn("name", filtered)
        self.assertIn("location", filtered)
        self.assertIn("belief_state", filtered)
        
        # Should NOT include contributor or admin fields
        self.assertNotIn("candidate_status", filtered)
        self.assertNotIn("confidence_score", filtered)
        
        # Should NEVER include blocked fields
        self.assertNotIn("contributor", filtered)
        self.assertNotIn("contributor_fingerprint", filtered)
    
    def test_contributor_mode_shows_candidate_metadata(self):
        """Contributor mode shows canonical + candidate metadata."""
        filtered = apply_visibility(self.sample_data, UI_MODE_CONTRIBUTOR)
        
        # Should include canonical-safe fields
        self.assertIn("name", filtered)
        self.assertIn("belief_state", filtered)
        
        # Should include contributor-visible fields
        self.assertIn("candidate_status", filtered)
        self.assertIn("last_observed_date", filtered)
        
        # Should NOT include admin fields
        self.assertNotIn("confidence_score", filtered)
        self.assertNotIn("evidence_count", filtered)
        
        # Should NEVER include blocked fields
        self.assertNotIn("contributor", filtered)
    
    def test_admin_mode_shows_diagnostics(self):
        """Admin mode shows canonical + candidate + diagnostics."""
        filtered = apply_visibility(self.sample_data, UI_MODE_ADMIN)
        
        # Should include all non-blocked fields
        self.assertIn("name", filtered)
        self.assertIn("candidate_status", filtered)
        self.assertIn("confidence_score", filtered)
        self.assertIn("diagnostic", filtered)
        
        # Should NEVER include blocked fields
        self.assertNotIn("contributor", filtered)
        self.assertNotIn("device_id", filtered)
    
    def test_filtering_handles_list_of_objects(self):
        """Filtering works with lists of objects."""
        data_list = [
            {"name": "Stop A", "contributor": "user1"},
            {"name": "Stop B", "confidence_score": 0.8},
        ]
        
        filtered = apply_visibility(data_list, UI_MODE_READ)
        
        # Should be a list of same length
        self.assertEqual(len(filtered), 2)
        
        # First item should have name but not contributor
        self.assertIn("name", filtered[0])
        self.assertNotIn("contributor", filtered[0])
        
        # Second item should have name but not confidence_score (admin field)
        self.assertIn("name", filtered[1])
        self.assertNotIn("confidence_score", filtered[1])
    
    def test_filtering_handles_nested_objects(self):
        """Filtering works with nested objects."""
        data = {
            "name": "Stop A",
            "metadata": {
                "description": "A stop",
                "confidence_score": 0.9,
            }
        }
        
        filtered = apply_visibility(data, UI_MODE_READ)
        
        # Top-level name should be present
        self.assertIn("name", filtered)
        
        # Nested description should be present if it's a canonical field
        # But confidence_score should be filtered out
        if "metadata" in filtered:
            self.assertNotIn("confidence_score", filtered["metadata"])
    
    def test_filtering_does_not_mutate_source_data(self):
        """Filtering creates a copy, does not mutate source."""
        original_data = deepcopy(self.sample_data)  # True deep copy

        # Apply filtering
        filtered = apply_visibility(self.sample_data, UI_MODE_READ)
        
        # Original data should be unchanged
        self.assertEqual(self.sample_data, original_data)
        
        # Filtered data should be different
        self.assertNotEqual(filtered, self.sample_data)


class VisibilityOnlyInvariantTests(TestCase):
    """Test that UI mode affects visibility only, not truth."""
    
    def setUp(self):
        self.underlying_data = {
            "name": "Test Stop",
            "location": {"lat": 40.0, "lon": -74.0},
            "confidence_score": 0.95,
            "evidence_count": 50,
        }
    
    def test_same_data_different_modes_only_fields_differ(self):
        """Same underlying data, different modes -> only visible fields differ."""
        read_view = apply_visibility(self.underlying_data, UI_MODE_READ)
        admin_view = apply_visibility(self.underlying_data, UI_MODE_ADMIN)
        
        # Both should have canonical-safe fields with same values
        self.assertEqual(read_view["name"], admin_view["name"])
        self.assertEqual(read_view["location"], admin_view["location"])
        
        # Admin view should have additional fields
        self.assertIn("confidence_score", admin_view)
        self.assertNotIn("confidence_score", read_view)
    
    def test_switching_modes_is_reversible(self):
        """Switching modes does not permanently remove data."""
        # Filter to read mode
        read_view = apply_visibility(self.underlying_data, UI_MODE_READ)
        
        # Filter to admin mode
        admin_view = apply_visibility(self.underlying_data, UI_MODE_ADMIN)
        
        # Switching back to read mode should produce same result
        read_view_2 = apply_visibility(self.underlying_data, UI_MODE_READ)
        
        self.assertEqual(read_view, read_view_2)
    
    def test_filtering_is_idempotent(self):
        """Filtering multiple times produces same result."""
        filtered_once = apply_visibility(self.underlying_data, UI_MODE_READ)
        
        # Note: We apply filtering to the original data again, not the filtered result
        # This tests that the underlying data remains unchanged
        filtered_twice = apply_visibility(self.underlying_data, UI_MODE_READ)
        
        self.assertEqual(filtered_once, filtered_twice)


class DefaultSafetyTests(TestCase):
    """Test that invalid or missing modes fail safely."""
    
    def test_invalid_mode_behaves_as_read(self):
        """Invalid mode values behave as 'read' mode."""
        data = {
            "name": "Stop",
            "confidence_score": 0.9,
        }
        
        filtered = apply_visibility(data, "invalid_mode")
        
        # Should behave like read mode
        self.assertIn("name", filtered)
        self.assertNotIn("confidence_score", filtered)
    
    def test_none_mode_behaves_as_read(self):
        """None mode behaves as 'read' mode."""
        data = {
            "name": "Stop",
            "confidence_score": 0.9,
        }
        
        filtered = apply_visibility(data, None)
        
        # Should behave like read mode
        self.assertIn("name", filtered)
        self.assertNotIn("confidence_score", filtered)
    
    def test_empty_string_mode_behaves_as_read(self):
        """Empty string mode behaves as 'read' mode."""
        data = {
            "name": "Stop",
            "confidence_score": 0.9,
        }
        
        filtered = apply_visibility(data, "")
        
        # Should behave like read mode
        self.assertIn("name", filtered)
        self.assertNotIn("confidence_score", filtered)


class ContributorThresholdSecrecyTests(TestCase):
    """Test that contributor mode never exposes threshold-related fields."""
    
    def test_contributor_mode_blocks_confidence_scores(self):
        """Contributor mode blocks confidence scores."""
        data = {
            "name": "Stop",
            "confidence_score": 0.95,
            "candidate_status": "under_review",
        }
        
        filtered = apply_visibility(data, UI_MODE_CONTRIBUTOR)
        
        # Should have candidate metadata
        self.assertIn("candidate_status", filtered)
        
        # Should NOT have confidence score
        self.assertNotIn("confidence_score", filtered)
    
    def test_contributor_mode_blocks_numeric_thresholds(self):
        """Contributor mode blocks all threshold-related numeric fields."""
        threshold_data = {
            "name": "Stop",
            "confidence": 0.8,
            "quality_score": 0.9,
            "threshold_distance": 0.1,
            "required_count": 5,
            "current_count": 3,
        }
        
        filtered = apply_visibility(threshold_data, UI_MODE_CONTRIBUTOR)
        
        # Should only have canonical-safe fields
        self.assertIn("name", filtered)
        
        # Should NOT have any threshold-related fields
        for field in THRESHOLD_RELATED_FIELDS:
            self.assertNotIn(field, filtered)
    
    def test_validate_contributor_mode_safety_passes_for_safe_data(self):
        """Validation passes when contributor data is safe."""
        safe_data = {
            "name": "Stop",
            "candidate_status": "under_review",
            "observation_count_category": "many",
        }
        
        # Should not raise
        self.assertTrue(validate_contributor_mode_safety(safe_data))
    
    def test_validate_contributor_mode_safety_fails_for_threshold_fields(self):
        """Validation fails when threshold-related fields are present."""
        unsafe_data = {
            "name": "Stop",
            "confidence_score": 0.95,  # Threshold-related field
        }
        
        # Should raise AssertionError
        with self.assertRaises(AssertionError) as context:
            validate_contributor_mode_safety(unsafe_data)
        
        self.assertIn("confidence_score", str(context.exception))
        self.assertIn("Contributor Threshold Secrecy", str(context.exception))
    
    def test_contributor_visible_fields_are_categorical_only(self):
        """Contributor-visible fields provide categorical data, not numeric."""
        # This is a design test: verify that CONTRIBUTOR_VISIBLE_FIELDS
        # contains only categorical/boolean/coarse-grained fields
        
        # None of the contributor-visible fields should be in threshold-related fields
        intersection = CONTRIBUTOR_VISIBLE_FIELDS & THRESHOLD_RELATED_FIELDS
        self.assertEqual(
            intersection,
            set(),
            f"Contributor-visible fields overlap with threshold fields: {intersection}"
        )


class TruthInvarianceTests(TestCase):
    """Test that UI mode does not affect truth or evaluation."""
    
    def test_mode_does_not_affect_underlying_data_structure(self):
        """UI mode does not change the structure of underlying data."""
        data = {
            "name": "Stop",
            "confidence_score": 0.95,
            "evidence_count": 50,
        }
        
        original_keys = set(data.keys())
        
        # Apply filtering in various modes
        apply_visibility(data, UI_MODE_READ)
        apply_visibility(data, UI_MODE_CONTRIBUTOR)
        apply_visibility(data, UI_MODE_ADMIN)
        
        # Original data structure should be unchanged
        self.assertEqual(set(data.keys()), original_keys)
    
    def test_mode_does_not_affect_data_values(self):
        """UI mode does not change the values of underlying data."""
        data = {
            "name": "Stop",
            "location": {"lat": 40.0, "lon": -74.0},
        }
        
        original_name = data["name"]
        original_location = data["location"].copy()
        
        # Apply filtering
        apply_visibility(data, UI_MODE_READ)
        
        # Values should be unchanged
        self.assertEqual(data["name"], original_name)
        self.assertEqual(data["location"], original_location)


class NonCanonicalSafetyTests(TestCase):
    """Test that UI mode does not promote evidence to canonical status."""
    
    def test_mode_does_not_create_new_fields(self):
        """UI mode filtering does not create new fields in response."""
        data = {"name": "Stop"}
        
        filtered = apply_visibility(data, UI_MODE_ADMIN)
        
        # Filtered data should only contain fields from original data
        # (or a subset), never new fields
        for key in filtered.keys():
            self.assertIn(key, data.keys())
    
    def test_mode_does_not_transform_field_semantics(self):
        """UI mode does not transform the meaning of fields."""
        data = {
            "name": "Main St",
            "belief_state": "Active (Low Confidence)",
        }
        
        filtered = apply_visibility(data, UI_MODE_READ)
        
        # If belief_state is visible, it should have the same value
        if "belief_state" in filtered:
            self.assertEqual(filtered["belief_state"], data["belief_state"])
    
    def test_always_blocked_fields_never_appear_in_any_mode(self):
        """Always-blocked fields never appear, even in admin mode."""
        data = {
            "name": "Stop",
            "contributor": "user123",
            "contributor_fingerprint": "abc123",
            "device_id": "device456",
            "user_id": "user789",
        }
        
        # Even admin mode should block these
        admin_filtered = apply_visibility(data, UI_MODE_ADMIN)
        
        for blocked_field in ALWAYS_BLOCKED_FIELDS:
            self.assertNotIn(
                blocked_field, 
                admin_filtered,
                f"Blocked field {blocked_field} appeared in admin mode"
            )


class IntegrationTests(TestCase):
    """Integration tests combining request parsing and filtering."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.sample_data = {
            "name": "Test Stop",
            "location": {"lat": 40.0, "lon": -74.0},
            "candidate_status": "under_review",
            "confidence_score": 0.95,
            "contributor": "user123",
        }
    
    def test_end_to_end_read_mode(self):
        """End-to-end test: request -> mode parsing -> filtering (read mode)."""
        request = self.factory.get("/api/stops?ui_mode=read")
        mode = parse_ui_mode(request)
        filtered = apply_visibility(self.sample_data, mode)
        
        # Should have canonical-safe fields only
        self.assertIn("name", filtered)
        self.assertIn("location", filtered)
        self.assertNotIn("candidate_status", filtered)
        self.assertNotIn("confidence_score", filtered)
        self.assertNotIn("contributor", filtered)
    
    def test_end_to_end_contributor_mode(self):
        """End-to-end test: request -> mode parsing -> filtering (contributor mode)."""
        request = self.factory.get("/api/stops", HTTP_X_UI_MODE="contributor")
        mode = parse_ui_mode(request)
        filtered = apply_visibility(self.sample_data, mode)
        
        # Should have canonical + candidate metadata
        self.assertIn("name", filtered)
        self.assertIn("candidate_status", filtered)
        self.assertNotIn("confidence_score", filtered)  # Admin field
        self.assertNotIn("contributor", filtered)  # Always blocked
    
    def test_end_to_end_admin_mode(self):
        """End-to-end test: request -> mode parsing -> filtering (admin mode)."""
        request = self.factory.get("/api/stops?ui_mode=admin")
        mode = parse_ui_mode(request)
        filtered = apply_visibility(self.sample_data, mode)
        
        # Should have canonical + candidate + diagnostics
        self.assertIn("name", filtered)
        self.assertIn("candidate_status", filtered)
        self.assertIn("confidence_score", filtered)
        self.assertNotIn("contributor", filtered)  # Always blocked
    
    def test_end_to_end_invalid_mode_defaults_safely(self):
        """End-to-end test: invalid mode -> defaults to read."""
        request = self.factory.get("/api/stops?ui_mode=hacker_mode")
        mode = parse_ui_mode(request)
        filtered = apply_visibility(self.sample_data, mode)
        
        # Should behave like read mode
        self.assertIn("name", filtered)
        self.assertNotIn("confidence_score", filtered)
        self.assertNotIn("contributor", filtered)

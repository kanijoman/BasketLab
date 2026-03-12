"""Tests for src.database.utils — get_collection_name and safe_divide."""

import pytest
from src.database.utils import get_collection_name, safe_divide, _sanitize_component


# ---------------------------------------------------------------------------
# _sanitize_component (internal helper)
# ---------------------------------------------------------------------------

class TestSanitizeComponent:
    def test_strips_leading_trailing_whitespace(self):
        assert _sanitize_component("  FEB  ") == "FEB"

    def test_replaces_internal_spaces_with_underscore(self):
        assert _sanitize_component("Liga EBA") == "Liga_EBA"

    def test_replaces_dollar_sign(self):
        result = _sanitize_component("FEB$LF2")
        assert "$" not in result

    def test_collapses_multiple_underscores(self):
        assert _sanitize_component("A__B___C") == "A_B_C"

    def test_strips_leading_underscore(self):
        assert not _sanitize_component("_hello").startswith("_")

    def test_strips_trailing_underscore(self):
        assert not _sanitize_component("hello_").endswith("_")

    def test_empty_string_returns_empty(self):
        assert _sanitize_component("") == ""

    def test_normal_string_unchanged(self):
        assert _sanitize_component("FEB") == "FEB"


# ---------------------------------------------------------------------------
# get_collection_name
# ---------------------------------------------------------------------------

class TestGetCollectionName:
    def test_basic_format(self):
        result = get_collection_name("FEB", "LF2_2025", "A")
        assert result == "FEB_LF2_2025_A"

    def test_fbcyl_format(self):
        result = get_collection_name("FBCYL", "SE_2025", "A")
        assert result == "FBCYL_SE_2025_A"

    def test_spaces_replaced_by_underscores(self):
        result = get_collection_name("FEB LF2", "2024 2025", "Group A")
        assert " " not in result

    def test_dollar_sign_sanitised(self):
        result = get_collection_name("FEB$LF2", "2025", "A")
        assert "$" not in result

    def test_multiple_underscores_collapsed(self):
        result = get_collection_name("FEB", "LF2__2025", "A")
        assert "__" not in result

    def test_system_prefix_prefixed(self):
        result = get_collection_name("system.col", "2025", "A")
        assert not result.lower().startswith("system.")

    def test_returns_string(self):
        assert isinstance(get_collection_name("FEB", "2025", "A"), str)

    def test_empty_competition(self):
        result = get_collection_name("", "2025", "A")
        # Should not raise, result may start with _
        assert isinstance(result, str)

    def test_components_joined_by_underscores(self):
        parts = get_collection_name("FEB", "LF2", "A").split("_")
        assert len(parts) >= 3

    def test_special_chars_in_group(self):
        result = get_collection_name("FEB", "LF2", "Group/A")
        assert "/" not in result

    def test_unicode_whitespace_replaced(self):
        result = get_collection_name("FEB\tLF2", "2025", "A")
        assert "\t" not in result


# ---------------------------------------------------------------------------
# safe_divide
# ---------------------------------------------------------------------------

class TestSafeDivide:
    def test_returns_dict(self):
        result = safe_divide({"$sum": "$pts"}, {"$sum": "$games"})
        assert isinstance(result, dict)

    def test_top_level_key_is_cond(self):
        result = safe_divide({"$sum": "$pts"}, {"$sum": "$games"})
        assert "$cond" in result

    def test_cond_is_three_element_list(self):
        result = safe_divide({"$sum": "$pts"}, {"$sum": "$games"})
        assert isinstance(result["$cond"], list)
        assert len(result["$cond"]) == 3

    def test_default_zero_when_denominator_is_zero(self):
        result = safe_divide({"$sum": "$pts"}, {"$sum": "$games"}, default=0)
        # Second element of $cond is the default when denominator == 0
        assert result["$cond"][1] == 0

    def test_custom_default(self):
        result = safe_divide({"$sum": "$pts"}, {"$sum": "$games"}, default=-1)
        assert result["$cond"][1] == -1

    def test_condition_checks_denominator_eq_zero(self):
        denom = {"$sum": "$games"}
        result = safe_divide({"$sum": "$pts"}, denom)
        cond = result["$cond"][0]
        assert "$eq" in cond
        assert cond["$eq"][0] == denom

    def test_divide_expression_in_third_element(self):
        result = safe_divide({"$sum": "$pts"}, {"$sum": "$games"})
        divide_expr = result["$cond"][2]
        assert "$divide" in divide_expr

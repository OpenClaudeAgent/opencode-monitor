"""Tests for MITRE ATT&CK utilities."""

import pytest

from opencode_monitor.security.mitre_utils import (
    serialize_mitre_techniques,
    deserialize_mitre_techniques,
)


class TestSerializeMitreTechniques:
    """Tests for serialize_mitre_techniques function."""

    def test_serialize_empty_list(self):
        """Empty list serializes to '[]'."""
        result = serialize_mitre_techniques([])
        assert result == "[]"

    def test_serialize_list_of_techniques(self):
        """List of techniques serializes to JSON array."""
        techniques = ["T1059.001", "T1566.001", "T1027"]
        result = serialize_mitre_techniques(techniques)
        assert result == '["T1059.001", "T1566.001", "T1027"]'

    def test_serialize_single_technique(self):
        """Single technique in list serializes correctly."""
        result = serialize_mitre_techniques(["T1059"])
        assert result == '["T1059"]'

    def test_serialize_none_returns_empty_array(self):
        """None returns '[]'."""
        result = serialize_mitre_techniques(None)
        assert result == "[]"

    def test_serialize_string_returns_empty_array(self):
        """String input returns '[]'."""
        result = serialize_mitre_techniques("T1059")
        assert result == "[]"

    def test_serialize_dict_returns_empty_array(self):
        """Dict input returns '[]'."""
        result = serialize_mitre_techniques({"technique": "T1059"})
        assert result == "[]"

    def test_serialize_int_returns_empty_array(self):
        """Integer input returns '[]'."""
        result = serialize_mitre_techniques(123)
        assert result == "[]"


class TestDeserializeMitreTechniques:
    """Tests for deserialize_mitre_techniques function."""

    def test_deserialize_empty_array_string(self):
        """'[]' deserializes to empty list."""
        result = deserialize_mitre_techniques("[]")
        assert result == []

    def test_deserialize_techniques_array(self):
        """JSON array of techniques deserializes to list."""
        json_str = '["T1059.001", "T1566.001", "T1027"]'
        result = deserialize_mitre_techniques(json_str)
        assert result == ["T1059.001", "T1566.001", "T1027"]

    def test_deserialize_single_technique(self):
        """Single technique in array deserializes correctly."""
        result = deserialize_mitre_techniques('["T1059"]')
        assert result == ["T1059"]

    def test_deserialize_none_returns_empty_list(self):
        """None returns empty list."""
        result = deserialize_mitre_techniques(None)
        assert result == []

    def test_deserialize_empty_string_returns_empty_list(self):
        """Empty string returns empty list."""
        result = deserialize_mitre_techniques("")
        assert result == []

    def test_deserialize_invalid_json_returns_empty_list(self):
        """Invalid JSON returns empty list."""
        result = deserialize_mitre_techniques("not valid json")
        assert result == []

    def test_deserialize_json_object_returns_empty_list(self):
        """JSON object (not array) returns empty list."""
        result = deserialize_mitre_techniques('{"technique": "T1059"}')
        assert result == []

    def test_deserialize_json_string_returns_empty_list(self):
        """JSON string (not array) returns empty list."""
        result = deserialize_mitre_techniques('"T1059"')
        assert result == []


class TestRoundTrip:
    """Tests for serialize/deserialize round-trip."""

    def test_roundtrip_empty_list(self):
        """Empty list survives round-trip."""
        original = []
        serialized = serialize_mitre_techniques(original)
        deserialized = deserialize_mitre_techniques(serialized)
        assert deserialized == original

    def test_roundtrip_techniques(self):
        """Techniques survive round-trip."""
        original = ["T1059.001", "T1566.001", "T1027"]
        serialized = serialize_mitre_techniques(original)
        deserialized = deserialize_mitre_techniques(serialized)
        assert deserialized == original

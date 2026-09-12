"""
Tests for ``otg_mcp.schema.extract_component``.

``extract_component`` is the only schema logic left in the codebase: it walks a
dotted path over an OpenAPI document that has already been fetched from a target.
Two things matter about it and are pinned here — ``components.schemas.X`` is
handled specially (schema names themselves contain dots, e.g. ``Flow.Router``, so
they cannot be split on ``.``), and every failure mode is normalised to
``ValueError`` so callers have a single exception type to handle.
"""

import pytest

from otg_mcp.schema import extract_component


@pytest.fixture
def document():
    """A small OpenAPI document with dotted schema names and nested paths."""
    return {
        "openapi": "3.0.3",
        "info": {"title": "Open Traffic Generator API", "version": "1.20.0"},
        "components": {
            "schemas": {
                "Flow": {"description": "A flow object"},
                "Flow.Router": {"description": "A flow router object"},
            },
            "responses": {"Success": {"description": "Success response"}},
        },
        "paths": {"/config": {"post": {"operationId": "set_config"}}},
    }


class TestComponentsSchemasShortcut:
    """The ``components.schemas.X`` special case."""

    def test_schema_is_returned_by_name(self, document):
        """A schema under ``components.schemas`` is returned whole."""
        result = extract_component(document, "components.schemas.Flow")

        assert result == {"description": "A flow object"}

    def test_dotted_schema_name_is_treated_as_one_key(self, document):
        """A schema name containing a dot is looked up verbatim.

        OTG names schemas like ``Flow.Router``; splitting the path on every dot
        would look for a ``Router`` key inside ``Flow`` and never resolve.
        """
        result = extract_component(document, "components.schemas.Flow.Router")

        assert result == {"description": "A flow router object"}

    def test_unknown_schema_name_raises_value_error(self, document):
        """An unknown schema name raises ValueError naming the schema.

        Callers surface this message to the MCP client, so it has to identify
        what was asked for rather than just failing.
        """
        with pytest.raises(ValueError, match="Nope not found in components.schemas"):
            extract_component(document, "components.schemas.Nope")

    def test_document_without_components_raises_value_error(self):
        """A document with no ``components`` section raises ValueError, not KeyError.

        A target can serve a trimmed or malformed spec; the KeyError is converted
        so callers only ever handle ValueError.
        """
        with pytest.raises(ValueError, match="Error accessing components.schemas"):
            extract_component({"openapi": "3.0.3"}, "components.schemas.Flow")

    def test_document_without_schemas_section_raises_value_error(self):
        """A ``components`` section with no ``schemas`` key also raises ValueError."""
        with pytest.raises(ValueError, match="Error accessing components.schemas"):
            extract_component(
                {"components": {"responses": {}}}, "components.schemas.Flow"
            )


class TestDottedPathNavigation:
    """Generic dotted-path navigation for anything outside components.schemas."""

    def test_nested_path_is_resolved(self, document):
        """A multi-segment path walks into nested dictionaries."""
        result = extract_component(document, "info.title")

        assert result == "Open Traffic Generator API"

    def test_single_segment_path_returns_a_whole_section(self, document):
        """A one-segment path returns that top-level section."""
        result = extract_component(document, "paths")

        assert result == {"/config": {"post": {"operationId": "set_config"}}}

    def test_sibling_of_the_schemas_shortcut_is_navigated_generically(self, document):
        """``components.responses.X`` resolves through the generic walk.

        Only ``components.schemas.`` is special-cased, so neighbouring sections
        must still be reachable.
        """
        result = extract_component(document, "components.responses.Success")

        assert result == {"description": "Success response"}

    def test_missing_segment_raises_value_error_naming_the_segment(self, document):
        """A path segment that is absent raises ValueError identifying it.

        The message names both the missing segment and the full path so a typo is
        obvious from the error alone.
        """
        with pytest.raises(ValueError, match="Component missing not found in path"):
            extract_component(document, "info.missing")

    def test_navigating_into_a_non_container_raises_value_error(self, document):
        """Indexing into a scalar raises ValueError rather than TypeError.

        A path that runs past the end of the document hits ``in`` on a non-container;
        that TypeError is normalised like every other failure here.
        """
        with pytest.raises(ValueError, match="Invalid component path"):
            extract_component({"info": {"revision": 3}}, "info.revision.major")

    def test_navigating_into_a_list_raises_value_error(self, document):
        """A path segment addressed against a list is reported as a bad path."""
        with pytest.raises(ValueError, match="not found in path"):
            extract_component({"tags": ["a", "b"]}, "tags.first")

from src.llm import Provider, _TOOL_PARAMETERS
from src.types import EnrichedWordFromLLM


def test_tool_schema_matches_model():
    """Ensure _TOOL_PARAMETERS items schema matches EnrichedWordFromLLM."""
    item_schema = _TOOL_PARAMETERS["properties"]["words"]["items"]
    model_schema = EnrichedWordFromLLM.model_json_schema()
    model_schema.pop("$schema", None)
    model_schema.pop("title", None)
    assert item_schema == model_schema


def test_tool_schema_has_required_fields():
    """Ensure all non-optional EnrichedWordFromLLM fields are required."""
    item_schema = _TOOL_PARAMETERS["properties"]["words"]["items"]
    required = set(item_schema["required"])
    assert required == {"numero", "palavra", "explicacao", "traducao", "exemplos"}


def test_tool_schema_excludes_contexto():
    """Ensure contexto is NOT in the tool schema (it's post-hoc)."""
    item_schema = _TOOL_PARAMETERS["properties"]["words"]["items"]
    assert "contexto" not in item_schema.get("properties", {})
    assert "contexto" not in item_schema.get("required", [])


def test_provider_type_is_defined():
    """Ensure Provider can be imported without NameError."""
    assert Provider is not None

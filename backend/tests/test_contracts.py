from app.api import app
from app.schemas import Evidence, EvidenceReview, ExcerptSelection, Candidates, DraftContent, Quality


def test_openapi_and_strict_output_shapes():
    schema = app.openapi()
    assert "/api/v1/runs/{run_id}/approve" in schema["paths"]
    for model in [Evidence, EvidenceReview, ExcerptSelection, Candidates, DraftContent, Quality]:
        output = model.model_json_schema()
        definitions = [output, *output.get("$defs", {}).values()]
        for definition in definitions:
            if definition.get("type") == "object":
                assert definition["additionalProperties"] is False
                assert set(definition["properties"]) == set(definition["required"])

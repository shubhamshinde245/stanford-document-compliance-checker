"""HTTP surface.

TestClient is deliberately not used as a context manager: that would run the
lifespan, which starts the APScheduler job and prints the index status. These
tests exercise routes, not startup.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.main import MAX_UPLOAD_BYTES, app
from backend.retrieve.reports import save_report

from .test_reports import make_evaluation


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def saved_report():
    return save_report(
        filename="procedure.md",
        check_id="check-1",
        matches=[],
        evaluation=make_evaluation(),
    )


def upload(name: str = "procedure.md", body: bytes = b"Some procedure text."):
    return {"file": (name, body, "text/plain")}


# --------------------------------------------------------------------------
# Health
# --------------------------------------------------------------------------


def test_health_reports_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["ai_gateway"] in {"configured", "missing"}


# --------------------------------------------------------------------------
# Upload validation -- shared by /api/check and /api/evaluate
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/api/check", "/api/evaluate"])
def test_an_unsupported_extension_is_rejected(client, path):
    response = client.post(
        path, files=upload("procedure.exe"), data={"slug": "a-policy"}
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


@pytest.mark.parametrize("path", ["/api/check", "/api/evaluate"])
def test_an_empty_upload_is_rejected(client, path):
    response = client.post(
        path, files=upload(body=b""), data={"slug": "a-policy"}
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


@pytest.mark.parametrize("path", ["/api/check", "/api/evaluate"])
def test_an_oversized_upload_is_rejected(client, path):
    body = b"x" * (MAX_UPLOAD_BYTES + 1)
    response = client.post(path, files=upload(body=body), data={"slug": "a-policy"})
    assert response.status_code == 413
    assert "12 MB" in response.json()["detail"]


@pytest.mark.parametrize("path", ["/api/check", "/api/evaluate"])
def test_a_missing_file_is_a_validation_error(client, path):
    assert client.post(path, data={"slug": "a-policy"}).status_code == 422


def test_evaluate_requires_a_slug(client):
    assert client.post("/api/evaluate", files=upload()).status_code == 422


# --------------------------------------------------------------------------
# Slug validation -- the directory-escape boundary
# --------------------------------------------------------------------------


TRAVERSAL_SLUGS = ["../secrets", "..\\secrets", "a/../../b", "nested/slug"]


@pytest.mark.parametrize("slug", TRAVERSAL_SLUGS)
def test_evaluate_rejects_a_slug_that_could_escape_the_policy_directory(client, slug):
    response = client.post("/api/evaluate", files=upload(), data={"slug": slug})
    # A slug containing "/" may not route at all; either way it must not be served.
    assert response.status_code in {400, 404, 422}
    if response.status_code == 400:
        assert response.json()["detail"] == "Invalid policy slug."


@pytest.mark.parametrize("slug", ["a..b", "..b", "a.."])
def test_policy_routes_reject_dotted_slugs(client, slug):
    for path in (f"/api/policies/{slug}/pdf", f"/api/policies/{slug}/safeguards"):
        response = client.get(path)
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid policy slug."


@pytest.mark.parametrize("path", ["/api/policies/../pdf", "/api/reports/.."])
def test_a_bare_dot_dot_segment_never_reaches_a_handler(client, path):
    """Normalized away before routing, so it 404s rather than being validated.

    Asserted separately from the slug checks because the rejection happens a
    layer earlier -- what matters is only that it is never served.
    """
    assert client.get(path).status_code in {400, 404}


def test_an_unknown_policy_is_a_404(client, monkeypatch):
    monkeypatch.setattr("backend.main.load_catalog", lambda: {"policies": []})
    response = client.get("/api/policies/no-such-policy/safeguards")
    assert response.status_code == 404
    assert response.json()["detail"] == "Policy not found."


# --------------------------------------------------------------------------
# Reports
# --------------------------------------------------------------------------


def test_reports_list_is_empty_to_begin_with(client):
    response = client.get("/api/reports")
    assert response.status_code == 200
    assert response.json() == {"reports": []}


def test_a_saved_report_appears_in_the_listing(client, saved_report):
    body = client.get("/api/reports").json()
    assert [row["id"] for row in body["reports"]] == [saved_report.id]
    assert body["reports"][0]["filename"] == "procedure.md"


def test_a_report_can_be_fetched_by_id(client, saved_report):
    response = client.get(f"/api/reports/{saved_report.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == saved_report.id
    assert body["evaluation"]["rows"][0]["requirement_id"] == "REQ-1"


def test_a_missing_report_is_a_404(client):
    response = client.get("/api/reports/3f2504e0-4f89-11d3-9a0c-0305e82c3301")
    assert response.status_code == 404
    assert response.json()["detail"] == "Report not found."


@pytest.mark.parametrize("bad_id", ["not-a-uuid", "report", "a" * 100, "1234"])
def test_a_malformed_report_id_is_a_400_not_a_404(client, bad_id):
    """Malformed and absent are different answers, and the status codes say so."""
    response = client.get(f"/api/reports/{bad_id}")
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid report id."


def test_a_report_can_be_deleted(client, saved_report):
    assert client.delete(f"/api/reports/{saved_report.id}").json() == {
        "status": "deleted"
    }
    assert client.get(f"/api/reports/{saved_report.id}").status_code == 404
    assert client.get("/api/reports").json() == {"reports": []}


def test_deleting_twice_is_a_404_the_second_time(client, saved_report):
    client.delete(f"/api/reports/{saved_report.id}")
    assert client.delete(f"/api/reports/{saved_report.id}").status_code == 404


@pytest.mark.parametrize("bad_id", ["not-a-uuid", "report"])
def test_deleting_a_malformed_id_is_a_400(client, bad_id):
    assert client.delete(f"/api/reports/{bad_id}").status_code == 400


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------


def valid_settings(**overrides):
    payload = {
        "provider": "stanford",
        "chat_model": "gpt-5.6-sol",
        "embedding_model": "text-embedding-ada-002",
        "reasoning_effort": "medium",
        "match_min_confidence": 50.0,
        "match_min_gap": 2.5,
    }
    payload.update(overrides)
    return payload


def test_settings_are_returned_with_the_match_rule(client):
    body = client.get("/api/llm/settings").json()
    assert body["match_min_confidence"] == 50.0
    assert body["match_min_gap"] == 2.5
    assert set(body["locked_columns"]) == {
        "requirement_id",
        "verdict",
        "requirement_quote",
        "evidence_quote",
    }


def test_saving_the_match_rule_round_trips(client):
    response = client.put(
        "/api/llm/settings",
        json=valid_settings(match_min_confidence=61.0, match_min_gap=4.0),
    )
    assert response.status_code == 200
    assert response.json()["match_min_gap"] == 4.0
    assert client.get("/api/llm/settings").json()["match_min_confidence"] == 61.0


@pytest.mark.parametrize(
    "payload",
    [
        valid_settings(match_min_confidence=-1),
        valid_settings(match_min_confidence=101),
        valid_settings(match_min_gap=-0.5),
        valid_settings(match_min_gap=1000),
        valid_settings(match_min_gap="abc"),
        valid_settings(reasoning_effort="extreme"),
        valid_settings(provider="hal9000"),
        valid_settings(chat_model=""),
    ],
)
def test_invalid_settings_are_refused(client, payload):
    response = client.put("/api/llm/settings", json=payload)
    assert response.status_code in {400, 422}


def test_a_rejected_save_leaves_the_stored_settings_untouched(client):
    client.put("/api/llm/settings", json=valid_settings(match_min_gap=3.0))
    client.put("/api/llm/settings", json=valid_settings(match_min_gap=-5))
    assert client.get("/api/llm/settings").json()["match_min_gap"] == 3.0


def test_saving_columns_rejects_an_invalid_name(client):
    response = client.put(
        "/api/llm/settings",
        json=valid_settings(
            output_columns=[{"name": "Bad Name", "description": "x"}]
        ),
    )
    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()


def test_saving_columns_restores_the_locked_ones(client):
    response = client.put(
        "/api/llm/settings",
        json=valid_settings(
            output_columns=[{"name": "severity", "description": "How bad."}]
        ),
    )
    names = [column["name"] for column in response.json()["output_columns"]]
    assert names[:4] == [
        "requirement_id",
        "verdict",
        "requirement_quote",
        "evidence_quote",
    ]
    assert "severity" in names


# --------------------------------------------------------------------------
# Output schema preview
# --------------------------------------------------------------------------


def test_the_output_schema_preview_matches_what_the_model_is_sent(client):
    body = client.get("/api/llm/output-schema").json()
    assert body["verdicts"] == ["aligned", "contradicted", "missing", "flagged"]
    assert body["json_schema"]["strict"] is True
    assert "compliance analyst" in body["system_prompt"]
    row = body["json_schema"]["schema"]["properties"]["rows"]["items"]
    assert "sources" in row["required"]


def test_the_preview_follows_a_settings_change(client):
    """The preview is the contract; it has to track the saved columns."""
    client.put(
        "/api/llm/settings",
        json=valid_settings(
            output_columns=[{"name": "severity", "description": "How bad it is."}]
        ),
    )
    body = client.get("/api/llm/output-schema").json()
    row = body["json_schema"]["schema"]["properties"]["rows"]["items"]
    assert "severity" in row["properties"]
    assert "How bad it is." in body["system_prompt"]


# --------------------------------------------------------------------------
# Index not built
# --------------------------------------------------------------------------


def test_check_reports_503_when_the_index_is_missing(client, tmp_path, monkeypatch):
    """A 503 tells the operator to run `make index`; it is not a no-match."""
    monkeypatch.setattr(
        "backend.retrieve.index.INDEX_JSON", tmp_path / "absent.json"
    )
    monkeypatch.setattr("backend.retrieve.index.INDEX_NPZ", tmp_path / "absent.npz")
    response = client.post("/api/check", files=upload())
    assert response.status_code == 503
    assert "make index" in response.json()["detail"]


# --------------------------------------------------------------------------
# OpenAPI
# --------------------------------------------------------------------------


def test_every_route_is_documented(client):
    paths = client.get("/openapi.json").json()["paths"]
    for route in (
        "/api/health",
        "/api/check",
        "/api/evaluate",
        "/api/reports",
        "/api/reports/{report_id}",
        "/api/policies",
        "/api/llm/settings",
        "/api/llm/output-schema",
    ):
        assert route in paths


def test_the_check_response_advertises_the_match_rule(client):
    schema = client.get("/openapi.json").json()["components"]["schemas"]["CheckResponse"]
    for field in ("matched", "match_threshold", "match_min_gap", "match_gap"):
        assert field in schema["properties"]

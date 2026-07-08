"""
Consumer-driven contract tests for service-to-service HTTP calls.

Each test encodes what a CONSUMER actually sends/reads (from its call sites)
and asserts it against the PROVIDER's real OpenAPI schema. A provider rename,
a removed endpoint, or a consumer imagining a field fails here — in CI,
before anything reaches an environment.

When one of these tests fails, fix BOTH sides together (see CLAUDE.md,
"audit both sides of the contract in one pass").
"""

from typing import Any

import pytest

Spec = dict[str, Any]


@pytest.fixture(scope="module")
def job_spec() -> Spec:
    from jobcopilot_job.main import app

    return app.openapi()


@pytest.fixture(scope="module")
def profile_spec() -> Spec:
    from jobcopilot_profile.main import app

    return app.openapi()


@pytest.fixture(scope="module")
def agent_spec() -> Spec:
    from jobcopilot_agent.main import app

    return app.openapi()


@pytest.fixture(scope="module")
def discovery_spec() -> Spec:
    from jobcopilot_discovery.main import app

    return app.openapi()


# ── OpenAPI helpers ───────────────────────────────────────────────────────────


def _resolve(spec: Spec, schema: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        schema = spec["components"]["schemas"][name]
    return schema


def _operation(spec: Spec, method: str, path: str) -> dict[str, Any]:
    assert path in spec["paths"], f"provider no longer exposes {path}"
    ops = spec["paths"][path]
    assert method in ops, f"provider no longer supports {method.upper()} {path}"
    return ops[method]


def _query_params(spec: Spec, method: str, path: str) -> set[str]:
    op = _operation(spec, method, path)
    return {p["name"] for p in op.get("parameters", []) if p["in"] == "query"}


def _response_properties(spec: Spec, method: str, path: str, code: str = "200") -> dict[str, Any]:
    op = _operation(spec, method, path)
    assert code in op["responses"], f"{method.upper()} {path} has no {code} response"
    schema = _resolve(spec, op["responses"][code]["content"]["application/json"]["schema"])
    return schema.get("properties", {})


def _request_body(spec: Spec, method: str, path: str) -> dict[str, Any]:
    op = _operation(spec, method, path)
    return _resolve(spec, op["requestBody"]["content"]["application/json"]["schema"])


def _items_properties(spec: Spec, response_props: dict[str, Any]) -> set[str]:
    """Field names of PaginatedResponse.items entries."""
    items_schema = _resolve(spec, response_props["items"]["items"])
    return set(items_schema.get("properties", {}))


def _assert_body_compatible(spec: Spec, method: str, path: str, sent: set[str]) -> None:
    body = _request_body(spec, method, path)
    declared = set(body.get("properties", {}))
    required = set(body.get("required", []))
    unknown = sent - declared
    missing = required - sent
    assert not unknown, f"{method.upper()} {path}: consumer sends unknown fields {unknown}"
    assert not missing, f"{method.upper()} {path}: consumer omits required fields {missing}"


# ── Agent Service → Job Service (ReAct tools + job.discovered consumer) ──────


def test_search_jobs_tool_contract(job_spec: Spec) -> None:
    assert {"tenant_id", "q", "limit"} <= _query_params(job_spec, "get", "/internal/jobs")
    props = _response_properties(job_spec, "get", "/internal/jobs")
    assert "items" in props
    # Fields the tool copies into its LLM-facing summary
    assert {"job_id", "title", "company_name", "location"} <= _items_properties(job_spec, props)


def test_get_applications_tool_contract(job_spec: Spec) -> None:
    assert {"user_id", "tenant_id", "status", "limit"} <= _query_params(
        job_spec, "get", "/internal/applications"
    )
    props = _response_properties(job_spec, "get", "/internal/applications")
    assert "items" in props
    assert {"application_id", "job_id", "status", "match_score", "job"} <= _items_properties(
        job_spec, props
    )


def test_update_kanban_tool_contract(job_spec: Spec) -> None:
    _assert_body_compatible(
        job_spec,
        "patch",
        "/internal/applications/by-job/{job_id}",
        sent={"user_id", "tenant_id", "status"},
    )
    props = _response_properties(job_spec, "patch", "/internal/applications/by-job/{job_id}")
    assert "status" in props


def test_analyze_job_tool_contract(job_spec: Spec) -> None:
    props = _response_properties(job_spec, "get", "/internal/jobs/{job_id}")
    # Fields analyze_job reads before running AnalyzerGraph
    assert {"job_id", "tenant_id", "url", "title", "company_name", "location", "raw_jd"} <= set(
        props
    )


def test_job_discovered_consumer_upsert_contract(job_spec: Spec) -> None:
    _assert_body_compatible(
        job_spec,
        "post",
        "/internal/jobs",
        sent={
            "tenant_id",
            "url",
            "title",
            "company_name",
            "location",
            "raw_jd",
            "source",
            "discovered_at",
        },
    )
    # The consumer keys its analysis by this field
    assert "job_id" in _response_properties(job_spec, "post", "/internal/jobs")

    _assert_body_compatible(job_spec, "patch", "/internal/jobs/{job_id}", sent={"analysis"})


# ── Agent Service → Profile Service (resume text for AnalyzerGraph/matching) ─


def test_agent_reads_active_resume_text(profile_spec: Spec) -> None:
    props = _response_properties(profile_spec, "get", "/internal/profiles/{user_id}")
    assert "active_resume_text" in props


# ── Discovery Service → Profile Service (cookie validation) ──────────────────


def test_discovery_reads_decrypted_cookie(profile_spec: Spec) -> None:
    props = _response_properties(profile_spec, "get", "/internal/profiles/{user_id}/cookie")
    assert "linkedin_cookie" in props


# ── /v1 collection endpoints must be PaginatedResponse (CLAUDE.md rule) ──────

_PAGINATED_FIELDS = {"items", "total", "page", "size", "has_next"}


@pytest.mark.parametrize(
    ("spec_name", "path"),
    [
        ("job_spec", "/v1/jobs"),
        ("job_spec", "/v1/applications"),
        ("job_spec", "/v1/companies"),
        ("profile_spec", "/v1/resumes"),
        ("discovery_spec", "/v1/discovery/configs"),
        ("discovery_spec", "/v1/discovery/runs"),
    ],
)
def test_v1_collections_are_paginated(
    spec_name: str, path: str, request: pytest.FixtureRequest
) -> None:
    spec = request.getfixturevalue(spec_name)
    props = _response_properties(spec, "get", path)
    assert _PAGINATED_FIELDS <= set(props), (
        f"GET {path} must return PaginatedResponse, got fields {set(props)}"
    )


# ── Agent /v1 wire fields the frontend detail page reads ─────────────────────


def test_analysis_response_wire_fields(agent_spec: Spec) -> None:
    props = _response_properties(agent_spec, "get", "/v1/agent/analyses/{job_id}")
    assert {"analysis_id", "job_id", "jd_structured", "match_score", "status"} <= set(props)

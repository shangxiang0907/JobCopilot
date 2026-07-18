"""Version traceability: /healthz and /metrics must surface the build's git revision.

The revision travels image ENV GIT_SHA -> BaseServiceSettings.git_sha ->
build_health_router / jobcopilot_build_info. A regression here silently breaks
the deploy-time closed-loop verification in deploy.sh.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jobcopilot_shared.config import BaseServiceSettings
from jobcopilot_shared.health import build_health_router
from jobcopilot_shared.metrics import instrument_app


def test_healthz_reports_version_and_revision() -> None:
    app = FastAPI()
    app.include_router(build_health_router("test-svc", "0.1.0", "abc123def"))
    client = TestClient(app)
    for path in ("/healthz/live", "/healthz/ready"):
        body = client.get(path).json()
        assert body == {
            "status": "ok",
            "service": "test-svc",
            "version": "0.1.0",
            "revision": "abc123def",
        }


def test_settings_read_git_sha_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_SHA", "deadbeefcafe")
    assert BaseServiceSettings().git_sha == "deadbeefcafe"


def test_settings_git_sha_defaults_to_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GIT_SHA", raising=False)
    assert BaseServiceSettings().git_sha == "dev"


def test_build_info_metric_carries_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_SHA", "cafe1234")
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    app = FastAPI()
    instrument_app(app)
    text = TestClient(app).get("/metrics").text
    assert 'jobcopilot_build_info{revision="cafe1234"} 1.0' in text

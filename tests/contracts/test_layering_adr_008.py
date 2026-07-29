"""
Layering contract (SAD ADR-008): the Core layer never depends on the AI layer.

The Core layer (Profile / Job / Discovery / Notification) must stay complete and
usable with the Agent Service stopped. `import-linter` enforces the Python-import
half of that rule (`pyproject.toml`, contract "Core services never depend on the
AI layer (ADR-008)"). It cannot see the two ways a dependency actually tends to
enter this repo:

* an HTTP call assembled from a base URL in a settings class, and
* a container that will not start until the Agent Service is healthy.

Those are what this module checks. A violation here is not a style problem —
it means switching the AI layer off (quota exhausted, LLM outage, a hand
refactor of `services/agent/`) can take a plain CRUD journey down with it, which
is the exact failure ADR-008 was written to prevent.

Deliberately NOT forbidden:
* The Agent Service depending on Core internal APIs — that is the allowed
  direction.
* Kong routing `/v1/agent/*` — the gateway fronts both layers by definition.
* A Core service consuming an event the AI layer publishes. Nothing does today,
  and if one ever did it would still start, run and serve with the publisher
  absent; it would simply receive no such events. Queue-decoupled consumption is
  not a startup or request-path dependency.

The behavioural half of this ADR is the no-AI-mode E2E test (v0.3 item 4): these
tests prove the coupling is absent in the source, that one proves the product
still works without the layer.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

# Service directory name → its Python package. The AI layer is deliberately
# absent: it is the layer these services must not reach for.
CORE_SERVICES: dict[str, str] = {
    "profile": "jobcopilot_profile",
    "job": "jobcopilot_job",
    "discovery": "jobcopilot_discovery",
    "notification": "jobcopilot_notification",
}

CORE_COMPOSE_SERVICES = (
    "profile-service",
    "job-service",
    "discovery-service",
    "notification-service",
)

AGENT_COMPOSE_SERVICE = "agent-service"

# Every spelling of "reach the Agent Service" that has a plausible route into a
# Core service: its container hostname, its public and internal path prefixes,
# a settings field or env var holding its base URL, and its Python package.
# Patterns are specific on purpose — a bare "agent" would fire on User-Agent
# strings in the discovery adapters and train everyone to ignore this test.
AGENT_REFERENCE_PATTERNS: dict[str, re.Pattern[str]] = {
    "agent service hostname": re.compile(r"agent-service"),
    "agent API path": re.compile(r"/v1/agent\b"),
    "agent internal path": re.compile(r"/internal/agent\b"),
    "agent base URL setting": re.compile(r"(?i)\bagent_service_url\b"),
    "agent Python package": re.compile(r"\bjobcopilot_agent\b"),
}


def _core_source_files() -> list[Path]:
    files: list[Path] = []
    for service in CORE_SERVICES:
        src = REPO_ROOT / "services" / service / "src"
        assert src.is_dir(), f"{src} is missing — did the service layout change?"
        files.extend(sorted(src.rglob("*.py")))
    assert files, "found no Core service sources to scan"
    return files


@pytest.fixture(scope="module")
def compose() -> dict[str, Any]:
    raw = (REPO_ROOT / "infra" / "docker-compose.yml").read_text(encoding="utf-8")
    parsed = yaml.safe_load(raw)
    assert AGENT_COMPOSE_SERVICE in parsed["services"], (
        "the Agent Service is no longer in docker-compose.yml — this test's "
        "premise changed, update it rather than deleting it"
    )
    return dict(parsed["services"])


def test_core_settings_expose_no_agent_base_url() -> None:
    """A Core service that knows the Agent Service's address will eventually call it."""
    offenders: list[str] = []
    for service, package in CORE_SERVICES.items():
        module = __import__(f"{package}.config", fromlist=["Settings"])
        for field in module.Settings.model_fields:
            if "agent" in field.lower():
                offenders.append(f"{service}: Settings.{field}")

    assert not offenders, (
        f"Core service settings must not carry an Agent Service address (SAD ADR-008): {offenders}"
    )


def test_core_sources_never_reference_the_agent_service() -> None:
    """The HTTP direction import-linter cannot see: a URL string is not an import."""
    offenders: list[str] = []
    for path in _core_source_files():
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for label, pattern in AGENT_REFERENCE_PATTERNS.items():
                if pattern.search(line):
                    rel = path.relative_to(REPO_ROOT)
                    offenders.append(f"{rel}:{line_no} ({label}): {line.strip()}")

    assert not offenders, (
        "Core services must not reach the AI layer (SAD ADR-008). If the Core "
        "layer needs this capability, it belongs in the Core layer:\n" + "\n".join(offenders)
    )


def test_no_core_container_depends_on_the_agent_service(compose: dict[str, Any]) -> None:
    """`depends_on: agent-service` would make the AI layer a Core startup prerequisite."""
    offenders: list[str] = []
    for name in CORE_COMPOSE_SERVICES:
        assert name in compose, f"{name} is missing from docker-compose.yml"
        # Both compose forms: the short list and the long condition mapping.
        depends_on = compose[name].get("depends_on") or {}
        if AGENT_COMPOSE_SERVICE in list(depends_on):
            offenders.append(f"{name}.depends_on")

        env = compose[name].get("environment") or {}
        values = env.values() if isinstance(env, dict) else env
        for value in values:
            if AGENT_COMPOSE_SERVICE in str(value):
                offenders.append(f"{name}.environment → {value}")

    assert not offenders, (
        "A Core container must start and serve with the Agent Service stopped "
        f"(SAD ADR-008): {offenders}"
    )


def test_the_agent_service_may_depend_on_core(compose: dict[str, Any]) -> None:
    """
    The allowed direction, pinned so a future 'symmetry' cleanup cannot quietly
    invert the layering: ADR-008 is one-way, not no-way.
    """
    agent = compose[AGENT_COMPOSE_SERVICE]
    settings = __import__("jobcopilot_agent.config", fromlist=["Settings"]).Settings
    core_urls = {f for f in settings.model_fields if f.endswith("_service_url")}

    assert core_urls, (
        "the Agent Service no longer holds any Core service URL — either the AI "
        "layer stopped using the Core layer, or the wiring moved and this test "
        "is now blind"
    )
    assert agent.get("depends_on"), "the Agent Service should still start after the Core layer"

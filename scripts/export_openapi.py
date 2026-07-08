#!/usr/bin/env python
"""
Export each FastAPI service's OpenAPI schema to openapi/<service>.json.

    ~/.local/bin/uv run python scripts/export_openapi.py

The committed JSON files are the wire-contract snapshot: frontend types are
generated from them (npm run gen:api-types) and CI fails if either is stale.
Each service is exported in a subprocess so module-level state (settings,
metric registries) cannot leak across services.
"""

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "openapi"

SERVICES = {
    "profile": "jobcopilot_profile.main",
    "job": "jobcopilot_job.main",
    "discovery": "jobcopilot_discovery.main",
    "agent": "jobcopilot_agent.main",
    "notification": "jobcopilot_notification.main",
}

# Engines/clients are created lazily; imports only need parseable values.
ENV_DEFAULTS = {
    "DATABASE_URL": "postgresql+asyncpg://placeholder:placeholder@localhost:5432/placeholder",
    "ENCRYPTION_KEY": "0" * 64,
    "REDIS_URL": "redis://localhost:6379",
    "RABBITMQ_URL": "amqp://guest:guest@localhost:5672/",
    "DASHSCOPE_API_KEY": "placeholder",
    "LANGCHAIN_TRACING_V2": "false",
}


def export_one(name: str) -> None:
    app = importlib.import_module(SERVICES[name]).app
    spec = app.openapi()
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / f"{name}.json"
    out.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n")
    print(f"  openapi/{name}.json  ({len(spec['paths'])} paths)")


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--one":
        export_one(sys.argv[2])
        return 0

    env = {**os.environ}
    for key, value in ENV_DEFAULTS.items():
        env.setdefault(key, value)

    print("Exporting OpenAPI schemas:")
    for name in SERVICES:
        subprocess.run(
            [sys.executable, __file__, "--one", name],
            check=True,
            env=env,
            cwd=REPO_ROOT,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

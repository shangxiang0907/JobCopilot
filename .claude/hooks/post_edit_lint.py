#!/usr/bin/env python3
"""PostToolUse hook: lint every edited/written Python file immediately.

Reads the hook payload from stdin, and for .py files runs `ruff check` and
`ruff format --check` on just that file. Failures exit 2 with the diagnostics
on stderr, which Claude Code feeds straight back to the model — the model gets
mechanical feedback on every edit instead of discovering lint failures at
pre-push time. (mypy stays in the pre-push checklist/CI: a strict whole-service
run is too slow for a per-edit hook.)
"""

import json
import os
import subprocess
import sys

UV = os.path.expanduser("~/.local/bin/uv")


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    file_path = (payload.get("tool_input") or {}).get("file_path", "")
    if not file_path.endswith(".py") or "/.venv/" in file_path or not os.path.exists(file_path):
        return

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    failures: list[str] = []
    for args in (["ruff", "check", file_path], ["ruff", "format", "--check", file_path]):
        result = subprocess.run(
            [UV, "run", *args],
            capture_output=True,
            text=True,
            cwd=project_dir,
            timeout=60,
        )
        if result.returncode != 0:
            failures.append(result.stdout + result.stderr)

    if failures:
        sys.stderr.write(
            f"Lint failed for {file_path} — fix before continuing:\n" + "\n".join(failures)
        )
        sys.exit(2)


if __name__ == "__main__":
    main()

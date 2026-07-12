#!/usr/bin/env python3
"""PreToolUse hook: block Bash commands that violate repo conventions.

Reads the hook payload from stdin, inspects tool_input.command, and exits 2
(with the reason on stderr, which Claude Code feeds back to the model) when a
forbidden pattern is found. Conventions enforced (see CLAUDE.md):

- `docker compose build --parallel` overloads the WSL/Docker Desktop vsock
  credential-helper channel; Compose v2 already parallelizes builds.
- Bare `python` / `python3`: this uv workspace shares one .venv — everything
  must run through `uv run` (the hook itself runs on system python3, which is
  harness infrastructure, not project code).
- `uv run --package`: breaks the single-workspace-venv model.
"""

import json
import re
import sys

_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")


def segments(command: str) -> list[str]:
    """Split a shell command into pipeline/sequence segments.

    Quoted spans are dropped first: their content is data (grep patterns,
    commit messages, JSON payloads), not commands, and must not create
    false segment boundaries.
    """
    return [s.strip() for s in re.split(r"[;&|]+|\n", _QUOTED.sub("", command)) if s.strip()]


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    command = (payload.get("tool_input") or {}).get("command", "")
    if not command:
        return

    for seg in segments(command):
        # Env-var prefixes (FOO=bar cmd ...) don't change what the command is.
        stripped = re.sub(r"^(\w+=\S+\s+)*", "", seg)

        if (
            re.match(r"docker(-compose)?\b", stripped)
            and re.search(r"\bbuild\b", stripped)
            and "--parallel" in stripped
        ):
            sys.stderr.write(
                "BLOCKED: never use --parallel with docker compose build (WSL vsock "
                "credential-helper contention — see CLAUDE.md). Run `docker compose build` "
                "without the flag; Compose v2 parallelizes on its own.\n"
            )
            sys.exit(2)

        if re.match(r"(\S*/)?uv\s+run\s+--package\b", stripped):
            sys.stderr.write(
                "BLOCKED: `uv run --package` is forbidden — this workspace shares a single "
                ".venv at the repo root. Use plain `~/.local/bin/uv run <cmd>` (see CLAUDE.md).\n"
            )
            sys.exit(2)

        # Bare python at the start of a segment; python inside containers
        # (docker ... python) is legitimate and never segment-initial.
        if re.match(r"python3?\b", stripped):
            sys.stderr.write(
                "BLOCKED: never call python directly — this uv workspace requires "
                "`~/.local/bin/uv run python ...` (see CLAUDE.md, Running Python Commands).\n"
            )
            sys.exit(2)


if __name__ == "__main__":
    main()

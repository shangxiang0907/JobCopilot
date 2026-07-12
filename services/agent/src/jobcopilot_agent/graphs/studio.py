"""LangGraph Studio entry points — development only, never imported by the service.

`build_react_agent` bakes user/tenant into the system prompt, so it cannot be
exported as a module-level compiled graph. Studio supports graph *factories*
that receive a RunnableConfig; this wrapper adapts the factory and reads
user_id / tenant_id from `configurable` (settable in the Studio UI), with
dev placeholders as defaults.

Registered in the repo-root `langgraph.json`; launch with `langgraph dev`.
"""

from typing import Any

from langchain_core.runnables import RunnableConfig

from jobcopilot_agent.graphs.react_graph import build_react_agent


def react_graph(config: RunnableConfig) -> Any:
    configurable = (config or {}).get("configurable", {})
    return build_react_agent(
        user_id=configurable.get("user_id", "studio-dev-user"),
        tenant_id=configurable.get("tenant_id", "studio-dev-tenant"),
    )

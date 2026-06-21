"""
ReActGraph — AI assistant with tool use, streamed via SSE.

Uses LangGraph's create_react_agent with DashScope LLM and the 5 ReAct tools.
User context (user_id, tenant_id) is injected via RunnableConfig.configurable.
"""

from typing import Any

from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent

from jobcopilot_agent.prompts.react import REACT_SYSTEM
from jobcopilot_agent.services.llm import get_llm
from jobcopilot_agent.tools.job_tools import ALL_TOOLS


def build_react_agent(user_id: str, tenant_id: str) -> Any:
    """Build a ReAct agent with user context bound in the system prompt."""
    llm = get_llm()
    system_prompt = REACT_SYSTEM.format(user_id=user_id, tenant_id=tenant_id)
    return create_react_agent(
        llm,
        tools=ALL_TOOLS,
        prompt=SystemMessage(content=system_prompt),
    )

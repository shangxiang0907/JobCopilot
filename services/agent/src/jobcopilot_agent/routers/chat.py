"""
POST /v1/agent/chat/stream — SSE streaming AI chat endpoint.

Streams ReActGraph output as Server-Sent Events.
SSE format:  data: {"type": "token", "content": "..."}\n\n
             data: {"type": "tool_call", "name": "...", "args": {...}}\n\n
             data: {"type": "done"}\n\n
"""

import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

from jobcopilot_agent.deps import CurrentUser
from jobcopilot_agent.graphs.react_graph import build_react_agent
from jobcopilot_agent.schemas.agent import ChatRequest

log = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/agent/chat", tags=["chat"])


async def _event_stream(
    messages: list[dict],
    user_id: str,
    tenant_id: str,
) -> AsyncGenerator[str, None]:
    agent = build_react_agent(user_id, tenant_id)
    lc_messages = [
        HumanMessage(content=m["content"]) if m["role"] == "user" else m for m in messages
    ]

    config = {
        "configurable": {"user_id": user_id, "tenant_id": tenant_id},
    }

    try:
        async for event in agent.astream_events(
            {"messages": lc_messages},
            config=config,
            version="v2",
        ):
            event_type = event.get("event")

            if event_type == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                if chunk and chunk.content:
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"

            elif event_type == "on_tool_start":
                payload = json.dumps(
                    {
                        "type": "tool_call",
                        "name": event.get("name"),
                        "args": event["data"].get("input", {}),
                    }
                )
                yield f"data: {payload}\n\n"

            elif event_type == "on_tool_end":
                yield f"data: {json.dumps({'type': 'tool_result', 'name': event.get('name')})}\n\n"

    except Exception as exc:
        log.error("stream_failed", extra={"error": str(exc)})
        yield f"data: {json.dumps({'type': 'error', 'content': 'Stream error occurred'})}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    user: CurrentUser,
) -> StreamingResponse:
    """Stream AI assistant responses as Server-Sent Events."""
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    return StreamingResponse(
        _event_stream(
            messages=messages,
            user_id=str(user["user_id"]),
            tenant_id=str(user["tenant_id"]),
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

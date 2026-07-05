"""Content narrowing for LLM responses shared by the graph nodes."""

from langchain_core.messages import BaseMessage


def response_text(response: BaseMessage) -> str:
    """Return the response's plain-text content.

    Raises TypeError for non-string (content-block / multimodal) payloads, which
    the JSON-parsing graph nodes cannot consume. Unlike an `assert isinstance`,
    this narrowing survives `python -O` and reports a precise error into each
    node's failure path.
    """
    content = response.content
    if not isinstance(content, str):
        raise TypeError(f"expected text LLM response, got {type(content).__name__}")
    return content

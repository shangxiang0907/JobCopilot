from functools import lru_cache

from langchain_openai import ChatOpenAI

from jobcopilot_agent.config import settings


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        openai_api_key=settings.dashscope_api_key or "placeholder",
        openai_api_base=settings.dashscope_base_url,
        temperature=0.1,
    )

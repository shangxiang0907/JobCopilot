from functools import lru_cache

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from jobcopilot_agent.config import settings


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=SecretStr(settings.dashscope_api_key or "placeholder"),
        base_url=settings.dashscope_base_url,
        temperature=0.1,
    )

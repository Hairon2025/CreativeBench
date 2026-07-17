"""GLM client factory using its OpenAI-compatible endpoint."""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from creativebench.config import Settings


class MissingGLMAPIKeyError(RuntimeError):
    """Raised before client construction when GLM credentials are absent."""


def build_glm_model(settings: Settings) -> BaseChatModel:
    """Build a LangChain chat model without sending a network request."""

    if settings.glm_api_key is None or not settings.glm_api_key.get_secret_value().strip():
        raise MissingGLMAPIKeyError(
            "未配置 CREATIVEBENCH_GLM_API_KEY；请在最后联调阶段写入本地 .env"
        )

    return ChatOpenAI(
        model=settings.glm_model,
        api_key=settings.glm_api_key.get_secret_value(),
        base_url=settings.glm_base_url,
        temperature=0,
        timeout=settings.glm_timeout_seconds,
        max_retries=0,
        model_kwargs={"response_format": {"type": "json_object"}},
    )

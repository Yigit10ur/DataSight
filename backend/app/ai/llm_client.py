from typing import Protocol

from app.config import settings


class LLMError(RuntimeError):
    """The model could not be reached or answered with nothing usable."""


class LLMClient(Protocol):
    def complete(self, system: str, user: str) -> str: ...


class AnthropicClient:
    """The only place in the codebase that talks to a model."""

    def __init__(self, api_key: str, model: str, max_tokens: int, timeout: float) -> None:
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._timeout = timeout

    def complete(self, system: str, user: str) -> str:
        from anthropic import Anthropic, AnthropicError

        client = Anthropic(api_key=self._api_key, timeout=self._timeout)
        try:
            response = client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except AnthropicError as error:
            raise LLMError(str(error)) from error

        text = "".join(block.text for block in response.content if block.type == "text")
        if not text.strip():
            raise LLMError("The model returned an empty response.")
        return text


def default_client() -> LLMClient | None:
    """The configured client, or nothing when no key has been supplied.

    Returning None rather than raising is deliberate: an explanation layer is an
    addition to the product, and the product has to work without it.
    """
    if not settings.anthropic_api_key:
        return None

    return AnthropicClient(
        api_key=settings.anthropic_api_key,
        model=settings.explanation_model,
        max_tokens=settings.explanation_max_tokens,
        timeout=settings.explanation_timeout_seconds,
    )

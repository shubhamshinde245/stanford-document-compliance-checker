from __future__ import annotations

from typing import Any

from backend.llm.providers import (
    LLMError,
    configured_providers,
    get_provider,
)
from backend.llm.store import load_settings

PREVIEW_DIMS = 8


class LLMRouter:
    """Switchboard for Stanford Gateway, OpenAI, and Anthropic.

    Ollama is reserved as a local fallback but is not wired in this pass.
    """

    def settings(self) -> dict[str, Any]:
        data = load_settings()
        data["configured"] = configured_providers()
        return data

    def _chat_provider(self, provider_id: str | None = None):
        settings = load_settings()
        chosen = provider_id or settings["provider"]
        if chosen == "ollama":
            raise LLMError(
                "Ollama is a placeholder fallback and is not wired yet.",
                status_code=501,
            )
        configured = configured_providers()
        if chosen in configured and not configured[chosen]:
            label = {
                "stanford": "Stanford Gateway",
                "openai": "OpenAI",
                "anthropic": "Anthropic",
            }.get(chosen, chosen)
            raise LLMError(
                f"{label} is not configured. Add the API key on the server.",
                status_code=503,
            )
        return get_provider(chosen)

    def _embed_provider(self, provider_id: str | None = None):
        settings = load_settings()
        chosen = provider_id or settings["provider"]
        if chosen == "anthropic":
            configured = configured_providers()
            if configured["stanford"]:
                return get_provider("stanford")
            if configured["openai"]:
                return get_provider("openai")
            raise LLMError(
                "Embeddings need Stanford Gateway or OpenAI. Anthropic has no embeddings API.",
                status_code=400,
            )
        return self._chat_provider(chosen)

    async def list_models(self, provider_id: str | None = None) -> list[dict[str, Any]]:
        return await self._chat_provider(provider_id).list_models()

    async def chat(
        self,
        prompt: str,
        *,
        model: str | None = None,
        reasoning_effort: str | None = None,
        provider_id: str | None = None,
    ) -> dict[str, Any]:
        text = prompt.strip()
        if not text:
            raise LLMError("Prompt is empty.", status_code=400)
        settings = load_settings()
        effort = reasoning_effort or settings["reasoning_effort"]
        provider = self._chat_provider(provider_id)
        result = await provider.chat(
            model=model or settings["chat_model"],
            prompt=text,
            reasoning_effort=effort,
        )
        result["reasoning_effort"] = effort if effort != "none" else None
        return result

    async def embed(
        self,
        text: str,
        *,
        model: str | None = None,
        provider_id: str | None = None,
    ) -> dict[str, Any]:
        value = text.strip()
        if not value:
            raise LLMError("Embedding input is empty.", status_code=400)
        settings = load_settings()
        provider = self._embed_provider(provider_id)
        result = await provider.embed(
            model=model or settings["embedding_model"],
            text=value,
        )
        preview = result.get("preview") or []
        result["preview"] = preview[:PREVIEW_DIMS]
        return result

    async def embed_many(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        provider_id: str | None = None,
    ) -> dict[str, Any]:
        cleaned = [text.strip() for text in texts]
        if not cleaned or any(not value for value in cleaned):
            raise LLMError("Embedding input is empty.", status_code=400)
        settings = load_settings()
        provider = self._embed_provider(provider_id)
        return await provider.embed_many(
            model=model or settings["embedding_model"],
            texts=cleaned,
        )


llm = LLMRouter()

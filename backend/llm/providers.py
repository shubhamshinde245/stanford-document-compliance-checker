from __future__ import annotations

import json
from typing import Any, Literal

import httpx

from backend.settings import (
    AI_GATEWAY_API_KEY,
    AI_GATEWAY_BASE_URL,
    ANTHROPIC_API_KEY,
    ANTHROPIC_BASE_URL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
)

ModelKind = Literal["chat", "embedding", "other"]

TIMEOUT = httpx.Timeout(300.0, connect=10.0)
ANTHROPIC_VERSION = "2023-06-01"


class LLMError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def classify_model(model_id: str) -> ModelKind:
    lower = model_id.lower()
    if "embedding" in lower:
        return "embedding"
    if any(token in lower for token in ("dall-e", "imagen", "realtime")):
        return "other"
    if "image" in lower or "batch" in lower:
        return "other"
    return "chat"


def v1_base(url: str) -> str:
    base = url.rstrip("/")
    if base.endswith("/v1"):
        return base
    return f"{base}/v1"


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return ""


def _error_message(payload: Any, fallback: str) -> str:
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
        if isinstance(error, str) and error.strip():
            return error.strip()
        for key in ("detail", "message"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return fallback


async def _request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    json: dict[str, Any] | None = None,
) -> Any:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.request(method, url, headers=headers, json=json)
    except httpx.TimeoutException as exc:
        raise LLMError("The model request timed out.", status_code=504) from exc
    except httpx.RequestError as exc:
        raise LLMError(f"Could not reach the model provider: {exc}", status_code=502) from exc

    body: Any
    try:
        body = response.json()
    except ValueError:
        body = None

    if response.is_error:
        raise LLMError(
            _error_message(body, f"Provider returned HTTP {response.status_code}."),
            status_code=502 if response.status_code >= 500 else response.status_code,
        )
    return body


class OpenAICompatibleProvider:
    def __init__(self, provider_id: str, base_url: str, api_key: str, label: str) -> None:
        self.id = provider_id
        self.label = label
        self.base_url = v1_base(base_url)
        self.api_key = api_key

    def _require_key(self) -> None:
        if not self.api_key:
            raise LLMError(
                f"{self.label} is not configured. Add the API key on the server.",
                status_code=503,
            )

    def _headers(self) -> dict[str, str]:
        self._require_key()
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def list_models(self) -> list[dict[str, Any]]:
        payload = await _request_json(
            "GET",
            f"{self.base_url}/models",
            headers=self._headers(),
        )
        items = payload.get("data") if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            raise LLMError(f"{self.label} returned an unexpected models list.")
        models: list[dict[str, Any]] = []
        for item in items:
            if isinstance(item, str):
                model_id = item
                owned_by = ""
            elif isinstance(item, dict):
                model_id = str(item.get("id") or item.get("name") or "").strip()
                owned_by = str(item.get("owned_by") or "")
            else:
                continue
            if not model_id:
                continue
            models.append(
                {
                    "id": model_id,
                    "kind": classify_model(model_id),
                    "owned_by": owned_by,
                }
            )
        models.sort(key=lambda row: (row["kind"], row["id"].lower()))
        return models

    async def chat(
        self,
        *,
        model: str,
        prompt: str,
        reasoning_effort: str,
        json_schema: dict[str, Any] | None = None,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if system and system.strip():
            messages.append({"role": "system", "content": system.strip()})
        messages.append({"role": "user", "content": prompt})
        body: dict[str, Any] = {
            "model": model,
            "stream": False,
            "messages": messages,
        }
        if reasoning_effort and reasoning_effort != "none":
            body["reasoning_effort"] = reasoning_effort
            body["max_completion_tokens"] = max_tokens or 2048
        elif max_tokens:
            body["max_completion_tokens"] = max_tokens
        if json_schema:
            schema = json_schema.get("schema") if "schema" in json_schema else json_schema
            name = str(json_schema.get("name") or "result")
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": name,
                    "strict": True,
                    "schema": schema,
                },
            }
        payload = await _request_json(
            "POST",
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=body,
        )
        content = ""
        if isinstance(payload, dict):
            choices = payload.get("choices")
            if isinstance(choices, list) and choices:
                first = choices[0]
                if isinstance(first, dict):
                    message = first.get("message")
                    if isinstance(message, dict):
                        content = _message_text(message.get("content"))
        return {
            "model": str(payload.get("model") if isinstance(payload, dict) else model),
            "content": content.strip(),
        }

    async def embed(self, *, model: str, text: str) -> dict[str, Any]:
        batch = await self.embed_many(model=model, texts=[text])
        vector = batch["embeddings"][0]
        return {
            "model": batch["model"],
            "dimensions": batch["dimensions"],
            "embedding": vector,
            "preview": vector[:8],
        }

    async def embed_many(self, *, model: str, texts: list[str]) -> dict[str, Any]:
        if not texts:
            raise LLMError("Embedding input is empty.", status_code=400)
        embeddings: list[list[float]] = []
        model_name = model
        batch_size = 64
        for offset in range(0, len(texts), batch_size):
            batch = texts[offset : offset + batch_size]
            payload = await _request_json(
                "POST",
                f"{self.base_url}/embeddings",
                headers=self._headers(),
                json={"model": model, "input": batch},
            )
            data = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(data, list) or not data:
                raise LLMError(f"{self.label} returned an empty embedding.")
            ordered = sorted(
                (item for item in data if isinstance(item, dict)),
                key=lambda item: int(item.get("index", 0)),
            )
            if len(ordered) != len(batch):
                raise LLMError(
                    f"{self.label} returned {len(ordered)} embeddings for {len(batch)} inputs."
                )
            for item in ordered:
                raw = item.get("embedding")
                if not isinstance(raw, list) or not raw:
                    raise LLMError(f"{self.label} returned an empty embedding.")
                embeddings.append([float(value) for value in raw])
            if isinstance(payload, dict) and payload.get("model"):
                model_name = str(payload["model"])
        dimensions = len(embeddings[0]) if embeddings else 0
        if any(len(vector) != dimensions for vector in embeddings):
            raise LLMError(f"{self.label} returned embeddings with mixed dimensions.")
        return {
            "model": model_name,
            "dimensions": dimensions,
            "embeddings": embeddings,
        }


class AnthropicProvider:
    id = "anthropic"
    label = "Anthropic"

    def __init__(self) -> None:
        self.base_url = ANTHROPIC_BASE_URL.rstrip("/")
        self.api_key = ANTHROPIC_API_KEY

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise LLMError(
                "Anthropic is not configured. Add ANTHROPIC_API_KEY on the server.",
                status_code=503,
            )
        return {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def list_models(self) -> list[dict[str, Any]]:
        payload = await _request_json(
            "GET",
            f"{self.base_url}/v1/models",
            headers=self._headers(),
        )
        items = payload.get("data") if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            raise LLMError("Anthropic returned an unexpected models list.")
        models: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("id") or "").strip()
            if not model_id:
                continue
            models.append(
                {
                    "id": model_id,
                    "kind": "chat",
                    "owned_by": "anthropic",
                }
            )
        models.sort(key=lambda row: row["id"].lower())
        return models

    async def chat(
        self,
        *,
        model: str,
        prompt: str,
        reasoning_effort: str,
        json_schema: dict[str, Any] | None = None,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        del reasoning_effort
        user = prompt
        if json_schema:
            user = (
                prompt
                + "\n\nRespond with JSON only that matches this schema:\n"
                + json.dumps(json_schema.get("schema") or json_schema)
            )
        messages: list[dict[str, str]] = [{"role": "user", "content": user}]
        payload_body: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens or 1024,
            "messages": messages,
        }
        if system and system.strip():
            payload_body["system"] = system.strip()
        payload = await _request_json(
            "POST",
            f"{self.base_url}/v1/messages",
            headers=self._headers(),
            json=payload_body,
        )
        content = ""
        if isinstance(payload, dict):
            blocks = payload.get("content")
            if isinstance(blocks, list):
                parts: list[str] = []
                for block in blocks:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text")
                        if isinstance(text, str):
                            parts.append(text)
                content = "\n".join(parts)
        return {
            "model": str(payload.get("model") if isinstance(payload, dict) else model),
            "content": content.strip(),
        }

    async def embed(self, *, model: str, text: str) -> dict[str, Any]:
        del model, text
        raise LLMError(
            "Anthropic has no embeddings API. Embeddings use Stanford Gateway or OpenAI.",
            status_code=400,
        )

    async def embed_many(self, *, model: str, texts: list[str]) -> dict[str, Any]:
        del model, texts
        raise LLMError(
            "Anthropic has no embeddings API. Embeddings use Stanford Gateway or OpenAI.",
            status_code=400,
        )


class OllamaProvider:
    id = "ollama"
    label = "Ollama"

    async def list_models(self) -> list[dict[str, Any]]:
        raise LLMError(
            "Ollama is a placeholder fallback and is not wired yet.",
            status_code=501,
        )

    async def chat(
        self,
        *,
        model: str,
        prompt: str,
        reasoning_effort: str,
    ) -> dict[str, Any]:
        del model, prompt, reasoning_effort
        raise LLMError(
            "Ollama is a placeholder fallback and is not wired yet.",
            status_code=501,
        )

    async def embed(self, *, model: str, text: str) -> dict[str, Any]:
        del model, text
        raise LLMError(
            "Ollama is a placeholder fallback and is not wired yet.",
            status_code=501,
        )

    async def embed_many(self, *, model: str, texts: list[str]) -> dict[str, Any]:
        del model, texts
        raise LLMError(
            "Ollama is a placeholder fallback and is not wired yet.",
            status_code=501,
        )


def configured_providers() -> dict[str, bool]:
    return {
        "stanford": bool(AI_GATEWAY_API_KEY),
        "openai": bool(OPENAI_API_KEY),
        "anthropic": bool(ANTHROPIC_API_KEY),
        "ollama": False,
    }


def get_provider(provider_id: str) -> OpenAICompatibleProvider | AnthropicProvider | OllamaProvider:
    if provider_id == "openai":
        return OpenAICompatibleProvider(
            "openai",
            OPENAI_BASE_URL,
            OPENAI_API_KEY,
            "OpenAI",
        )
    if provider_id == "anthropic":
        return AnthropicProvider()
    if provider_id == "ollama":
        return OllamaProvider()
    return OpenAICompatibleProvider(
        "stanford",
        AI_GATEWAY_BASE_URL,
        AI_GATEWAY_API_KEY,
        "Stanford Gateway",
    )

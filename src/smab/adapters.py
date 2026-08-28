from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any
from uuid import uuid4

from .models import ModelTurn, ToolCall


class AdapterError(RuntimeError):
    pass


class ModelAdapter(ABC):
    @abstractmethod
    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ModelTurn:
        raise NotImplementedError


class OpenAICompatibleAdapter(ModelAdapter):
    """Minimal client for OpenAI-compatible chat-completions endpoints.

    ``tool_format=native`` sends the regular ``tools`` field. ``json`` instead
    presents the schemas in the system prompt, which is useful for tiny models
    trained to emit constrained JSON but not native function-call tokens.
    """

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        tool_format: str = "native",
        temperature: float = 0.0,
        max_tokens: int = 512,
        timeout: float = 120.0,
        extra_body: dict[str, Any] | None = None,
    ) -> None:
        if tool_format not in {"native", "json"}:
            raise ValueError("tool_format must be 'native' or 'json'")
        self.url = _chat_completions_url(base_url)
        self.model = model
        self.api_key = api_key
        self.tool_format = tool_format
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.extra_body = extra_body or {}

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ModelTurn:
        wire_messages = messages
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": wire_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.tool_format == "native":
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        else:
            wire_messages = _json_protocol_messages(messages, tools)
            payload["messages"] = wire_messages
            payload["response_format"] = {"type": "json_object"}
        payload.update(self.extra_body)

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise AdapterError(f"HTTP {exc.code} from model endpoint: {body[:1000]}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise AdapterError(f"Model endpoint request failed: {exc}") from exc
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)

        try:
            message = raw["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AdapterError(f"Unexpected endpoint response: {str(raw)[:1000]}") from exc
        if self.tool_format == "native":
            turn = _parse_native_turn(message)
        else:
            turn = _parse_json_turn(message.get("content"))
        parser_metadata = turn.raw
        turn.raw = {**raw, "_smab": parser_metadata} if parser_metadata else raw
        turn.usage = {**raw.get("usage", {}), "latency_ms": elapsed_ms}
        return turn


def _chat_completions_url(base_url: str) -> str:
    clean = base_url.rstrip("/")
    if clean.endswith("/chat/completions"):
        return clean
    if clean.endswith("/v1"):
        return f"{clean}/chat/completions"
    return f"{clean}/v1/chat/completions"


def _parse_native_turn(message: dict[str, Any]) -> ModelTurn:
    calls: list[ToolCall] = []
    for raw_call in message.get("tool_calls") or []:
        function = raw_call.get("function", {})
        raw_arguments = function.get("arguments", "{}")
        parse_error = None
        try:
            arguments = raw_arguments if isinstance(raw_arguments, dict) else json.loads(raw_arguments)
            if not isinstance(arguments, dict):
                raise TypeError("arguments are not a JSON object")
        except (json.JSONDecodeError, TypeError) as exc:
            arguments = {}
            parse_error = str(exc)
        calls.append(
            ToolCall(
                id=raw_call.get("id") or f"call_{uuid4().hex[:12]}",
                name=str(function.get("name", "")),
                arguments=arguments,
                parse_error=parse_error,
            )
        )
    return ModelTurn(content=message.get("content"), tool_calls=calls)


def _parse_json_turn(content: str | None) -> ModelTurn:
    if not content:
        return ModelTurn(content="", raw={"protocol_error": "empty response"})
    try:
        payload = _extract_json_object(content)
    except (json.JSONDecodeError, ValueError) as exc:
        return ModelTurn(content=content, raw={"protocol_error": str(exc)})
    if "final" in payload:
        return ModelTurn(content=str(payload["final"]))
    calls: list[ToolCall] = []
    raw_calls = payload.get("tool_calls", [])
    if isinstance(raw_calls, dict):
        raw_calls = [raw_calls]
    for item in raw_calls if isinstance(raw_calls, list) else []:
        if not isinstance(item, dict):
            continue
        arguments = item.get("arguments", {})
        parse_error = None
        if not isinstance(arguments, dict):
            parse_error = "arguments are not a JSON object"
            arguments = {}
        calls.append(
            ToolCall(
                id=f"call_{uuid4().hex[:12]}",
                name=str(item.get("name", "")),
                arguments=arguments,
                parse_error=parse_error,
            )
        )
    if not calls:
        return ModelTurn(
            content=content,
            raw={"protocol_error": "JSON object contains neither final nor valid tool_calls"},
        )
    return ModelTurn(content=None, tool_calls=calls)


def _extract_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("response contains no valid JSON object")


def _json_protocol_messages(
    messages: list[dict[str, Any]], tools: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    protocol = (
        "You are a tool-using assistant. Reply with exactly one JSON object and no markdown. "
        "To call tools: {\"tool_calls\":[{\"name\":\"tool_name\",\"arguments\":{...}}]}. "
        "When the task is complete or no tool is appropriate: {\"final\":\"answer\"}. "
        "Never invent a tool or parameter. Available tool schemas:\n"
        + json.dumps(tools, ensure_ascii=False, separators=(",", ":"))
    )
    converted: list[dict[str, Any]] = [{"role": "system", "content": protocol}]
    for message in messages:
        role = message.get("role")
        if role == "tool":
            converted.append(
                {
                    "role": "user",
                    "content": (
                        f"TOOL_RESULT name={message.get('name', '')} "
                        f"call_id={message.get('tool_call_id', '')}: {message.get('content', '')}"
                    ),
                }
            )
        elif role == "assistant" and message.get("tool_calls"):
            calls = [
                {
                    "name": item.get("function", {}).get("name", ""),
                    "arguments": _safe_json_loads(item.get("function", {}).get("arguments", "{}")),
                }
                for item in message["tool_calls"]
            ]
            converted.append(
                {"role": "assistant", "content": json.dumps({"tool_calls": calls}, ensure_ascii=False)}
            )
        else:
            converted.append({"role": role, "content": message.get("content") or ""})
    return converted


def _safe_json_loads(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}

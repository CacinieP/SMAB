from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]
    id: str = ""
    parse_error: str | None = None


@dataclass(slots=True)
class ModelTurn:
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BenchmarkCase:
    id: str
    category: str
    split: str
    prompt: str
    tools: list[dict[str, Any]]
    tool_behaviors: dict[str, Any]
    expected: dict[str, Any]
    dimensions: list[str]
    max_turns: int = 8
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any], catalog: dict[str, Any]) -> "BenchmarkCase":
        tool_names = data.get("tools", [])
        tools = [catalog[name] for name in tool_names]
        known = {
            "id",
            "category",
            "split",
            "prompt",
            "tools",
            "tool_behaviors",
            "expected",
            "dimensions",
            "max_turns",
            "tags",
        }
        return cls(
            id=data["id"],
            category=data["category"],
            split=data.get("split", "core"),
            prompt=data["prompt"],
            tools=tools,
            tool_behaviors=data.get("tool_behaviors", {}),
            expected=data.get("expected", {}),
            dimensions=data.get("dimensions", [data["category"]]),
            max_turns=int(data.get("max_turns", 8)),
            tags=list(data.get("tags", [])),
            metadata={key: value for key, value in data.items() if key not in known},
        )


@dataclass(slots=True)
class TraceEvent:
    turn: int
    requested_name: str
    name: str
    arguments: dict[str, Any]
    output: Any = None
    error: str | None = None
    parse_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn": self.turn,
            "requested_name": self.requested_name,
            "name": self.name,
            "arguments": self.arguments,
            "output": self.output,
            "error": self.error,
            "parse_error": self.parse_error,
        }

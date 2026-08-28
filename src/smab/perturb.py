from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class PerturbedTools:
    tools: list[dict[str, Any]]
    exposed_to_canonical: dict[str, str]


def perturb_tools(tools: list[dict[str, Any]], variant: str, seed: int = 0) -> PerturbedTools:
    if variant not in {"original", "shuffled", "aliased"}:
        raise ValueError(f"Unknown schema variant: {variant}")
    transformed = copy.deepcopy(tools)
    mapping: dict[str, str] = {}
    if variant == "aliased":
        for index, tool in enumerate(transformed, start=1):
            canonical = tool["function"]["name"]
            exposed = f"fn_{index:02d}"
            mapping[exposed] = canonical
            tool["function"]["name"] = exposed
    else:
        mapping = {tool["function"]["name"]: tool["function"]["name"] for tool in transformed}
    if variant == "shuffled":
        random.Random(seed).shuffle(transformed)
    return PerturbedTools(tools=transformed, exposed_to_canonical=mapping)

"""The only door to Gemini. Every call is cached, schema-validated, and has a deterministic fallback.

GEMINI_MODE
  live    cache hit -> cached answer; miss -> Gemini on Vertex AI, validated, written to cache
  replay  cache hit -> cached answer; miss -> deterministic fallback (never touches the network)
  off     always the deterministic fallback

Cache: cache/gemini/<task>/<sha256>.json, keyed by task + prompt version + inputs (images by content hash).
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from .settings import get_settings

log = logging.getLogger("wiw.gemini")
T = TypeVar("T", bound=BaseModel)


@dataclass
class Image:
    data: bytes
    mime_type: str = "image/png"


Part = str | Image


@dataclass
class Result(Generic[T]):
    value: T
    source: str  # live | cache | fallback
    error: str | None = None


def _part_key(p: Part) -> Any:
    if isinstance(p, Image):
        return {"image_sha256": hashlib.sha256(p.data).hexdigest()}
    return p


def cache_key(task: str, version: str, system: str | None, parts: list[Part], extra: Any = None) -> str:
    blob = json.dumps({"task": task, "v": version, "system": system, "parts": [_part_key(p) for p in parts],
                       "extra": extra}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def _cache_path(task: str, key: str):  # noqa: ANN202
    return get_settings().cache_dir / task / f"{key}.json"


def cache_get(task: str, key: str) -> Any | None:
    p = _cache_path(task, key)
    if p.is_file():
        try:
            return json.loads(p.read_text())["response"]
        except (json.JSONDecodeError, KeyError):
            return None
    return None


def cache_put(task: str, key: str, response: Any, summary: str = "") -> None:
    p = _cache_path(task, key)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"task": task, "model": get_settings().gemini_model, "summary": summary[:200],
                             "created": time.strftime("%Y-%m-%dT%H:%M:%S"), "response": response}, indent=1))


@lru_cache(maxsize=1)
def client():
    from google import genai

    from .gcp_auth import credentials

    s = get_settings()
    return genai.Client(vertexai=True, project=s.project, location=s.gemini_location, credentials=credentials())


_DROP = {"title", "default", "maxLength", "minLength", "maxItems", "minItems", "minimum", "maximum",
         "exclusiveMinimum", "exclusiveMaximum"}


def gemini_schema(model: type[BaseModel]) -> dict:
    """Pydantic JSON schema in the subset Vertex accepts: refs inlined, bounds/titles/defaults dropped.
    The dropped constraints are still enforced by pydantic validation on the response."""
    import copy

    full = model.model_json_schema()
    defs = full.get("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(copy.deepcopy(defs[node["$ref"].split("/")[-1]]))
            return {k: walk(v) for k, v in node.items() if k not in _DROP and k != "$defs"}
        if isinstance(node, list):
            return [walk(x) for x in node]
        return node

    return walk(full)


def _to_parts(parts: list[Part]) -> list:
    from google.genai import types

    return [types.Part.from_bytes(data=p.data, mime_type=p.mime_type) if isinstance(p, Image) else p for p in parts]


def generate_json(task: str, *, version: str, parts: list[Part], schema: type[T], fallback: Callable[[], T],
                  system: str | None = None, temperature: float = 0.2,
                  validate: Callable[[T], T] | None = None) -> Result[T]:
    """Structured JSON generation. `validate` may repair or raise ValueError for domain checks."""
    s = get_settings()
    key = cache_key(task, version, system, parts)

    def check(raw: Any) -> T:
        v = schema.model_validate(raw)
        return validate(v) if validate else v

    if s.gemini_mode != "off":
        cached = cache_get(task, key)
        if cached is not None:
            try:
                return Result(check(cached), "cache")
            except (ValidationError, ValueError) as e:
                log.warning("cached %s failed validation: %s", task, e)
    if s.gemini_mode == "live":
        try:
            from google.genai import types

            resp = client().models.generate_content(
                model=s.gemini_model, contents=_to_parts(parts),
                config=types.GenerateContentConfig(
                    system_instruction=system, temperature=temperature, response_mime_type="application/json",
                    response_json_schema=gemini_schema(schema)))
            raw = json.loads(resp.text)
            value = check(raw)
            cache_put(task, key, raw, summary=next((p for p in parts if isinstance(p, str)), ""))
            return Result(value, "live")
        except Exception as e:  # noqa: BLE001  (network, quota, JSON, schema, domain validation)
            log.warning("gemini %s failed, using fallback: %s", task, e)
            return Result(fallback(), "fallback", str(e)[:300])
    return Result(fallback(), "fallback")


# ------------------------------------------------------------------ function calling (stylist chat)

@dataclass
class AgentResult:
    text: str
    trace: list[dict]   # serializable: model calls + tool responses of this turn
    source: str         # live | cache | fallback


def run_agent(task: str, *, version: str, system: str, history: list[dict], tools: list[dict],
              execute: Callable[[str, dict], dict], fallback: Callable[[list[dict]], AgentResult],
              max_steps: int = 5) -> AgentResult:
    """Function-calling loop. history: [{"role": "user"|"model", "text": str}] (text only; last is the user turn).

    live   : always calls Gemini (raw response contents are kept inside the turn so Gemini 3 thought signatures
             survive), and caches every step keyed by the serializable trace so far.
    replay : replays cached steps, executing tools locally; on a miss the deterministic `fallback` finishes the turn
             (it receives the trace so far, so tools that already ran are not re-run).
    off    : fallback only.
    """
    s = get_settings()
    tool_names = sorted(t["name"] for t in tools)
    trace: list[dict] = []
    if s.gemini_mode == "off":
        return fallback(trace)
    if s.gemini_mode == "live":
        try:
            return _run_live(task, version, system, history, tools, execute, max_steps, tool_names)
        except Exception as e:  # noqa: BLE001
            log.warning("gemini agent failed, using fallback: %s", e)
            return fallback(trace)
    for _ in range(max_steps):
        key = cache_key(task, version, system, [json.dumps(history + trace, sort_keys=True, default=str)], tool_names)
        step = cache_get(task, key)
        if step is None:
            return fallback(trace)
        if not step.get("calls"):
            return AgentResult(step.get("text", ""), trace, "cache")
        trace.append({"role": "model", "calls": step["calls"]})
        for c in step["calls"]:
            trace.append({"role": "tool", "name": c["name"], "response": execute(c["name"], c["args"])})
    return fallback(trace)


def _run_live(task, version, system, history, tools, execute, max_steps, tool_names) -> AgentResult:  # noqa: ANN001
    from google.genai import types

    s = get_settings()
    contents = [types.Content(role="user" if h["role"] == "user" else "model", parts=[types.Part(text=h["text"])])
                for h in history]
    decls = [types.FunctionDeclaration(name=t["name"], description=t["description"],
                                       parameters_json_schema=t["parameters"]) for t in tools]
    config = types.GenerateContentConfig(
        system_instruction=system, temperature=0.3, tools=[types.Tool(function_declarations=decls)],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
    trace: list[dict] = []
    for _ in range(max_steps):
        key = cache_key(task, version, system, [json.dumps(history + trace, sort_keys=True, default=str)], tool_names)
        resp = client().models.generate_content(model=s.gemini_model, contents=contents, config=config)
        calls = [{"name": fc.name, "args": _plain(fc.args or {})} for fc in (resp.function_calls or [])]
        if not calls:
            text = resp.text or ""
            cache_put(task, key, {"text": text, "calls": []}, summary=history[-1]["text"])
            return AgentResult(text, trace, "live")
        cache_put(task, key, {"text": "", "calls": calls}, summary=history[-1]["text"])
        contents.append(resp.candidates[0].content)  # keeps thought signatures
        trace.append({"role": "model", "calls": calls})
        parts = []
        for c in calls:
            out = execute(c["name"], c["args"])
            trace.append({"role": "tool", "name": c["name"], "response": out})
            parts.append(types.Part(function_response=types.FunctionResponse(name=c["name"], response=out)))
        contents.append(types.Content(role="user", parts=parts))
    raise RuntimeError("agent exceeded max steps")


def _plain(v: Any) -> Any:
    """Convert proto/Map values from function call args into plain JSON types."""
    if isinstance(v, dict) or hasattr(v, "items"):
        return {str(k): _plain(x) for k, x in dict(v).items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v

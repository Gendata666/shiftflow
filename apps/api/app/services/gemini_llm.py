"""
Gemini provider — free-tier pilot implementation of the copilot's two AI
boundaries (NL→spec parsing, streaming tool chat). Mirrors the Claude
provider's contracts exactly: the same SpecDraft/SpecUpdateDraft schemas,
the same chat event shapes, the same deterministic tool executor.

Token economy is identical by design: the model only reads compact spec
summaries and only writes rules; solving/verification stay in CP-SAT.

Model comes from settings.GEMINI_MODEL (default gemini-3.5-flash — free
tier ~10 RPM / 1,500 req/day, plenty for a pilot; switch to
gemini-3.1-pro-preview when billing is attached — config change only).
"""

from __future__ import annotations

import json
from typing import AsyncIterator, Callable, Optional, Type, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.core.config import settings

T = TypeVar("T", bound=BaseModel)

_client: Optional[genai.Client] = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


# ─── Structured parsing (NL brief → draft) ───────────────────────────────────

async def parse_structured(system: str, user: str, schema: Type[T]) -> T:
    """One Gemini call constrained to `schema`. Native response_schema
    (constrained decoding) first; if the API rejects our nested
    discriminated-union schema, fall back to schema-in-prompt + local
    validation. Both paths end in Pydantic validation — a malformed reply
    fails loudly here, never in the solver."""
    client = _get_client()
    try:
        response = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0,
            ),
        )
        parsed = response.parsed
        if isinstance(parsed, schema):
            return parsed
        return schema.model_validate_json(response.text)
    except Exception:
        # Fallback: schema embedded in the prompt, plain JSON mode.
        response = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=(
                f"{user}\n\nReturn ONLY a JSON object valid against this JSON Schema:\n"
                f"{json.dumps(schema.model_json_schema(), ensure_ascii=False)}"
            ),
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                temperature=0,
            ),
        )
        return schema.model_validate_json(response.text)


# ─── Streaming tool chat ─────────────────────────────────────────────────────

def _to_function_declarations(chat_tools: list[dict]) -> list[types.Tool]:
    """Convert the provider-neutral CHAT_TOOLS definitions (Anthropic-style
    dicts with JSON-schema input) to Gemini function declarations."""
    decls = []
    for tool in chat_tools:
        schema = dict(tool["input_schema"])
        schema.pop("additionalProperties", None)  # not accepted by Gemini
        decls.append(
            types.FunctionDeclaration(
                name=tool["name"],
                description=tool["description"],
                parameters_json_schema=schema,
            )
        )
    return [types.Tool(function_declarations=decls)]


async def stream_chat_turn(
    system: str,
    history: list[types.Content],
    user_message: str,
    chat_tools: list[dict],
    run_tool: Callable[[str, dict], "types.Awaitable[str] | str"],
) -> AsyncIterator[dict]:
    """Drive one manager turn against Gemini with function calling.
    Yields the same event dicts as the Claude path:
      {"type": "text", "text"} | {"type": "tool", "name"} | {"type": "done"}.
    Tool side-effect events (spec_updated / report) are emitted by the
    caller, which owns the tool executor. `history` is mutated in place so
    the caller can persist it."""
    client = _get_client()
    tools = _to_function_declarations(chat_tools)
    history.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

    while True:
        stream = await client.aio.models.generate_content_stream(
            model=settings.GEMINI_MODEL,
            contents=history,
            config=types.GenerateContentConfig(
                system_instruction=system,
                tools=tools,
                temperature=0.2,
            ),
        )

        text_parts: list[str] = []
        function_calls: list[types.FunctionCall] = []
        async for chunk in stream:
            for cand in chunk.candidates or []:
                for part in (cand.content.parts if cand.content else []) or []:
                    if part.text:
                        text_parts.append(part.text)
                        yield {"type": "text", "text": part.text}
                    if part.function_call:
                        function_calls.append(part.function_call)

        model_parts: list[types.Part] = []
        if text_parts:
            model_parts.append(types.Part(text="".join(text_parts)))
        for fc in function_calls:
            model_parts.append(types.Part(function_call=fc))
        if model_parts:
            history.append(types.Content(role="model", parts=model_parts))

        if not function_calls:
            break

        response_parts: list[types.Part] = []
        for fc in function_calls:
            yield {"type": "tool", "name": fc.name}
            result = run_tool(fc.name, dict(fc.args or {}))
            if hasattr(result, "__await__"):
                result = await result
            # Internal marker so the caller can emit side-effect events
            # (spec_updated / report) after the tool actually ran.
            yield {"type": "tool_done", "name": fc.name}
            response_parts.append(
                types.Part.from_function_response(name=fc.name, response={"result": result})
            )
        history.append(types.Content(role="user", parts=response_parts))

    yield {"type": "done"}

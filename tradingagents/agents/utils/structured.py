"""Shared helpers for invoking agents with required structured output.

The Portfolio Manager, Trader, Research Manager, and Sentiment Analyst follow the same
canonical pattern:

1. At agent creation, wrap the LLM with ``with_structured_output(Schema)``
   so the model returns a typed Pydantic instance. Providers that do not
   support structured output are rejected.
2. At invocation, run the structured call and render the result back to
   markdown. Provider, parsing, and validation failures propagate so an
   analysis cannot silently continue without the schema contract.

Centralising the pattern here keeps the agent factories small and gives all
structured agents the same strict failure behavior.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

# Schema-only structured output binds exactly one tool (the schema itself), so a
# model that reaches for a search tool emits an unknown tool call and the
# structured invocation fails. Agents on this path state the constraint
# explicitly rather than relying on the binding alone (#1130).
NO_EXTERNAL_TOOLS = (
    "Use only the evidence provided in this prompt. Do not call external tools "
    "or search the web; if something is missing, say so explicitly."
)


def bind_structured(llm: Any, schema: type[T], agent_name: str) -> Any:
    """Bind a required structured-output schema, raising clearly if unsupported."""
    try:
        return llm.with_structured_output(schema)
    except (NotImplementedError, AttributeError) as exc:
        raise RuntimeError(
            f"{agent_name} requires structured output, but the selected model "
            "or provider does not support it. Choose a model with structured-output support."
        ) from exc


def invoke_structured(
    structured_llm: Any,
    prompt: Any,
    render: Callable[[T], str],
    agent_name: str,
) -> str:
    """Run a required structured call and render its validated result to markdown.

    ``prompt`` is whatever the underlying LLM accepts (a string for chat
    invocations, a list of message dicts for chat models that take that
    shape).
    """
    result = structured_llm.invoke(prompt)
    if result is None:
        raise ValueError(f"{agent_name}: structured output returned no parsed result")
    return render(result)

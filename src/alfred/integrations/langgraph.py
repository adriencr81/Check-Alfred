"""Native LangGraph / LangChain connector: attach a handler, get an Alfred trace.

`AlfredCallbackHandler` is a LangChain `BaseCallbackHandler`. Attach it to a
LangGraph (or any LangChain runnable) invocation and every model call and tool
call becomes a span in the exact OTLP JSON shape `alfred.trace.ingest` reads —
no manual instrumentation.

    from alfred.instrument import AgentTracer
    from alfred.integrations.langgraph import AlfredCallbackHandler

    tracer = AgentTracer(agent="support-bot", traces_dir="traces")
    graph.invoke(inputs, config={"callbacks": [AlfredCallbackHandler(tracer)]})
    tracer.flush()  # → traces/support-bot-<ts>.json  → alfred watch

The design decision that makes this safe (docs/adr/0014): LangChain callbacks
are event-driven (start/end pairs keyed by ``run_id``) while `AgentTracer`
exposes context managers. The handler bridges the two by driving the proven
`AgentTracer` context managers manually — `__enter__` on a ``*_start`` event,
`__exit__` on the matching ``*_end``. It never re-emits attribute keys itself,
so the "every fact anchored to a real trace event" guarantee (CLAUDE.md rule
D5) is inherited, not re-implemented.

Requires the optional extra: ``pip install alfred-ai[langgraph]``.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any
from uuid import UUID

from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from alfred.instrument import AgentTracer
from alfred.instrument.tracer import LLMCall, ToolCall

_LLMSpan = tuple[AbstractContextManager[LLMCall], LLMCall]
_ToolSpan = tuple[AbstractContextManager[ToolCall], ToolCall]


class AlfredCallbackHandler(BaseCallbackHandler):
    """Records a LangGraph/LangChain run as an Alfred OTLP trace.

    One session spans the root graph run (`invoke_agent`); model calls (`chat`)
    and tool calls (`execute_tool`) are its children. Successive invocations of
    the same handler accumulate in the tracer's payload, exactly like manual
    `AgentTracer` sessions.

    In production the handler never raises into the graph — LangChain swallows
    callback errors unless `raise_error` is set. Pass ``raise_errors=True`` in
    tests so a mapping bug fails loudly instead of silently dropping spans.
    """

    def __init__(
        self,
        tracer: AgentTracer,
        *,
        task_name: str = "graph",
        raise_errors: bool = False,
    ) -> None:
        self._tracer = tracer
        self._task_name = task_name
        self.raise_error = raise_errors
        self._session_run: UUID | None = None
        self._session_cm: AbstractContextManager[None] | None = None
        self._llm: dict[UUID, _LLMSpan] = {}
        self._tool: dict[UUID, _ToolSpan] = {}

    # -- Session: bounded by the root chain/graph run --------------------------

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        if parent_run_id is None and self._session_run is None:
            name = (serialized or {}).get("name") or self._task_name
            cm = self._tracer.session(task_name=name, task_id=str(run_id))
            cm.__enter__()
            self._session_cm = cm
            self._session_run = run_id

    def on_chain_end(self, outputs: dict[str, Any], *, run_id: UUID, **kwargs: Any) -> None:
        self._end_session(run_id)

    def on_chain_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._end_session(run_id)

    def _end_session(self, run_id: UUID) -> None:
        if run_id == self._session_run and self._session_cm is not None:
            self._session_cm.__exit__(None, None, None)
            self._session_cm = None
            self._session_run = None

    # -- LLM spans -------------------------------------------------------------

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self._begin_llm(serialized, run_id, kwargs)

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self._begin_llm(serialized, run_id, kwargs)

    def _begin_llm(self, serialized: dict[str, Any], run_id: UUID, kwargs: dict[str, Any]) -> None:
        if self._session_run is None:
            return
        cm = self._tracer.llm_call(model=_model_name(serialized, kwargs))
        handle = cm.__enter__()
        self._llm[run_id] = (cm, handle)

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        entry = self._llm.pop(run_id, None)
        if entry is None:
            return
        cm, handle = entry
        usage = _usage(response)
        if usage is not None:
            input_tokens, output_tokens, model = usage
            handle.record_usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                response_model=model,
            )
        cm.__exit__(None, None, None)

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        entry = self._llm.pop(run_id, None)
        if entry is not None:
            entry[0].__exit__(None, None, None)

    # -- Tool spans ------------------------------------------------------------

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        if self._session_run is None:
            return
        name = (serialized or {}).get("name") or "tool"
        arguments = inputs if isinstance(inputs, dict) else None
        cm = self._tracer.tool_call(name, arguments)
        handle = cm.__enter__()
        self._tool[run_id] = (cm, handle)

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        self._end_tool(run_id, "ok")

    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._end_tool(run_id, "error")

    def _end_tool(self, run_id: UUID, status: str) -> None:
        entry = self._tool.pop(run_id, None)
        if entry is not None:
            cm, handle = entry
            handle.record_result(status=status)
            cm.__exit__(None, None, None)


def _model_name(serialized: dict[str, Any] | None, kwargs: dict[str, Any]) -> str | None:
    """Best-effort model id from the callback payload; None if the run omits it."""
    params = kwargs.get("invocation_params")
    if isinstance(params, dict):
        for key in ("model", "model_name", "model_id"):
            value = params.get(key)
            if isinstance(value, str) and value:
                return value
    metadata = kwargs.get("metadata")
    if isinstance(metadata, dict):
        value = metadata.get("ls_model_name")
        if isinstance(value, str) and value:
            return value
    if isinstance(serialized, dict):
        kwargs_field = serialized.get("kwargs")
        if isinstance(kwargs_field, dict):
            for key in ("model", "model_name"):
                value = kwargs_field.get(key)
                if isinstance(value, str) and value:
                    return value
    return None


def _usage(response: LLMResult) -> tuple[int, int, str | None] | None:
    """(input_tokens, output_tokens, model) from the response, or None if absent.

    Prefers the per-message ``usage_metadata`` carried by chat models
    (langchain-core 0.2+/1.x), falling back to the aggregated ``token_usage`` /
    ``usage`` block in ``llm_output`` that older/text LLMs report.
    """
    for generation_list in response.generations:
        for generation in generation_list:
            message = getattr(generation, "message", None)
            metadata = getattr(message, "usage_metadata", None)
            if (
                isinstance(metadata, dict)
                and isinstance(metadata.get("input_tokens"), int)
                and isinstance(metadata.get("output_tokens"), int)
            ):
                return metadata["input_tokens"], metadata["output_tokens"], _message_model(message)
    output = response.llm_output
    if isinstance(output, dict):
        tokens = output.get("token_usage") or output.get("usage")
        if isinstance(tokens, dict):
            input_tokens = tokens.get("prompt_tokens", tokens.get("input_tokens"))
            output_tokens = tokens.get("completion_tokens", tokens.get("output_tokens"))
            if isinstance(input_tokens, int) and isinstance(output_tokens, int):
                model = output.get("model_name")
                return input_tokens, output_tokens, model if isinstance(model, str) else None
    return None


def _message_model(message: Any) -> str | None:
    metadata = getattr(message, "response_metadata", None)
    if isinstance(metadata, dict):
        candidate = metadata.get("model_name") or metadata.get("model")
        if isinstance(candidate, str) and candidate:
            return candidate
    return None

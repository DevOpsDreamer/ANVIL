"""
Pure OpenTelemetry telemetry module (AEGIS v8).

All Omium SDK dependencies have been removed. Tracing is handled
exclusively through opentelemetry-sdk with optional OTLP export
controlled by the OTEL_EXPORTER_OTLP_ENDPOINT environment variable.

Public API (consumed by tasks.py, pipeline.py, main.py, etc.):
  - init_telemetry() -> Tracer
  - get_tracer() -> Tracer
  - trace_operation(name, attributes, kind) — context manager
  - inject_trace_context() -> dict
  - extract_trace_context(carrier) -> token
  - detach_trace_context(token)
  - OmiumShim — shared no-op class so callers can drop `import omium`
  - record_llm_attributes(span, prompt_tokens, completion_tokens, rationale)
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

from opentelemetry import trace
from opentelemetry.context import attach, detach
from opentelemetry.trace import StatusCode, Tracer
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from app.config import OTEL_EXPORTER_OTLP_ENDPOINT, SERVICE_NAME

logger = logging.getLogger(__name__)

_propagator = TraceContextTextMapPropagator()
_tracer: Optional[Tracer] = None


# ── OmiumShim — shared no-op fallback ───────────────────────────────────────
# Other modules (e.g. pipeline.py) can import this instead of duplicating
# their own shim class.  Every method is a silent no-op so decorated
# functions still execute normally when the Omium SDK is absent.

def _noop_decorator(*args, **kwargs):
    """Return a pass-through decorator."""
    def _dec(fn):
        return fn
    return _dec


class OmiumShim:
    """
    Drop-in no-op replacement for the ``omium`` module.

    Provides ``trace`` and ``checkpoint`` as no-op decorators so that
    code decorated with ``@omium.trace(...)`` or ``@omium.checkpoint(...)``
    continues to work without the real Omium package installed.
    """

    trace = staticmethod(_noop_decorator)
    checkpoint = staticmethod(_noop_decorator)

    @staticmethod
    def init(**kwargs) -> None:  # noqa: D401
        """No-op — Omium SDK is not installed."""

    @staticmethod
    def set_execution_id(_id: str) -> None:
        """No-op — Omium SDK is not installed."""


# ── Bootstrap ────────────────────────────────────────────────────────────────

def init_telemetry() -> Tracer:
    """
    Initialise OpenTelemetry tracing and return the project tracer.

    * If *OTEL_EXPORTER_OTLP_ENDPOINT* is set, spans are exported via
      OTLP/gRPC (or OTLP/HTTP depending on the installed exporter).
    * If the variable is empty, a :class:`ConsoleSpanExporter` is used
      so spans are still visible in ``stdout`` during development.
    * If anything fails, the global no-op tracer is returned and every
      subsequent operation becomes a silent pass-through.
    """
    global _tracer

    if _tracer is not None:
        return _tracer

    try:
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )

        resource = Resource.create({"service.name": SERVICE_NAME})
        provider = TracerProvider(resource=resource)

        if OTEL_EXPORTER_OTLP_ENDPOINT:
            # Attempt OTLP export — requires opentelemetry-exporter-otlp-proto-grpc
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter,
                )

                otlp_exporter = OTLPSpanExporter(
                    endpoint=OTEL_EXPORTER_OTLP_ENDPOINT,
                )
                provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
                logger.info(
                    "OTLP exporter configured -> %s (service=%s)",
                    OTEL_EXPORTER_OTLP_ENDPOINT,
                    SERVICE_NAME,
                )
            except ImportError:
                logger.warning(
                    "opentelemetry-exporter-otlp-proto-grpc not installed; "
                    "falling back to ConsoleSpanExporter"
                )
                provider.add_span_processor(
                    BatchSpanProcessor(ConsoleSpanExporter())
                )
        else:
            # No endpoint → console-only (dev mode)
            provider.add_span_processor(
                BatchSpanProcessor(ConsoleSpanExporter())
            )
            logger.info(
                "OTEL console exporter active (no OTLP endpoint, service=%s)",
                SERVICE_NAME,
            )

        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(SERVICE_NAME)

    except Exception as exc:
        logger.warning("OpenTelemetry init failed (non-fatal): %s", exc)
        # Fall back to the global no-op tracer
        _tracer = trace.get_tracer(SERVICE_NAME)

    return _tracer


def get_tracer() -> Tracer:
    """Return the initialised tracer (calls *init_telemetry* if needed)."""
    if _tracer is None:
        return init_telemetry()
    return _tracer


# ── Span helpers ─────────────────────────────────────────────────────────────

@contextmanager
def trace_operation(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL,
) -> Generator[trace.Span, None, None]:
    """
    Context manager that creates a child span, attaches attributes,
    and records exceptions automatically.
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name, kind=kind) as span:
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, v)
        try:
            yield span
        except Exception as exc:
            span.set_status(StatusCode.ERROR, str(exc))
            span.record_exception(exc)
            raise


def record_llm_attributes(
    span: trace.Span,
    prompt_tokens: int,
    completion_tokens: int,
    rationale: str = "",
) -> None:
    """
    Attach LLM-specific semantic attributes to *span*.

    Follows the emerging OpenTelemetry Semantic Conventions for GenAI
    (``gen_ai.*``).
    """
    try:
        span.set_attribute("gen_ai.usage.prompt_tokens", prompt_tokens)
        span.set_attribute("gen_ai.usage.completion_tokens", completion_tokens)
        span.set_attribute(
            "gen_ai.usage.total_tokens",
            prompt_tokens + completion_tokens,
        )
        if rationale:
            # Truncate long rationale to keep span payload reasonable
            span.set_attribute("gen_ai.rationale", rationale[:512])
    except Exception:
        # Span may be a no-op; never crash the caller
        pass


# ── W3C Trace Context propagation ───────────────────────────────────────────

def inject_trace_context() -> Dict[str, str]:
    """
    Capture the current span context into a carrier dict
    (W3C ``traceparent`` + ``tracestate``).

    The traceparent format is: ``00-{trace_id}-{span_id}-01``
    """
    carrier: Dict[str, str] = {}
    _propagator.inject(carrier)
    return carrier


def extract_trace_context(carrier: Dict[str, str]):
    """
    Restore span context from a carrier dict (e.g. received via Celery).
    Returns a token that **must** be detached when the task completes.
    """
    ctx = _propagator.extract(carrier)
    return attach(ctx)


def detach_trace_context(token) -> None:
    """Detach a previously attached trace context."""
    detach(token)

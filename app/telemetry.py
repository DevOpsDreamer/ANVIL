"""
Omium / OpenTelemetry telemetry module.

Configures the OTLP gRPC exporter to send traces to
ingest.monium.yandex.cloud:443 using the provided Omium API key.
Provides context-manager helpers for span creation and W3C
Trace Context propagation across async boundaries (Celery).
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

from opentelemetry import trace
from opentelemetry.context import attach, detach
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import StatusCode, Tracer
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from app.config import OMIUM_API_KEY, OMIUM_ENDPOINT, SERVICE_NAME

logger = logging.getLogger(__name__)

_propagator = TraceContextTextMapPropagator()
_tracer: Optional[Tracer] = None


# ── Bootstrap ────────────────────────────────────────────────────────────────

def init_telemetry() -> Tracer:
    """Initialise the global TracerProvider and return the project tracer."""
    global _tracer
    if _tracer is not None:
        return _tracer

    resource = Resource.create({"service.name": SERVICE_NAME})

    exporter = OTLPSpanExporter(
        endpoint=OMIUM_ENDPOINT,
        headers=(("authorization", f"Bearer {OMIUM_API_KEY}"),),
        insecure=False,
    )

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    _tracer = trace.get_tracer(SERVICE_NAME)
    logger.info(
        "Omium telemetry initialised → %s (service=%s)", OMIUM_ENDPOINT, SERVICE_NAME
    )
    return _tracer


def get_tracer() -> Tracer:
    """Return the initialised tracer (calls init_telemetry if needed)."""
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


# ── W3C Trace Context propagation across Celery ─────────────────────────────

def inject_trace_context() -> Dict[str, str]:
    """
    Capture the current span context into a carrier dict
    (W3C traceparent + tracestate) for embedding in Celery task metadata.
    """
    carrier: Dict[str, str] = {}
    _propagator.inject(carrier)
    return carrier


def extract_trace_context(carrier: Dict[str, str]):
    """
    Restore span context from a carrier dict received via Celery.
    Returns a token that must be detached when the task completes.
    """
    ctx = _propagator.extract(carrier)
    return attach(ctx)


def detach_trace_context(token) -> None:
    """Detach a previously attached trace context."""
    detach(token)

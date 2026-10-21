"""Optional tracing. When OTEL_EXPORTER_OTLP_ENDPOINT is set and the `otel` extra is installed,
every agent run, model request and tool call is exported as OpenTelemetry spans (Pydantic AI's
built-in instrumentation, GenAI semantic conventions). Works with Arize Phoenix, Langfuse,
Jaeger or any OTLP backend. See docs/11-evals-and-observability.md.
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)
_done = False


def setup_tracing() -> bool:
    global _done
    if _done or not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return _done
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from pydantic_ai import Agent, InstrumentationSettings
    except ImportError:
        log.warning("OTEL_EXPORTER_OTLP_ENDPOINT is set but the 'otel' extra is not installed")
        return False
    provider = TracerProvider(resource=Resource.create({"service.name": os.environ.get("OTEL_SERVICE_NAME", "rebo")}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    # Prompts and results contain business data: keep content out of traces unless asked for.
    include = os.environ.get("REBO_TRACE_CONTENT", "false").lower() == "true"
    Agent.instrument_all(InstrumentationSettings(tracer_provider=provider, include_content=include,
                                                 include_binary_content=False))
    _done = True
    return True

"""Tracing. Every question is one `rebo.ask` span; the agent run, model requests and tool calls nest
under it (Pydantic AI's instrumentation, GenAI semantic conventions). Exported over OTLP to
OTEL_EXPORTER_OTLP_ENDPOINT, or, when that is not set, to Phoenix on 127.0.0.1:6006 if it answers
(`docker compose up -d phoenix`), so local development is traced by default. Works with any OTLP
backend. See docs/11-evals-and-observability.md.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager

log = logging.getLogger(__name__)
_done = False


PHOENIX_DEFAULT = "http://127.0.0.1:6006"


def phoenix_url() -> str | None:
    """Where traces can be opened: PHOENIX_URL, else the OTLP endpoint when it is Phoenix's, else None."""
    url = os.environ.get("PHOENIX_URL") or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or ""
    return url.rstrip("/") or None


def _phoenix_answers(url: str) -> bool:
    import urllib.request
    try:
        urllib.request.urlopen(url, timeout=0.3)
        return True
    except Exception:
        return False


def setup_tracing() -> bool:
    global _done
    if _done:
        return _done
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        if os.environ.get("REBO_TRACING", "auto") == "off" or not _phoenix_answers(PHOENIX_DEFAULT):
            return False
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = PHOENIX_DEFAULT  # local Phoenix found: trace there
        os.environ.setdefault("OTEL_RESOURCE_ATTRIBUTES", "openinference.project.name=rebo")
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


@contextmanager
def ask_span(**attributes):
    """One span per question; yields a dict that receives `trace_id` (hex) when tracing is on."""
    out: dict = {}
    try:
        from opentelemetry import trace
    except ImportError:
        yield out
        return
    with trace.get_tracer("rebo").start_as_current_span("rebo.ask") as span:
        ctx = span.get_span_context()
        if ctx.is_valid:
            out["trace_id"] = format(ctx.trace_id, "032x")
        for k, v in attributes.items():
            span.set_attribute(f"rebo.{k}", str(v))
        out["span"] = span
        yield out


def trace_link(trace_id: str) -> str | None:
    """Browser link to one trace in Phoenix: {PHOENIX_URL}/projects/{project id}/traces/{trace id}. The
    project id is looked up by name (openinference.project.name, "rebo") through Phoenix's REST API,
    reached at the OTLP endpoint; the link uses PHOENIX_URL, which the browser can open."""
    api = (os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or "").rstrip("/")
    public = (os.environ.get("PHOENIX_URL") or api).rstrip("/")
    if not api:
        return None
    attrs = dict(kv.split("=", 1) for kv in os.environ.get("OTEL_RESOURCE_ATTRIBUTES", "").split(",") if "=" in kv)
    name = attrs.get("openinference.project.name", "default")
    import httpx2
    projects = httpx2.get(f"{api}/v1/projects", timeout=3).json()["data"]
    project = next((p for p in projects if p["name"] == name), None) or next(p for p in projects if p["name"] == "default")
    return f"{public}/projects/{project['id']}/traces/{trace_id}"


def annotate_trace(trace_id: str | None, name: str, *, label: str, score: float | None = None,
                   explanation: str | None = None, kind: str = "HUMAN", identifier: str = "") -> bool:
    """Attach a verdict to a trace in Phoenix (POST /v1/trace_annotations), e.g. the asker's feedback or an
    eval's gold match, so traces can be filtered by it. Best effort: returns False when tracing is off or
    Phoenix does not answer; never raises. The same identifier updates an earlier annotation."""
    api = (os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or "").rstrip("/")
    if not trace_id or not api:
        return False
    body = {"data": [{"trace_id": trace_id, "name": name, "annotator_kind": kind, "identifier": identifier,
                      "result": {"label": label, "score": score, "explanation": explanation}}]}
    try:
        import httpx2
        httpx2.post(f"{api}/v1/trace_annotations", json=body, timeout=3).raise_for_status()
        return True
    except Exception as e:
        log.info("trace annotation %s failed: %s", name, e)
        return False

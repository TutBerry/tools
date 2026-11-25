import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased


def configure_tracing(service):
    ratio = float(os.getenv("TRACE_SAMPLE_RATIO", "0.1"))
    if not 0 <= ratio <= 1:
        raise ValueError("TRACE_SAMPLE_RATIO must be between zero and one")
    provider = TracerProvider(resource=Resource.create({"service.name": service,
        "service.version": os.getenv("APP_VERSION", "0.1.0")}),
        sampler=ParentBased(TraceIdRatioBased(ratio)))
    endpoint = os.getenv("OTLP_ENDPOINT")
    if endpoint:
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)

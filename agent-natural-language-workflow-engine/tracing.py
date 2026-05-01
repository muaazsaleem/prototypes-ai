from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor


def setup_tracing() -> trace.Tracer:
    """Configures OpenTelemetry with a console exporter and returns a tracer instance.

    Uses a SimpleSpanProcessor to ensure spans are flushed to stdout immediately
    after each operation finishes. This setup is optimized for CLI visibility
    rather than high-throughput production tracing.
    """
    # identify the service in trace logs
    resource = Resource(attributes={"service.name": "nl-workflow-engine"})
    provider = TracerProvider(resource=resource)

    # flush spans immediately to console for live feedback
    provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    return trace.get_tracer("workflow-engine")

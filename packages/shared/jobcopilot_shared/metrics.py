"""Prometheus HTTP metrics shared by every FastAPI service.

Metric names are identical across services (namespace `jobcopilot_`, e.g.
`jobcopilot_http_requests_total`); the service is identified by the Prometheus
scrape `job` label, per the one-metric-name-many-labels convention — never by
encoding the service into the metric name.
"""

import os

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest, multiprocess
from prometheus_fastapi_instrumentator import Instrumentator

_NAMESPACE = "jobcopilot"


def instrument_app(app: FastAPI) -> None:
    """Attach HTTP metrics and expose them on GET /metrics.

    Multi-worker services (uvicorn --workers N) MUST set
    PROMETHEUS_MULTIPROC_DIR — each worker is a separate process, so without
    the multiprocess registry a scrape would hit one arbitrary worker's
    counters. The directory is created here; containers start with a fresh
    filesystem, so stale metric files cannot survive a restart.
    """
    mp_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if mp_dir:
        os.makedirs(mp_dir, exist_ok=True)

    instrumentator = Instrumentator(
        excluded_handlers=["/metrics", "/healthz/.*"],
        should_group_status_codes=False,
    )
    instrumentator.instrument(app, metric_namespace=_NAMESPACE)

    if mp_dir:
        # An explicit route (not a Mount) avoids the /metrics -> /metrics/ 307.
        # Per prometheus_client docs, multiprocess mode aggregates into a fresh
        # registry at scrape time.
        @app.get("/metrics", include_in_schema=False)
        def metrics() -> Response:
            registry = CollectorRegistry()
            # prometheus_client ships no annotations for the multiprocess module.
            multiprocess.MultiProcessCollector(registry)  # type: ignore[no-untyped-call]
            return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
    else:
        instrumentator.expose(app, include_in_schema=False)

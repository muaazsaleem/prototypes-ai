from google.genai import types

# ---------------------------------------------------------------------------
# Mock data — simulates what a real metrics/logging/DB system would return.
# Keyed by service or database name so each scenario gets realistic numbers.
# ---------------------------------------------------------------------------

_SERVICE_METRICS = {
    "api-gateway": {
        "cpu_pct": 94,
        "memory_pct": 55,
        "replicas": 2,
        "rps": 12000,
        "error_rate_pct": 0.5,
    },
    "user-service": {
        "cpu_pct": 45,
        "memory_pct": 60,
        "replicas": 3,
        "rps": 3000,
        "error_rate_pct": 0.2,
    },
    "order-service": {
        "cpu_pct": 62,
        "memory_pct": 97,
        "replicas": 2,
        "rps": 1500,
        "error_rate_pct": 0.3,
    },
    "payment-service": {
        "cpu_pct": 88,
        "memory_pct": 72,
        "replicas": 2,
        "rps": 2000,
        "error_rate_pct": 45.0,
    },
    "inventory-service": {
        "cpu_pct": 30,
        "memory_pct": 40,
        "replicas": 2,
        "rps": 800,
        "error_rate_pct": 0.1,
    },
}

_DB_STATS = {
    "users-db": {
        "max_connections": 500,
        "active": 498,
        "idle": 2,
        "long_running_queries": 15,
        "avg_query_ms": 450,
    },
    "orders-db": {
        "max_connections": 300,
        "active": 120,
        "idle": 180,
        "long_running_queries": 2,
        "avg_query_ms": 80,
    },
    "analytics-db": {
        "max_connections": 200,
        "active": 45,
        "idle": 155,
        "long_running_queries": 0,
        "avg_query_ms": 200,
    },
}

_SERVICE_LOGS = {
    "api-gateway": [
        "2026-05-01 10:23:01 WARN  High latency detected: p99=2300ms",
        "2026-05-01 10:23:15 ERROR Upstream timeout: user-service /profile",
        "2026-05-01 10:23:28 WARN  CPU throttling detected on core 0",
        "2026-05-01 10:23:45 ERROR Request queue depth at 850/1000",
        "2026-05-01 10:23:59 WARN  Rate limiter approaching max capacity",
    ],
    "order-service": [
        "2026-05-01 10:20:01 WARN  Heap memory at 89%",
        "2026-05-01 10:21:30 WARN  GC pause: 1200ms (full GC triggered)",
        "2026-05-01 10:22:15 ERROR OOMKill risk: heap at 94%",
        "2026-05-01 10:23:00 ERROR Full GC running every 30 seconds",
        "2026-05-01 10:23:45 FATAL Memory allocation failed for order batch processor",
    ],
    "user-service": [
        "2026-05-01 10:22:10 ERROR DB connection timeout after 30s",
        "2026-05-01 10:22:25 ERROR DB pool exhausted, request queued",
        "2026-05-01 10:22:40 ERROR DB pool exhausted, request dropped",
        "2026-05-01 10:23:05 ERROR 15 long-running queries detected on users-db",
        "2026-05-01 10:23:30 ERROR Connection wait time exceeds 5s threshold",
    ],
    "payment-service": [
        "2026-05-01 10:23:00 ERROR Stripe gateway timeout: 504",
        "2026-05-01 10:23:10 ERROR Payment processor rejected: invalid_signature",
        "2026-05-01 10:23:20 ERROR TLS handshake failed: certificate chain error",
        "2026-05-01 10:23:35 ERROR 270 transactions failed this minute",
        "2026-05-01 10:23:50 FATAL Revenue impact: $45,000 in the last 10 minutes",
    ],
}


# ---------------------------------------------------------------------------
# Diagnostic tool implementations (read-only — these are exposed to the agent)
# ---------------------------------------------------------------------------


def get_cpu_metrics(service: str) -> dict:
    """Returns CPU percent, trend, replica count, and RPS for a service.

    trend is "increasing" when CPU is above 80% — the agent uses this to
    distinguish a spike from steady-state load.
    Unknown services fall back to a healthy-looking baseline.
    """
    m = _SERVICE_METRICS.get(service, {"cpu_pct": 20, "replicas": 1, "rps": 100})
    return {
        "service": service,
        "cpu_percent": m["cpu_pct"],
        "trend": "increasing" if m["cpu_pct"] > 80 else "stable",
        "current_replicas": m.get("replicas", 1),
        "requests_per_second": m.get("rps", 0),
    }


def get_memory_metrics(service: str) -> dict:
    """Returns memory percent, absolute usage in GB, limit in GB, and trend.

    order-service has a higher memory limit (8 GB) because it runs the batch
    processor; all other services are capped at 4 GB.
    """
    m = _SERVICE_METRICS.get(service, {"memory_pct": 30})
    limit_gb = 8 if service == "order-service" else 4
    used_gb = round(limit_gb * m["memory_pct"] / 100, 1)
    return {
        "service": service,
        "memory_percent": m["memory_pct"],
        "memory_used_gb": used_gb,
        "memory_limit_gb": limit_gb,
        "trend": "increasing" if m["memory_pct"] > 85 else "stable",
    }


def get_db_connections(database: str) -> dict:
    """Returns connection pool stats for a database, including utilization percent and long-running query count.

    utilization_percent is derived from active/max so the agent doesn't have to compute it.
    long_running_queries is the key signal for pool exhaustion caused by stale queries.
    """
    db = _DB_STATS.get(
        database,
        {
            "max_connections": 100,
            "active": 10,
            "idle": 90,
            "long_running_queries": 0,
            "avg_query_ms": 50,
        },
    )
    utilization = round(db["active"] / db["max_connections"] * 100, 1)
    return {
        "database": database,
        "max_connections": db["max_connections"],
        "active_connections": db["active"],
        "idle_connections": db["idle"],
        "utilization_percent": utilization,
        "long_running_queries": db["long_running_queries"],
        "avg_query_latency_ms": db["avg_query_ms"],
    }


def get_recent_logs(service: str, lines: int = 10) -> dict:
    """Returns the most recent log entries for a service, newest last.

    Returns a generic INFO entry for unknown services rather than an empty list,
    so the agent always gets a valid response it can reason about.
    """
    logs = _SERVICE_LOGS.get(
        service, [f"2026-05-01 10:23:00 INFO No significant events for {service}"]
    )
    return {"service": service, "log_entries": logs[:lines]}


def get_error_rate(service: str) -> dict:
    """Returns the current error rate percentage and derived errors-per-minute for a service."""
    m = _SERVICE_METRICS.get(service, {"error_rate_pct": 0.1, "rps": 100})
    errors_per_min = round(m["error_rate_pct"] / 100 * m.get("rps", 0) * 60, 0)
    return {
        "service": service,
        "error_rate_percent": m["error_rate_pct"],
        "requests_per_second": m.get("rps", 0),
        "errors_per_minute": errors_per_min,
    }


# ---------------------------------------------------------------------------
# Remediation tool implementations (write operations — NOT exposed to agent)
# These are only called after the risk judge approves the action.
# ---------------------------------------------------------------------------


def restart_service(service: str) -> dict:
    """Simulates a graceful pod restart; returns status and simulated duration."""
    return {
        "status": "success",
        "message": f"{service} restarted successfully",
        "duration_seconds": 12,
    }


def scale_service(service: str, replicas: int) -> dict:
    """Simulates scaling a service to the requested replica count; includes the previous count in the message."""
    current = _SERVICE_METRICS.get(service, {}).get("replicas", 1)
    return {
        "status": "success",
        "message": f"{service} scaled from {current} to {replicas} replicas",
        "duration_seconds": 30,
    }


def kill_long_running_queries(database: str, older_than_seconds: int = 60) -> dict:
    """Simulates killing stale queries on a database; uses the mock long_running_queries count as the kill total."""
    count = _DB_STATS.get(database, {}).get("long_running_queries", 0)
    return {
        "status": "success",
        "message": f"Killed {count} long-running queries on {database}",
        "queries_killed": count,
        "duration_seconds": 3,
    }


def run_vacuum(database: str) -> dict:
    """Simulates VACUUM ANALYZE; freed_gb is a fixed mock value for demo purposes."""
    return {
        "status": "success",
        "message": f"VACUUM ANALYZE completed on {database}",
        "freed_gb": 12.4,
        "duration_seconds": 45,
    }


def rollback_deployment(service: str, version: str) -> dict:
    """Simulates rolling a service back to a previous image version."""
    return {
        "status": "success",
        "message": f"{service} rolled back to version {version}",
        "duration_seconds": 25,
    }


_REMEDIATION_DISPATCH = {
    "restart_service": restart_service,
    "scale_service": scale_service,
    "kill_long_running_queries": kill_long_running_queries,
    "run_vacuum": run_vacuum,
    "rollback_deployment": rollback_deployment,
}

_DIAGNOSTIC_DISPATCH = {
    "get_cpu_metrics": get_cpu_metrics,
    "get_memory_metrics": get_memory_metrics,
    "get_db_connections": get_db_connections,
    "get_recent_logs": get_recent_logs,
    "get_error_rate": get_error_rate,
}


def execute_diagnostic_tool(name: str, args: dict) -> dict:
    """Dispatches a diagnostic tool call by name; returns an error dict for unknown tool names."""
    if name not in _DIAGNOSTIC_DISPATCH:
        return {"error": f"Unknown diagnostic tool: {name}"}
    return _DIAGNOSTIC_DISPATCH[name](**args)


def execute_remediation_tool(name: str, args: dict) -> dict:
    """Dispatches a remediation tool call by name; returns an error dict for unknown tool names."""
    if name not in _REMEDIATION_DISPATCH:
        return {"error": f"Unknown remediation tool: {name}"}
    return _REMEDIATION_DISPATCH[name](**args)


# ---------------------------------------------------------------------------
# Gemini function declarations — these tell the model what tools it can call.
# Only diagnostic (read-only) tools are exposed to the agent.
# ---------------------------------------------------------------------------

DIAGNOSTIC_TOOL_DECLARATIONS = [
    types.FunctionDeclaration(
        name="get_cpu_metrics",
        description="Get CPU usage, replica count, and request rate for a service",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "service": types.Schema(
                    type=types.Type.STRING,
                    description="Service name, e.g. api-gateway",
                )
            },
            required=["service"],
        ),
    ),
    types.FunctionDeclaration(
        name="get_memory_metrics",
        description="Get memory usage and trend for a service",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "service": types.Schema(
                    type=types.Type.STRING,
                    description="Service name",
                )
            },
            required=["service"],
        ),
    ),
    types.FunctionDeclaration(
        name="get_db_connections",
        description="Get database connection pool stats: active connections, idle, and long-running queries",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "database": types.Schema(
                    type=types.Type.STRING,
                    description="Database name, e.g. users-db",
                )
            },
            required=["database"],
        ),
    ),
    types.FunctionDeclaration(
        name="get_recent_logs",
        description="Get recent log entries for a service to look for error patterns",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "service": types.Schema(
                    type=types.Type.STRING,
                    description="Service name",
                ),
                "lines": types.Schema(
                    type=types.Type.INTEGER,
                    description="Number of log lines to retrieve (default: 10)",
                ),
            },
            required=["service"],
        ),
    ),
    types.FunctionDeclaration(
        name="get_error_rate",
        description="Get the current error rate percentage and errors-per-minute for a service",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "service": types.Schema(
                    type=types.Type.STRING,
                    description="Service name",
                )
            },
            required=["service"],
        ),
    ),
]

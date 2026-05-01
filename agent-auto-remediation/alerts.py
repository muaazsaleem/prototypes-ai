from dataclasses import dataclass


@dataclass
class Alert:
    """Represents an incoming infrastructure alert with technical context."""

    id: str
    service: str
    alert_type: str
    severity: str  # "critical" | "warning" | "info"
    description: str
    metadata: dict  # extra context: database name, threshold, current value, etc.


# Four scenarios that exercise every pipeline path:
# cpu_spike       → auto-execute (low risk)
# db_connections  → auto-execute (moderate risk)
# memory_leak     → auto-execute (moderate risk, service restart)
# payment_errors  → blocked by output filter before risk scoring
SCENARIOS = {
    "cpu_spike": Alert(
        id="alert-001",
        service="api-gateway",
        alert_type="HIGH_CPU",
        severity="critical",
        description="api-gateway CPU usage has been above 90% for the last 5 minutes. Response latency is degrading.",
        metadata={"threshold_pct": 90, "current_pct": 94, "duration_minutes": 5},
    ),
    "db_connections": Alert(
        id="alert-002",
        service="user-service",
        alert_type="DB_CONNECTIONS_EXHAUSTED",
        severity="critical",
        description="users-db connection pool is at 99% capacity. New connections are being rejected.",
        metadata={
            "database": "users-db",
            "max_connections": 500,
            "active_connections": 498,
        },
    ),
    "memory_leak": Alert(
        id="alert-003",
        service="order-service",
        alert_type="MEMORY_EXHAUSTION",
        severity="critical",
        description="order-service memory is at 97%. OOMKill is imminent within minutes.",
        metadata={"threshold_pct": 90, "current_pct": 97, "memory_limit_gb": 8},
    ),
    "payment_errors": Alert(
        id="alert-004",
        service="payment-service",
        alert_type="HIGH_ERROR_RATE",
        severity="critical",
        description="payment-service error rate at 45%. Transactions are failing and revenue impact is active.",
        metadata={"threshold_pct": 5, "current_pct": 45, "errors_per_minute": 270},
    ),
}

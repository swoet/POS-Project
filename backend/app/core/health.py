from datetime import datetime, timezone


def basic_health_payload() -> dict:
    """Build the lightweight health response without touching dependencies."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def detailed_health_payload(database_ok: bool, cache_ok: bool, version: str, environment: str) -> dict:
    """Build the detailed readiness payload from explicit dependency checks."""
    healthy = database_ok and cache_ok

    return {
        "status": "healthy" if healthy else "degraded",
        "services": {
            "database": "healthy" if database_ok else "unhealthy",
            "cache": "healthy" if cache_ok else "unhealthy",
        },
        "version": version,
        "environment": environment,
    }

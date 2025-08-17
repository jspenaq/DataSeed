"""
Telemetry module for DataSeed Dashboard.

This module provides a lightweight event tracking system for monitoring user interactions
and system events in the dashboard. Events are logged to console and optionally to file
for analysis and debugging purposes.
"""

import json
import logging
import time
from datetime import datetime
from typing import Any

import streamlit as st


class TelemetryLogger:
    """
    Lightweight telemetry logger for dashboard events.

    Features:
    - Console and file logging
    - Event categorization
    - Performance timing
    - Rate limiting awareness
    - Session tracking
    """

    def __init__(self, log_to_file: bool = True, log_file_path: str | None = None):
        self.log_to_file = log_to_file
        self.log_file_path = log_file_path or "dashboard_telemetry.log"
        self.session_id = self._get_session_id()

        # Set up logging
        self.logger = logging.getLogger("dashboard_telemetry")
        self.logger.setLevel(logging.INFO)

        # Prevent duplicate handlers
        if not self.logger.handlers:
            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter("%(asctime)s - TELEMETRY - %(levelname)s - %(message)s")
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)

            # File handler (if enabled)
            if self.log_to_file:
                try:
                    file_handler = logging.FileHandler(self.log_file_path)
                    file_handler.setLevel(logging.INFO)
                    file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
                    file_handler.setFormatter(file_formatter)
                    self.logger.addHandler(file_handler)
                except Exception as e:
                    print(f"Warning: Could not set up file logging: {e}")

    def _get_session_id(self) -> str:
        """Get or create a session ID for tracking user sessions."""
        if "telemetry_session_id" not in st.session_state:
            st.session_state.telemetry_session_id = f"session_{int(time.time())}"
        return st.session_state.telemetry_session_id

    def _create_event(
        self,
        event_type: str,
        event_name: str,
        properties: dict[str, Any] | None = None,
        duration_ms: float | None = None,
    ) -> dict[str, Any]:
        """Create a standardized event object."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": self.session_id,
            "event_type": event_type,
            "event_name": event_name,
            "properties": properties or {},
        }

        if duration_ms is not None:
            event["duration_ms"] = duration_ms

        # Add user agent and viewport info if available
        try:
            is_mobile = st.session_state.get("is_mobile", False)
            event["properties"]["is_mobile"] = is_mobile
        except:
            pass

        return event

    def track_event(
        self,
        event_type: str,
        event_name: str,
        properties: dict[str, Any] | None = None,
        duration_ms: float | None = None,
    ) -> None:
        """
        Track a general event.

        Args:
            event_type: Category of event (page_view, user_action, system_event, etc.)
            event_name: Specific event name
            properties: Additional event properties
            duration_ms: Optional duration in milliseconds
        """
        event = self._create_event(event_type, event_name, properties, duration_ms)
        self.logger.info(json.dumps(event, default=str))

    def track_page_view(self, page_name: str, properties: dict[str, Any] | None = None) -> None:
        """Track page view events."""
        self.track_event(
            event_type="page_view",
            event_name=f"view_{page_name.lower()}",
            properties={"page_name": page_name, **(properties or {})},
        )

    def track_user_action(self, action: str, component: str, properties: dict[str, Any] | None = None) -> None:
        """Track user interaction events."""
        self.track_event(
            event_type="user_action",
            event_name=f"{component}_{action}",
            properties={"action": action, "component": component, **(properties or {})},
        )

    def track_auto_refresh_toggle(self, enabled: bool, interval_seconds: int) -> None:
        """Track auto-refresh toggle events."""
        self.track_user_action(
            action="toggle_auto_refresh",
            component="refresh_controls",
            properties={
                "enabled": enabled,
                "interval_seconds": interval_seconds,
                "interval_minutes": interval_seconds / 60,
            },
        )

    def track_export_action(self, export_format: str, data_type: str, row_count: int, filename: str) -> None:
        """Track data export events."""
        self.track_user_action(
            action="export_data",
            component="export_buttons",
            properties={
                "export_format": export_format,
                "data_type": data_type,
                "row_count": row_count,
                "filename": filename,
            },
        )

    def track_rate_limit_event(
        self,
        wait_time_seconds: float,
        consecutive_429s: int,
        endpoint: str | None = None,
    ) -> None:
        """Track rate limiting events."""
        self.track_event(
            event_type="system_event",
            event_name="rate_limited",
            properties={
                "wait_time_seconds": wait_time_seconds,
                "consecutive_429s": consecutive_429s,
                "endpoint": endpoint,
                "severity": "warning" if consecutive_429s < 3 else "error",
            },
        )

    def track_api_call(
        self,
        endpoint: str,
        method: str,
        duration_ms: float,
        status_code: int,
        cache_hit: bool = False,
    ) -> None:
        """Track API call performance and status."""
        self.track_event(
            event_type="api_call",
            event_name=f"api_{method.lower()}_{endpoint.replace('/', '_')}",
            properties={
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                "cache_hit": cache_hit,
                "success": 200 <= status_code < 300,
            },
            duration_ms=duration_ms,
        )

    def track_error(
        self,
        error_type: str,
        error_message: str,
        component: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Track error events."""
        self.track_event(
            event_type="error",
            event_name=f"error_{component}",
            properties={
                "error_type": error_type,
                "error_message": error_message,
                "component": component,
                **(properties or {}),
            },
        )

    def track_performance(
        self,
        operation: str,
        duration_ms: float,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Track performance metrics."""
        self.track_event(
            event_type="performance",
            event_name=f"perf_{operation}",
            properties={"operation": operation, **(properties or {})},
            duration_ms=duration_ms,
        )


class PerformanceTimer:
    """Context manager for tracking operation performance."""

    def __init__(self, telemetry: TelemetryLogger, operation: str, properties: dict[str, Any] | None = None):
        self.telemetry = telemetry
        self.operation = operation
        self.properties = properties or {}
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration_ms = (time.time() - self.start_time) * 1000
            self.telemetry.track_performance(self.operation, duration_ms, self.properties)


# Global telemetry instance
@st.cache_resource
def get_telemetry_logger() -> TelemetryLogger:
    """Get cached telemetry logger instance."""
    return TelemetryLogger()


# Convenience functions for common tracking scenarios


def track_page_view(page_name: str, properties: dict[str, Any] | None = None) -> None:
    """Track page view with global telemetry logger."""
    telemetry = get_telemetry_logger()
    telemetry.track_page_view(page_name, properties)


def track_user_action(action: str, component: str, properties: dict[str, Any] | None = None) -> None:
    """Track user action with global telemetry logger."""
    telemetry = get_telemetry_logger()
    telemetry.track_user_action(action, component, properties)


def track_auto_refresh_toggle(enabled: bool, interval_seconds: int) -> None:
    """Track auto-refresh toggle with global telemetry logger."""
    telemetry = get_telemetry_logger()
    telemetry.track_auto_refresh_toggle(enabled, interval_seconds)


def track_export_action(export_format: str, data_type: str, row_count: int, filename: str) -> None:
    """Track export action with global telemetry logger."""
    telemetry = get_telemetry_logger()
    telemetry.track_export_action(export_format, data_type, row_count, filename)


def track_rate_limit_event(wait_time_seconds: float, consecutive_429s: int, endpoint: str | None = None) -> None:
    """Track rate limit event with global telemetry logger."""
    telemetry = get_telemetry_logger()
    telemetry.track_rate_limit_event(wait_time_seconds, consecutive_429s, endpoint)


def track_api_call(endpoint: str, method: str, duration_ms: float, status_code: int, cache_hit: bool = False) -> None:
    """Track API call with global telemetry logger."""
    telemetry = get_telemetry_logger()
    telemetry.track_api_call(endpoint, method, duration_ms, status_code, cache_hit)


def track_error(
    error_type: str,
    error_message: str,
    component: str,
    properties: dict[str, Any] | None = None,
) -> None:
    """Track error with global telemetry logger."""
    telemetry = get_telemetry_logger()
    telemetry.track_error(error_type, error_message, component, properties)


def performance_timer(operation: str, properties: dict[str, Any] | None = None) -> PerformanceTimer:
    """Create performance timer context manager."""
    telemetry = get_telemetry_logger()
    return PerformanceTimer(telemetry, operation, properties)


# Telemetry decorators for common patterns


def track_function_call(operation_name: str | None = None):
    """Decorator to track function call performance."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            with performance_timer(op_name):
                return func(*args, **kwargs)

        return wrapper

    return decorator


def track_streamlit_component(component_name: str):
    """Decorator to track Streamlit component rendering."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            with performance_timer(f"render_{component_name}"):
                return func(*args, **kwargs)

        return wrapper

    return decorator

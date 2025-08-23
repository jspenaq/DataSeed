"""
State management for DataSeed Dashboard.

This module provides centralized session state management for the Streamlit dashboard,
including user selections, filters, pagination cursors, and refresh intervals.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import streamlit as st


@dataclass
class FilterState:
    """State for content filtering options."""

    source: str | None = None
    search_query: str | None = ""
    sort_by: str = "published_at"
    sort_order: str = "desc"
    date_range: tuple | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class PaginationState:
    """State for pagination cursors and limits."""

    cursor: str | None = None
    limit: int = 20
    total_items: int = 0
    has_next: bool = False
    has_previous: bool = False


@dataclass
class RefreshState:
    """State for auto-refresh functionality."""

    enabled: bool = False
    interval_seconds: int = 300  # 5 minutes default
    last_refresh: datetime | None = None
    next_refresh: datetime | None = None
    is_paused: bool = False
    rate_limited: bool = False
    rate_limit_until: datetime | None = None

    @property
    def interval_minutes(self) -> float:
        """Get interval in minutes for backward compatibility."""
        return self.interval_seconds / 60.0

    def set_interval_minutes(self, minutes: float) -> None:
        """Set interval in minutes."""
        self.interval_seconds = int(minutes * 60)

    def calculate_next_refresh(self) -> datetime | None:
        """Calculate when the next refresh should occur."""
        if not self.enabled or self.is_paused:
            return None

        if self.rate_limited and self.rate_limit_until:
            return self.rate_limit_until

        if self.last_refresh:
            return self.last_refresh + timedelta(seconds=self.interval_seconds)

        return datetime.now() + timedelta(seconds=self.interval_seconds)

    def time_until_next_refresh(self) -> float | None:
        """Get seconds until next refresh."""
        next_refresh = self.calculate_next_refresh()
        if not next_refresh:
            return None

        return max(0, (next_refresh - datetime.now()).total_seconds())

    def should_refresh_now(self) -> bool:
        """Check if refresh should happen now."""
        if not self.enabled or self.is_paused:
            return False

        time_until = self.time_until_next_refresh()
        return time_until is not None and time_until <= 0


@dataclass
class UIState:
    """State for UI preferences and selections."""

    selected_page: str = "Overview"
    sidebar_collapsed: bool = False
    theme: str = "light"
    items_per_page: int = 20
    show_advanced_filters: bool = False


class DashboardState:
    """
    Centralized state management for the DataSeed dashboard.

    This class provides a clean interface for managing all dashboard state
    using Streamlit's session state as the underlying storage mechanism.
    """

    def __init__(self):
        self._init_state()

    def _init_state(self) -> None:
        """Initialize default state values if not already present."""
        # Always check and set all required session state keys
        if "filter_state" not in st.session_state:
            st.session_state.filter_state = FilterState()
        if "pagination_state" not in st.session_state:
            st.session_state.pagination_state = PaginationState()
        if "refresh_state" not in st.session_state:
            st.session_state.refresh_state = RefreshState()
        if "ui_state" not in st.session_state:
            st.session_state.ui_state = UIState()
        if "data_cache" not in st.session_state:
            st.session_state.data_cache = {}
        if "error_messages" not in st.session_state:
            st.session_state.error_messages = []
        if "loading_states" not in st.session_state:
            st.session_state.loading_states = {}
        if "user_preferences" not in st.session_state:
            st.session_state.user_preferences = {}

    @property
    def filters(self) -> FilterState:
        """Get current filter state."""
        return st.session_state.filter_state

    @filters.setter
    def filters(self, value: FilterState) -> None:
        """Set filter state."""
        st.session_state.filter_state = value

    @property
    def pagination(self) -> PaginationState:
        """Get current pagination state."""
        return st.session_state.pagination_state

    @pagination.setter
    def pagination(self, value: PaginationState) -> None:
        """Set pagination state."""
        st.session_state.pagination_state = value

    @property
    def refresh(self) -> RefreshState:
        """Get current refresh state."""
        return st.session_state.refresh_state

    @refresh.setter
    def refresh(self, value: RefreshState) -> None:
        """Set refresh state."""
        st.session_state.refresh_state = value

    @property
    def ui(self) -> UIState:
        """Get current UI state."""
        return st.session_state.ui_state

    @ui.setter
    def ui(self, value: UIState) -> None:
        """Set UI state."""
        st.session_state.ui_state = value

    def update_filter(self, **kwargs) -> None:
        """Update specific filter values."""
        current_filters = self.filters
        for key, value in kwargs.items():
            if hasattr(current_filters, key):
                setattr(current_filters, key, value)
        self.filters = current_filters

        # Reset pagination when filters change
        self.reset_pagination()

    def update_pagination(self, **kwargs) -> None:
        """Update specific pagination values."""
        current_pagination = self.pagination
        for key, value in kwargs.items():
            if hasattr(current_pagination, key):
                setattr(current_pagination, key, value)
        self.pagination = current_pagination

    def update_ui(self, **kwargs) -> None:
        """Update specific UI values."""
        current_ui = self.ui
        for key, value in kwargs.items():
            if hasattr(current_ui, key):
                setattr(current_ui, key, value)
        self.ui = current_ui

    def reset_pagination(self) -> None:
        """Reset pagination to initial state."""
        self.pagination = PaginationState(limit=self.pagination.limit)

    def reset_filters(self) -> None:
        """Reset all filters to default values."""
        self.filters = FilterState()
        self.reset_pagination()

    def cache_data(self, key: str, data: Any, ttl_minutes: int = 5) -> None:
        """Cache data with TTL."""
        st.session_state.data_cache[key] = {"data": data, "cached_at": datetime.now(), "ttl_minutes": ttl_minutes}

    def get_cached_data(self, key: str) -> Any | None:
        """Get cached data if not expired."""
        if key not in st.session_state.data_cache:
            return None

        cache_entry = st.session_state.data_cache[key]
        cached_at = cache_entry["cached_at"]
        ttl = timedelta(minutes=cache_entry["ttl_minutes"])

        if datetime.now() - cached_at > ttl:
            # Remove expired cache entry
            del st.session_state.data_cache[key]
            return None

        return cache_entry["data"]

    def clear_cache(self, key: str | None = None) -> None:
        """Clear cached data. If key is None, clear all cache."""
        if key is None:
            st.session_state.data_cache = {}
        elif key in st.session_state.data_cache:
            del st.session_state.data_cache[key]

    def add_error(self, message: str) -> None:
        """Add error message to display."""
        st.session_state.error_messages.append({"message": message, "timestamp": datetime.now()})

    def clear_errors(self) -> None:
        """Clear all error messages."""
        st.session_state.error_messages = []

    def get_errors(self) -> list[dict[str, Any]]:
        """Get current error messages."""
        return st.session_state.error_messages

    def set_loading(self, component: str, loading: bool = True) -> None:
        """Set loading state for a component."""
        st.session_state.loading_states[component] = loading

    def is_loading(self, component: str) -> bool:
        """Check if a component is in loading state."""
        return st.session_state.loading_states.get(component, False)

    def should_refresh(self) -> bool:
        """Check if auto-refresh should trigger."""
        return self.refresh.should_refresh_now()

    def mark_refreshed(self) -> None:
        """Mark that a refresh has occurred."""
        current_refresh = self.refresh
        current_refresh.last_refresh = datetime.now()
        current_refresh.next_refresh = current_refresh.calculate_next_refresh()
        current_refresh.rate_limited = False
        current_refresh.rate_limit_until = None
        self.refresh = current_refresh

    def set_rate_limited(self, wait_time_seconds: float) -> None:
        """Set rate limited state with wait time."""
        current_refresh = self.refresh
        current_refresh.rate_limited = True
        current_refresh.rate_limit_until = datetime.now() + timedelta(seconds=wait_time_seconds)
        current_refresh.is_paused = True  # Pause auto-refresh during rate limiting
        self.refresh = current_refresh

    def clear_rate_limit(self) -> None:
        """Clear rate limited state."""
        current_refresh = self.refresh
        current_refresh.rate_limited = False
        current_refresh.rate_limit_until = None
        current_refresh.is_paused = False
        self.refresh = current_refresh

    def update_refresh_settings(self, enabled: bool, interval_seconds: int) -> None:
        """Update refresh settings."""
        current_refresh = self.refresh
        current_refresh.enabled = enabled
        current_refresh.interval_seconds = interval_seconds
        if enabled:
            current_refresh.next_refresh = current_refresh.calculate_next_refresh()
        else:
            current_refresh.next_refresh = None
        self.refresh = current_refresh

    def get_user_preference(self, key: str, default: Any = None) -> Any:
        """Get user preference value."""
        return st.session_state.user_preferences.get(key, default)

    def set_user_preference(self, key: str, value: Any) -> None:
        """Set user preference value."""
        st.session_state.user_preferences[key] = value

    def export_state(self) -> dict[str, Any]:
        """Export current state for debugging or persistence."""
        return {
            "filters": self.filters.__dict__,
            "pagination": self.pagination.__dict__,
            "refresh": {
                **self.refresh.__dict__,
                "last_refresh": self.refresh.last_refresh.isoformat() if self.refresh.last_refresh else None,
            },
            "ui": self.ui.__dict__,
            "user_preferences": st.session_state.user_preferences,
        }


# Global state instance
# @st.cache_resource
def get_dashboard_state() -> DashboardState:
    """Get cached dashboard state instance."""
    return DashboardState()


def reset_dashboard_state() -> None:
    """Reset all dashboard state to defaults."""
    keys_to_clear = [
        "filter_state",
        "pagination_state",
        "refresh_state",
        "ui_state",
        "data_cache",
        "error_messages",
        "loading_states",
        "user_preferences",
    ]

    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]

    # Reinitialize state
    get_dashboard_state()

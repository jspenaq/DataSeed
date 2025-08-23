"""
Shared UI components for DataSeed Dashboard.

This module provides reusable UI components for the Streamlit dashboard,
including KPI cards, health badges, filters, and other common interface elements.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any

import streamlit as st

from dashboard.telemetry import track_auto_refresh_toggle, track_user_action

# Optional plotly imports - will be used when charts are implemented
try:
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


def render_page_header(title: str, description: str | None = None, show_refresh: bool = True) -> None:
    """
    Render a consistent page header with title, description, and optional refresh button.

    Args:
        title: Page title
        description: Optional page description
        show_refresh: Whether to show refresh button
    """
    col1, col2 = st.columns([3, 1])

    with col1:
        st.title(title)
        if description:
            st.markdown(f"*{description}*")

    with col2:
        if show_refresh:
            if st.button("🔄 Refresh", key=f"refresh_{title.lower()}"):
                st.rerun()


def render_kpi_card(
    title: str,
    value: str,
    delta: str | None = None,
    delta_color: str = "normal",
    help_text: str | None = None,
) -> None:
    """
    Render a KPI card with title, value, and optional delta.

    Args:
        title: KPI title
        value: Main value to display
        delta: Optional delta/change value
        delta_color: Color for delta ("normal", "inverse", "off")
        help_text: Optional help text tooltip
    """
    # This is a placeholder for the KPI card component
    # Will be implemented in subsequent tasks

    # Ensure delta_color is a valid literal type
    valid_colors = ["normal", "inverse", "off"]
    if delta_color not in valid_colors:
        delta_color = "normal"

    st.metric(
        label=title,
        value=value,
        delta=delta,
        delta_color=delta_color,  # type: ignore
        help=help_text,
    )


def render_health_badge(status: str, details: dict[str, Any] | None = None) -> None:
    """
    Render a health status badge with optional details.

    Args:
        status: Health status ("healthy", "degraded", "unhealthy")
        details: Optional health check details
    """
    # This is a placeholder for the health badge component
    # Will be implemented in subsequent tasks

    status_colors = {"healthy": "🟢", "degraded": "🟡", "unhealthy": "🔴", "unknown": "⚪"}

    icon = status_colors.get(status, "⚪")
    st.markdown(f"{icon} **{status.title()}**")

    if details and st.expander("View Details", expanded=False):
        st.json(details)


def render_data_table(
    data: list[dict[str, Any]],
    columns: list[str] | None = None,
    sortable: bool = True,
    searchable: bool = True,
    page_size: int = 10,
) -> None:
    """
    Render a data table with optional sorting and searching.

    Args:
        data: List of dictionaries containing table data
        columns: Optional list of columns to display
        sortable: Whether table should be sortable
        searchable: Whether to include search functionality
        page_size: Number of rows per page
    """
    # This is a placeholder for the data table component
    # Will be implemented in subsequent tasks

    if not data:
        st.info("No data available")
        return

    # For now, just display as a simple dataframe
    import pandas as pd

    df = pd.DataFrame(data)

    if columns:
        df = df[columns]

    st.dataframe(df, use_container_width=True)


def render_filter_sidebar(
    available_sources: list[str],
    current_filters: dict[str, Any],
    on_filter_change: Callable[[dict[str, Any]], None],
) -> None:
    """
    Render filter controls in the sidebar.

    Args:
        available_sources: List of available data sources
        current_filters: Current filter values
        on_filter_change: Callback function when filters change
    """
    # This is a placeholder for the filter sidebar component
    # Will be implemented in subsequent tasks

    st.sidebar.header("Filters")

    # Source filter
    selected_source = st.sidebar.selectbox(
        "Source",
        options=["All"] + available_sources,
        index=0 if not current_filters.get("source") else available_sources.index(current_filters["source"]) + 1,
    )

    # Search query
    search_query = st.sidebar.text_input(
        "Search",
        value=current_filters.get("search_query", ""),
        placeholder="Enter search terms...",
    )

    # Sort options
    sort_by = st.sidebar.selectbox("Sort by", options=["published_at", "score", "title"], index=0)

    sort_order = st.sidebar.selectbox("Order", options=["desc", "asc"], index=0)

    # Build filter dict
    filters = {
        "source": None if selected_source == "All" else selected_source,
        "search_query": search_query,
        "sort_by": sort_by,
        "sort_order": sort_order,
    }

    # Call callback if filters changed
    if filters != current_filters:
        on_filter_change(filters)


def render_loading_spinner(message: str = "Loading...") -> None:
    """
    Render a loading spinner with message.

    Args:
        message: Loading message to display
    """
    with st.spinner(message):
        st.empty()


def render_error_message(message: str, error_type: str = "error") -> None:
    """
    Render an error message with appropriate styling.

    Args:
        message: Error message to display
        error_type: Type of error ("error", "warning", "info")
    """
    if error_type == "error":
        st.error(message)
    elif error_type == "warning":
        st.warning(message)
    elif error_type == "info":
        st.info(message)
    else:
        st.markdown(message)


def render_pagination_controls(
    current_page: int,
    total_pages: int,
    has_next: bool,
    has_previous: bool,
    on_page_change: Callable[[int], None],
) -> None:
    """
    Render pagination controls.

    Args:
        current_page: Current page number
        total_pages: Total number of pages
        has_next: Whether there is a next page
        has_previous: Whether there is a previous page
        on_page_change: Callback function when page changes
    """
    # This is a placeholder for pagination controls
    # Will be implemented in subsequent tasks

    col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])

    with col1:
        if has_previous and st.button("⏮️ First"):
            on_page_change(1)

    with col2:
        if has_previous and st.button("◀️ Previous"):
            on_page_change(current_page - 1)

    with col3:
        st.markdown(
            f"<div style='text-align: center'>Page {current_page} of {total_pages}</div>",
            unsafe_allow_html=True,
        )

    with col4:
        if has_next and st.button("Next ▶️"):
            on_page_change(current_page + 1)

    with col5:
        if has_next and st.button("Last ⏭️"):
            on_page_change(total_pages)


def render_chart_placeholder(chart_type: str, title: str, height: int = 400) -> None:
    """
    Render a placeholder for charts that will be implemented later.

    Args:
        chart_type: Type of chart ("line", "bar", "pie", etc.)
        title: Chart title
        height: Chart height in pixels
    """
    # This is a placeholder for chart components
    # Will be implemented in subsequent tasks

    st.subheader(title)
    st.info(f"📊 {chart_type.title()} chart will be implemented here")
    st.empty()


def render_export_buttons(data: list[dict[str, Any]], filename_prefix: str = "dataseed_export") -> None:
    """
    Render export buttons for data download.

    Args:
        data: Data to export
        filename_prefix: Prefix for exported filename
    """
    # This is a placeholder for export functionality
    # Will be implemented in subsequent tasks

    if not data:
        return

    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
            label="📄 Export CSV",
            data="CSV export will be implemented",
            file_name=f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            disabled=True,
        )

    with col2:
        st.download_button(
            label="📋 Export JSON",
            data="JSON export will be implemented",
            file_name=f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            disabled=True,
        )


def render_auto_refresh_controls(refresh_state, api_client, key_prefix: str = "auto_refresh") -> dict[str, Any]:
    """
    Render comprehensive auto-refresh controls with rate limiting status.

    Args:
        refresh_state: RefreshState object from dashboard state
        api_client: API client instance for rate limit status
        key_prefix: Unique key prefix for Streamlit components

    Returns:
        Dict with refresh control actions and status
    """
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔄 Auto Refresh")

    # Get rate limit status
    rate_limit_status = api_client.get_rate_limit_status()

    # Auto-refresh toggle
    new_enabled = st.sidebar.checkbox(
        "Enable auto-refresh",
        value=refresh_state.enabled,
        disabled=rate_limit_status["is_rate_limited"],
        key=f"{key_prefix}_enabled",
        help="Automatically refresh data at specified intervals",
    )

    # Interval selection
    interval_options = {"15 seconds": 15, "30 seconds": 30, "1 minute": 60, "5 minutes": 300, "10 minutes": 600}

    current_interval_label = None
    for label, seconds in interval_options.items():
        if seconds == refresh_state.interval_seconds:
            current_interval_label = label
            break

    if current_interval_label is None:
        current_interval_label = f"{refresh_state.interval_seconds}s"
        interval_options[current_interval_label] = refresh_state.interval_seconds

    selected_interval_label = st.sidebar.selectbox(
        "Refresh interval",
        options=list(interval_options.keys()),
        index=list(interval_options.keys()).index(current_interval_label),
        disabled=not new_enabled or rate_limit_status["is_rate_limited"],
        key=f"{key_prefix}_interval",
        help="How often to refresh the data",
    )

    new_interval_seconds = interval_options[selected_interval_label]

    # Status display
    if rate_limit_status["is_rate_limited"]:
        wait_time = rate_limit_status["wait_time_seconds"]
        st.sidebar.error("⚠️ Rate Limited")
        st.sidebar.caption(f"Wait {wait_time:.1f}s before next request")

        # Progress bar for rate limit countdown
        progress = max(0, 1 - (wait_time / rate_limit_status["current_delay"]))
        st.sidebar.progress(progress)

    elif new_enabled and not refresh_state.is_paused:
        time_until_next = refresh_state.time_until_next_refresh()
        if time_until_next is not None:
            if time_until_next > 0:
                st.sidebar.success("✅ Active")
                st.sidebar.caption(f"Next refresh in {time_until_next:.0f}s")

                # Progress bar for refresh countdown
                progress = 1 - (time_until_next / refresh_state.interval_seconds)
                st.sidebar.progress(max(0, min(1, progress)))
            else:
                st.sidebar.info("🔄 Refreshing...")
        else:
            st.sidebar.info("⏸️ Paused")
    elif new_enabled and refresh_state.is_paused:
        st.sidebar.warning("⏸️ Paused")
    else:
        st.sidebar.info("⏹️ Disabled")

    # Manual refresh button
    manual_refresh = st.sidebar.button(
        "🔄 Refresh Now",
        disabled=rate_limit_status["is_rate_limited"],
        key=f"{key_prefix}_manual",
        help="Manually trigger a refresh",
    )

    # Pause/Resume button (only show when auto-refresh is enabled)
    pause_resume = None
    if new_enabled:
        if refresh_state.is_paused:
            pause_resume = st.sidebar.button("▶️ Resume", key=f"{key_prefix}_resume", help="Resume auto-refresh")
        else:
            pause_resume = st.sidebar.button("⏸️ Pause", key=f"{key_prefix}_pause", help="Pause auto-refresh")

    return {
        "enabled_changed": new_enabled != refresh_state.enabled,
        "interval_changed": new_interval_seconds != refresh_state.interval_seconds,
        "new_enabled": new_enabled,
        "new_interval_seconds": new_interval_seconds,
        "manual_refresh": manual_refresh,
        "pause_resume": pause_resume,
        "is_paused": refresh_state.is_paused,
        "rate_limited": rate_limit_status["is_rate_limited"],
        "should_refresh": refresh_state.should_refresh_now() and not rate_limit_status["is_rate_limited"],
    }


def render_refresh_status_indicator(refresh_state, api_client, show_in_main: bool = True) -> None:
    """
    Render refresh status indicator in main content area.

    Args:
        refresh_state: RefreshState object
        api_client: API client instance
        show_in_main: Whether to show in main content area
    """
    if not show_in_main:
        return

    rate_limit_status = api_client.get_rate_limit_status()

    if rate_limit_status["is_rate_limited"]:
        wait_time = rate_limit_status["wait_time_seconds"]
        st.warning(
            f"⚠️ **Rate Limited**: Please wait {wait_time:.1f} seconds before the next request. "
            f"Auto-refresh is temporarily paused.",
        )
    elif refresh_state.enabled and not refresh_state.is_paused:
        time_until_next = refresh_state.time_until_next_refresh()
        if time_until_next is not None and time_until_next > 0:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.info(f"🔄 **Auto-refresh active**: Next update in {time_until_next:.0f} seconds")
            with col2:
                # Small progress indicator
                progress = 1 - (time_until_next / refresh_state.interval_seconds)
                st.progress(max(0, min(1, progress)))


def render_auto_refresh_page_wrapper(
    page_content_func: Callable,
    page_title: str,
    state,
    api_client,
    key_prefix: str | None = None,
) -> None:
    """
    Wrapper function that adds auto-refresh functionality to any page.

    Args:
        page_content_func: Function that renders the main page content
        page_title: Title of the page for key generation
        state: Dashboard state instance
        api_client: API client instance
        key_prefix: Optional key prefix, defaults to page_title.lower()
    """
    if key_prefix is None:
        key_prefix = page_title.lower().replace(" ", "_")

    # Render auto-refresh controls in sidebar
    refresh_controls = render_auto_refresh_controls(state.refresh, api_client, key_prefix)

    # Handle refresh control actions
    settings_changed = False

    if refresh_controls["enabled_changed"] or refresh_controls["interval_changed"]:
        # Track auto-refresh toggle
        if refresh_controls["enabled_changed"]:
            track_auto_refresh_toggle(refresh_controls["new_enabled"], refresh_controls["new_interval_seconds"])

        state.update_refresh_settings(refresh_controls["new_enabled"], refresh_controls["new_interval_seconds"])
        settings_changed = True

    if refresh_controls["pause_resume"]:
        current_refresh = state.refresh
        action = "resume" if current_refresh.is_paused else "pause"
        track_user_action(action, "auto_refresh", {"interval_seconds": current_refresh.interval_seconds})
        current_refresh.is_paused = not current_refresh.is_paused
        state.refresh = current_refresh
        settings_changed = True

    # Handle refresh triggers
    should_refresh = refresh_controls["manual_refresh"] or refresh_controls["should_refresh"] or settings_changed

    if should_refresh and not refresh_controls["rate_limited"]:
        try:
            # Track manual refresh if triggered manually
            if refresh_controls["manual_refresh"]:
                track_user_action("manual_refresh", "refresh_button")

            # Clear relevant caches before refresh
            state.clear_cache()

            # Mark as refreshed
            state.mark_refreshed()

            # Trigger page rerun to refresh content
            st.rerun()

        except Exception as e:
            # Handle rate limiting or other API errors
            from dashboard.api import RateLimitError

            if isinstance(e, RateLimitError):
                state.set_rate_limited(e.wait_time)
                st.error(f"Rate limited: {str(e)}")
            else:
                st.error(f"Refresh failed: {str(e)}")

    # Show refresh status in main content
    render_refresh_status_indicator(state.refresh, api_client)

    # Render the actual page content
    try:
        page_content_func()
    except Exception as e:
        from dashboard.api import RateLimitError

        if isinstance(e, RateLimitError):
            state.set_rate_limited(e.wait_time)
            st.error(f"Failed to load page content due to rate limiting: {str(e)}")
        else:
            st.error(f"Failed to load page content: {str(e)}")

    # Auto-refresh logic - check if we should trigger a refresh
    if state.refresh.enabled and not state.refresh.is_paused and not refresh_controls["rate_limited"]:
        time_until_next = state.refresh.time_until_next_refresh()
        if time_until_next is not None and time_until_next <= 0:
            # Use a small delay to prevent too frequent refreshes
            import time

            time.sleep(1)
            st.rerun()


# Utility functions for common UI patterns


def format_timestamp(timestamp: datetime, format_type: str = "relative") -> str:
    """
    Format timestamp for display.

    Args:
        timestamp: Timestamp to format
        format_type: Format type ("relative", "absolute", "short")

    Returns:
        Formatted timestamp string
    """
    if format_type == "relative":
        # This would implement relative time formatting
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")
    if format_type == "short":
        return timestamp.strftime("%m/%d %H:%M")
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to specified length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add when truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def get_status_color(status: str) -> str:
    """
    Get color for status display.

    Args:
        status: Status string

    Returns:
        Color code or name
    """
    status_colors = {
        "healthy": "#28a745",
        "degraded": "#ffc107",
        "unhealthy": "#dc3545",
        "active": "#007bff",
        "inactive": "#6c757d",
        "success": "#28a745",
        "warning": "#ffc107",
        "error": "#dc3545",
        "info": "#17a2b8",
    }

    return status_colors.get(status.lower(), "#6c757d")

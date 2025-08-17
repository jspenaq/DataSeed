"""
Filter components for DataSeed Dashboard.

This module provides reusable filter components for the analytics page,
including time range selectors, source filters, and search inputs.
"""

from datetime import datetime, timedelta
from typing import Any

import streamlit as st


def render_time_window_selector(key: str = "time_window", default: str = "24h") -> str:
    """
    Render time window selector for analytics filtering.

    Args:
        key: Unique key for the widget
        default: Default time window value

    Returns:
        Selected time window string
    """
    options = {
        "1h": "Last Hour",
        "24h": "Last 24 Hours",
        "7d": "Last 7 Days",
        "30d": "Last 30 Days",
        "90d": "Last 90 Days",
    }

    selected = st.selectbox(
        "Time Window",
        options=list(options.keys()),
        format_func=lambda x: options[x],
        index=list(options.keys()).index(default) if default in options else 1,
        key=key,
        help="Select the time period for analytics data",
    )

    return selected


def render_source_multiselect(
    available_sources: list[str],
    key: str = "source_filter",
    default: list[str] | None = None,
) -> list[str]:
    """
    Render multi-select widget for source filtering.

    Args:
        available_sources: List of available source names
        key: Unique key for the widget
        default: Default selected sources

    Returns:
        List of selected source names
    """
    if default is None:
        default = []

    selected = st.multiselect(
        "Data Sources",
        options=available_sources,
        default=default,
        key=key,
        help="Select one or more data sources to include in analytics",
    )

    return selected


def render_search_input(
    key: str = "search_query",
    default: str = "",
    placeholder: str = "Search titles and content...",
) -> str:
    """
    Render search input for content filtering.

    Args:
        key: Unique key for the widget
        default: Default search value
        placeholder: Placeholder text

    Returns:
        Search query string
    """
    query = st.text_input(
        "Search Query",
        value=default,
        placeholder=placeholder,
        key=key,
        help="Search across item titles and content",
    )

    return query.strip()


def render_date_range_picker(key: str = "date_range", default_days: int = 7) -> tuple[datetime, datetime]:
    """
    Render date range picker for custom time filtering.

    Args:
        key: Unique key for the widget
        default_days: Default number of days to look back

    Returns:
        Tuple of (start_date, end_date)
    """
    col1, col2 = st.columns(2)

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=default_days)

    with col1:
        start = st.date_input(
            "Start Date",
            value=start_date,
            key=f"{key}_start",
            help="Start date for the analysis period",
        )

    with col2:
        end = st.date_input("End Date", value=end_date, key=f"{key}_end", help="End date for the analysis period")

    # Convert to datetime objects
    start_datetime = datetime.combine(start, datetime.min.time())
    end_datetime = datetime.combine(end, datetime.max.time())

    return start_datetime, end_datetime


def render_analytics_filters(available_sources: list[str], key_prefix: str = "analytics") -> dict[str, Any]:
    """
    Render complete analytics filter panel.

    Args:
        available_sources: List of available source names
        key_prefix: Prefix for widget keys to avoid conflicts

    Returns:
        Dictionary containing all filter values
    """
    st.subheader("🔍 Filters")

    # Time window selector
    time_window = render_time_window_selector(key=f"{key_prefix}_time_window")

    # Source filter
    selected_sources = render_source_multiselect(available_sources=available_sources, key=f"{key_prefix}_sources")

    # Search query
    search_query = render_search_input(key=f"{key_prefix}_search")

    # Advanced filters in expander
    with st.expander("Advanced Filters", expanded=False):
        # Custom date range option
        use_custom_dates = st.checkbox(
            "Use Custom Date Range",
            key=f"{key_prefix}_use_custom_dates",
            help="Override time window with custom date range",
        )

        custom_start, custom_end = None, None
        if use_custom_dates:
            custom_start, custom_end = render_date_range_picker(key=f"{key_prefix}_custom_dates")

        # Score range filter
        score_filter = st.checkbox(
            "Filter by Score Range",
            key=f"{key_prefix}_use_score_filter",
            help="Filter items by score/engagement range",
        )

        min_score, max_score = None, None
        if score_filter:
            col1, col2 = st.columns(2)
            with col1:
                min_score = st.number_input("Min Score", min_value=0, value=0, key=f"{key_prefix}_min_score")
            with col2:
                max_score = st.number_input("Max Score", min_value=0, value=1000, key=f"{key_prefix}_max_score")

    # Reset filters button
    if st.button("🔄 Reset Filters", key=f"{key_prefix}_reset"):
        # Clear session state for this filter set
        keys_to_clear = [
            f"{key_prefix}_time_window",
            f"{key_prefix}_sources",
            f"{key_prefix}_search",
            f"{key_prefix}_use_custom_dates",
            f"{key_prefix}_custom_dates_start",
            f"{key_prefix}_custom_dates_end",
            f"{key_prefix}_use_score_filter",
            f"{key_prefix}_min_score",
            f"{key_prefix}_max_score",
        ]

        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]

        st.rerun()

    return {
        "time_window": time_window,
        "sources": selected_sources,
        "search_query": search_query,
        "use_custom_dates": use_custom_dates,
        "custom_start": custom_start,
        "custom_end": custom_end,
        "score_filter": score_filter,
        "min_score": min_score,
        "max_score": max_score,
    }


def render_chart_controls(key_prefix: str = "chart") -> dict[str, Any]:
    """
    Render controls for chart customization.

    Args:
        key_prefix: Prefix for widget keys

    Returns:
        Dictionary containing chart control values
    """
    st.subheader("📊 Chart Options")

    col1, col2 = st.columns(2)

    with col1:
        # Chart height
        chart_height = st.slider(
            "Chart Height",
            min_value=300,
            max_value=800,
            value=400,
            step=50,
            key=f"{key_prefix}_height",
            help="Adjust the height of charts",
        )

        # Histogram bins
        histogram_bins = st.slider(
            "Histogram Bins",
            min_value=10,
            max_value=50,
            value=20,
            key=f"{key_prefix}_bins",
            help="Number of bins for score distribution histogram",
        )

    with col2:
        # Chart theme
        chart_theme = st.selectbox(
            "Chart Theme",
            options=["plotly", "plotly_white", "plotly_dark", "ggplot2", "seaborn"],
            index=1,
            key=f"{key_prefix}_theme",
            help="Visual theme for charts",
        )

        # Animation
        enable_animation = st.checkbox(
            "Enable Animations",
            value=True,
            key=f"{key_prefix}_animation",
            help="Enable chart animations and transitions",
        )

    return {"height": chart_height, "bins": histogram_bins, "theme": chart_theme, "animation": enable_animation}


def render_export_controls(key_prefix: str = "export") -> dict[str, Any]:
    """
    Render controls for data export options.

    Args:
        key_prefix: Prefix for widget keys

    Returns:
        Dictionary containing export control values
    """
    st.subheader("📤 Export Options")

    col1, col2 = st.columns(2)

    with col1:
        # Export format
        export_format = st.selectbox(
            "Export Format",
            options=["CSV", "JSON", "Excel"],
            key=f"{key_prefix}_format",
            help="Choose the format for data export",
        )

        # Include metadata
        include_metadata = st.checkbox(
            "Include Metadata",
            value=True,
            key=f"{key_prefix}_metadata",
            help="Include source and timestamp information",
        )

    with col2:
        # Max rows
        max_rows = st.number_input(
            "Max Rows",
            min_value=100,
            max_value=10000,
            value=1000,
            step=100,
            key=f"{key_prefix}_max_rows",
            help="Maximum number of rows to export",
        )

        # Filename prefix
        filename_prefix = st.text_input(
            "Filename Prefix",
            value="dataseed_analytics",
            key=f"{key_prefix}_filename",
            help="Prefix for exported filename",
        )

    return {
        "format": export_format,
        "include_metadata": include_metadata,
        "max_rows": max_rows,
        "filename_prefix": filename_prefix,
    }

"""
Overview Page - DataSeed Dashboard

Main dashboard page showing recent content, search functionality, and key metrics.
This page provides the primary interface for exploring data from all sources.
"""

import json
from datetime import datetime

import pandas as pd
import streamlit as st

from dashboard.api import get_api_client, run_async
from dashboard.state import get_dashboard_state
from dashboard.telemetry import track_export_action
from dashboard.ui import (
    format_timestamp,
    render_auto_refresh_page_wrapper,
    render_health_badge,
    render_kpi_card,
    render_page_header,
    truncate_text,
)


def render_overview_kpis():
    """Render key performance indicators for the overview with mobile responsiveness."""
    try:
        api_client = get_api_client()

        # Fetch stats from API
        with st.spinner("Loading KPIs..."):
            stats_data = run_async(api_client.get_stats(window="24h"))

        # Check if mobile for responsive layout
        is_mobile = st.session_state.get("is_mobile", False)

        if is_mobile:
            # Stack KPI cards vertically on mobile
            st.markdown('<div class="kpi-mobile-container">', unsafe_allow_html=True)

            render_kpi_card(
                title="Total Items",
                value=f"{stats_data.get('total_items', 0):,}",
                delta=f"+{stats_data.get('new_last_window', 0)}",
                help_text="Total content items across all sources",
            )

            render_kpi_card(
                title="Success Rate",
                value=f"{98.5:.1f}%",  # Placeholder
                delta="+0.2%",
                help_text="Ingestion success rate in the last 24 hours",
            )

            render_kpi_card(
                title="Avg Ingestion Lag",
                value="2.3 min",  # Placeholder
                delta="-0.5 min",
                delta_color="inverse",
                help_text="Average time between publication and ingestion",
            )

            render_kpi_card(
                title="Total Errors",
                value="3",  # Placeholder
                delta="-2",
                delta_color="inverse",
                help_text="Total ingestion errors in the last 24 hours",
            )

            st.markdown("</div>", unsafe_allow_html=True)
        else:
            # Use columns on desktop/tablet
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                render_kpi_card(
                    title="Total Items",
                    value=f"{stats_data.get('total_items', 0):,}",
                    delta=f"+{stats_data.get('new_last_window', 0)}",
                    help_text="Total content items across all sources",
                )

            with col2:
                # Calculate success rate (placeholder - would need ingestion run data)
                success_rate = 98.5  # Placeholder
                render_kpi_card(
                    title="Success Rate",
                    value=f"{success_rate:.1f}%",
                    delta="+0.2%",
                    help_text="Ingestion success rate in the last 24 hours",
                )

            with col3:
                # Average ingestion lag (placeholder)
                avg_lag = "2.3 min"
                render_kpi_card(
                    title="Avg Ingestion Lag",
                    value=avg_lag,
                    delta="-0.5 min",
                    delta_color="inverse",
                    help_text="Average time between publication and ingestion",
                )

            with col4:
                # Total errors (placeholder)
                total_errors = 3
                render_kpi_card(
                    title="Total Errors",
                    value=str(total_errors),
                    delta="-2",
                    delta_color="inverse",
                    help_text="Total ingestion errors in the last 24 hours",
                )

    except Exception as e:
        st.error(f"Failed to load KPIs: {str(e)}")
        # Show placeholder KPIs with responsive layout
        is_mobile = st.session_state.get("is_mobile", False)

        if is_mobile:
            render_kpi_card("Total Items", "Loading...", help_text="Total content items across all sources")
            render_kpi_card("Success Rate", "Loading...", help_text="Ingestion success rate in the last 24 hours")
            render_kpi_card(
                "Avg Ingestion Lag",
                "Loading...",
                help_text="Average time between publication and ingestion",
            )
            render_kpi_card("Total Errors", "Loading...", help_text="Total ingestion errors in the last 24 hours")
        else:
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                render_kpi_card("Total Items", "Loading...", help_text="Total content items across all sources")
            with col2:
                render_kpi_card("Success Rate", "Loading...", help_text="Ingestion success rate in the last 24 hours")
            with col3:
                render_kpi_card(
                    "Avg Ingestion Lag",
                    "Loading...",
                    help_text="Average time between publication and ingestion",
                )
            with col4:
                render_kpi_card("Total Errors", "Loading...", help_text="Total ingestion errors in the last 24 hours")


def render_system_health():
    """Render system health status with mobile responsiveness."""
    st.subheader("System Health")

    try:
        api_client = get_api_client()

        with st.spinner("Checking system health..."):
            health_data = run_async(api_client.get_health())

        checks = health_data.get("checks", {})
        is_mobile = st.session_state.get("is_mobile", False)

        if is_mobile:
            # Stack health checks vertically on mobile
            st.markdown("**API**")
            api_status = checks.get("api", {}).get("status", "unknown")
            render_health_badge(api_status, checks.get("api", {}).get("details"))

            st.markdown("**Database**")
            db_status = checks.get("database", {}).get("status", "unknown")
            render_health_badge(db_status, checks.get("database", {}).get("details"))

            st.markdown("**Redis**")
            redis_status = checks.get("redis", {}).get("status", "unknown")
            render_health_badge(redis_status, checks.get("redis", {}).get("details"))
        else:
            # Create columns for each service on desktop
            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown("**API**")
                api_status = checks.get("api", {}).get("status", "unknown")
                render_health_badge(api_status, checks.get("api", {}).get("details"))

            with col2:
                st.markdown("**Database**")
                db_status = checks.get("database", {}).get("status", "unknown")
                render_health_badge(db_status, checks.get("database", {}).get("details"))

            with col3:
                st.markdown("**Redis**")
                redis_status = checks.get("redis", {}).get("status", "unknown")
                render_health_badge(redis_status, checks.get("redis", {}).get("details"))

        # Overall status
        overall_status = health_data.get("status", "unknown")
        st.markdown(f"**Overall Status**: {overall_status.title()}")

    except Exception as e:
        st.error(f"Failed to check system health: {str(e)}")
        is_mobile = st.session_state.get("is_mobile", False)

        if is_mobile:
            st.markdown("**API**")
            render_health_badge("unknown")
            st.markdown("**Database**")
            render_health_badge("unknown")
            st.markdown("**Redis**")
            render_health_badge("unknown")
        else:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**API**")
                render_health_badge("unknown")
            with col2:
                st.markdown("**Database**")
                render_health_badge("unknown")
            with col3:
                st.markdown("**Redis**")
                render_health_badge("unknown")


def render_trending_now():
    """Render trending items section."""
    st.subheader("Trending Now")

    try:
        api_client = get_api_client()

        with st.spinner("Loading trending items..."):
            trending_items = run_async(api_client.get_trending_items(window="24h", limit=10, use_hot_score=True))

        if not trending_items:
            st.info("No trending items found in the last 24 hours.")
            return

        # Display trending items
        for i, item in enumerate(trending_items, 1):
            with st.container():
                col1, col2, col3, col4 = st.columns([0.5, 3, 1, 1])

                with col1:
                    st.markdown(f"**{i}**")

                with col2:
                    title = truncate_text(item.get("title", "No title"), 80)
                    url = item.get("url", "")
                    if url:
                        st.markdown(f"[{title}]({url})")
                    else:
                        st.markdown(title)

                with col3:
                    source_name = (
                        item.get("source", {}).get("name", "Unknown")
                        if isinstance(item.get("source"), dict)
                        else "Unknown"
                    )
                    st.caption(source_name.title())

                with col4:
                    score = item.get("score", 0)
                    published_at = item.get("published_at")
                    if published_at:
                        try:
                            if isinstance(published_at, str):
                                pub_time = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                            else:
                                pub_time = published_at
                            time_str = format_timestamp(pub_time, "relative")
                        except:
                            time_str = "Unknown"
                    else:
                        time_str = "Unknown"

                    st.caption(f"Score: {score}")
                    st.caption(time_str)

                if i < len(trending_items):
                    st.divider()

    except Exception as e:
        st.error(f"Failed to load trending items: {str(e)}")


def render_latest_items_table():
    """Render the latest items table with filters and export."""
    st.subheader("Latest Items")

    state = get_dashboard_state()

    # Filters
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        # Source filter
        source_options = ["All Sources", "hackernews", "reddit", "github", "producthunt"]
        selected_source = st.selectbox(
            "Source",
            options=source_options,
            index=0
            if not state.filters.source
            else source_options.index(state.filters.source)
            if state.filters.source in source_options
            else 0,
            key="overview_source_filter",
        )

        # Update state if changed
        new_source = None if selected_source == "All Sources" else selected_source
        if new_source != state.filters.source:
            state.update_filter(source=new_source)

    with col2:
        # Search filter
        search_query = st.text_input(
            "Search",
            value=state.filters.search_query or "",
            placeholder="Search titles and content...",
            key="overview_search_filter",
        )

        # Update state if changed
        if search_query != state.filters.search_query:
            state.update_filter(search_query=search_query)

    with col3:
        # Refresh button
        if st.button("🔄 Refresh", key="refresh_items"):
            state.clear_cache("latest_items")
            st.rerun()

    try:
        api_client = get_api_client()

        # Check cache first
        cache_key = "latest_items"
        cached_data = state.get_cached_data(cache_key)

        if cached_data is None:
            with st.spinner("Loading latest items..."):
                response = run_async(
                    api_client.get_items(
                        source=state.filters.source,
                        q=state.filters.search_query,
                        sort="published_at",
                        order="desc",
                        limit=50,
                    ),
                )

                items = response.get("items", [])
                state.cache_data(cache_key, items, ttl_minutes=2)
        else:
            items = cached_data

        if not items:
            st.info("No items found. Try adjusting your filters.")
            return

        # Prepare data for display
        display_data = []
        for item in items:
            # Handle source data
            source_info = item.get("source", {})
            if isinstance(source_info, dict):
                source_name = source_info.get("name", "Unknown")
            else:
                source_name = "Unknown"

            # Handle published_at
            published_at = item.get("published_at")
            if published_at:
                try:
                    if isinstance(published_at, str):
                        pub_time = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                    else:
                        pub_time = published_at
                    formatted_time = pub_time.strftime("%Y-%m-%d %H:%M")
                except:
                    formatted_time = "Unknown"
            else:
                formatted_time = "Unknown"

            display_data.append(
                {
                    "Title": truncate_text(item.get("title", "No title"), 60),
                    "Source": source_name.title(),
                    "Score": item.get("score", 0) or 0,
                    "Published": formatted_time,
                    "URL": item.get("url", ""),
                },
            )

        # Display table
        if display_data:
            df = pd.DataFrame(display_data)

            # Make titles clickable if URL exists
            def make_clickable(row):
                if row["URL"]:
                    return f'<a href="{row["URL"]}" target="_blank">{row["Title"]}</a>'
                return row["Title"]

            # Display the dataframe
            st.dataframe(df[["Title", "Source", "Score", "Published"]], use_container_width=True, hide_index=True)

            # Export functionality
            st.markdown("---")
            col1, col2 = st.columns(2)

            with col1:
                # CSV Export
                csv_data = df.to_csv(index=False)
                csv_filename = f"dataseed_items_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                if st.download_button(label="📄 Export CSV", data=csv_data, file_name=csv_filename, mime="text/csv"):
                    track_export_action("csv", "overview_items", len(df), csv_filename)

            with col2:
                # JSON Export
                json_data = json.dumps([item for item in items], indent=2, default=str)
                json_filename = f"dataseed_items_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                if st.download_button(
                    label="📋 Export JSON",
                    data=json_data,
                    file_name=json_filename,
                    mime="application/json",
                ):
                    track_export_action("json", "overview_items", len(items), json_filename)

    except Exception as e:
        st.error(f"Failed to load items: {str(e)}")


def render_overview_content():
    """Render the main overview page content (without auto-refresh wrapper) with mobile responsiveness."""
    # Header KPIs
    render_overview_kpis()

    st.markdown("---")

    # System Health and Trending - responsive layout
    is_mobile = st.session_state.get("is_mobile", False)

    if is_mobile:
        # Stack vertically on mobile
        render_system_health()
        st.markdown("---")
        render_trending_now()
    else:
        # Side by side on desktop
        col1, col2 = st.columns([1, 1])

        with col1:
            render_system_health()

        with col2:
            render_trending_now()

    st.markdown("---")

    # Latest Items Table
    render_latest_items_table()


def render_overview_page():
    """Main function to render the overview page with auto-refresh functionality."""
    state = get_dashboard_state()
    api_client = get_api_client()

    # Page header
    render_page_header(
        title="Overview",
        description="Real-time insights and latest content from all data sources",
        show_refresh=False,  # Auto-refresh wrapper handles refresh
    )

    # Use the auto-refresh wrapper
    render_auto_refresh_page_wrapper(
        page_content_func=render_overview_content,
        page_title="Overview",
        state=state,
        api_client=api_client,
        key_prefix="overview",
    )


# Helper functions for future enhancements


def calculate_time_ago(timestamp: datetime) -> str:
    """Calculate human-readable time ago string."""
    now = datetime.utcnow()
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=now.tzinfo)

    diff = now - timestamp

    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    if diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    if diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    return "Just now"


def get_source_color(source_name: str) -> str:
    """Get color for source display."""
    colors = {"hackernews": "#ff6600", "reddit": "#ff4500", "github": "#333333", "producthunt": "#da552f"}
    return colors.get(source_name.lower(), "#6c757d")

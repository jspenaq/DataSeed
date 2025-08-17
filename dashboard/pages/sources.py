"""
Sources Page - DataSeed Dashboard

Data source management page showing source status, configuration, and ingestion statistics.
Provides monitoring and management capabilities for all connected data sources.
"""

from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import streamlit as st

from dashboard.api import get_api_client, run_async
from dashboard.state import get_dashboard_state
from dashboard.ui import (
    format_timestamp,
    render_health_badge,
    render_kpi_card,
    render_page_header,
    truncate_text,
)


def get_health_status(source: dict[str, Any]) -> str:
    """Determine health status based on source statistics."""
    stats = source.get("stats", {})

    if stats.get("total_runs", 0) == 0:
        return "unknown"

    # Check if last run was recent (within 2 hours)
    last_successful = stats.get("last_successful_run")
    if last_successful:
        try:
            if isinstance(last_successful, str):
                last_time = datetime.fromisoformat(last_successful.replace("Z", "+00:00"))
            else:
                last_time = last_successful

            time_since_last = datetime.now() - last_time.replace(tzinfo=None)
            if time_since_last > timedelta(hours=2):
                return "degraded"
        except:
            pass

    # Check success rate
    success_rate = stats.get("success_rate", 0)
    if success_rate >= 95:
        return "healthy"
    if success_rate >= 80:
        return "degraded"
    return "failed"


def render_sources_overview(sources_data: dict[str, Any]):
    """Render overview metrics for all sources with mobile responsiveness."""
    is_mobile = st.session_state.get("is_mobile", False)

    # Calculate metrics
    total_ingestions = sum(source.get("stats", {}).get("total_runs", 0) for source in sources_data.get("sources", []))
    total_successful = sum(
        source.get("stats", {}).get("successful_runs", 0) for source in sources_data.get("sources", [])
    )
    success_rate = (total_successful / total_ingestions * 100) if total_ingestions > 0 else 0
    total_items = sum(
        source.get("stats", {}).get("total_items_processed", 0) for source in sources_data.get("sources", [])
    )
    avg_items = (total_items / total_ingestions) if total_ingestions > 0 else 0

    if is_mobile:
        # Stack KPI cards vertically on mobile
        render_kpi_card(
            title="Active Sources",
            value=str(sources_data.get("total", 0)),
            delta=None,
            help_text="Number of configured and active data sources",
        )

        render_kpi_card(
            title="Total Ingestions",
            value=f"{total_ingestions:,}",
            delta=None,
            help_text="Total ingestion runs across all sources (last 7 days)",
        )

        render_kpi_card(
            title="Success Rate",
            value=f"{success_rate:.1f}%",
            delta=None,
            help_text="Overall ingestion success rate (last 7 days)",
        )

        render_kpi_card(
            title="Avg Items/Run",
            value=f"{avg_items:.0f}",
            delta=None,
            help_text="Average items processed per ingestion run",
        )
    else:
        # Use columns on desktop
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            render_kpi_card(
                title="Active Sources",
                value=str(sources_data.get("total", 0)),
                delta=None,
                help_text="Number of configured and active data sources",
            )

        with col2:
            render_kpi_card(
                title="Total Ingestions",
                value=f"{total_ingestions:,}",
                delta=None,
                help_text="Total ingestion runs across all sources (last 7 days)",
            )

        with col3:
            render_kpi_card(
                title="Success Rate",
                value=f"{success_rate:.1f}%",
                delta=None,
                help_text="Overall ingestion success rate (last 7 days)",
            )

        with col4:
            render_kpi_card(
                title="Avg Items/Run",
                value=f"{avg_items:.0f}",
                delta=None,
                help_text="Average items processed per ingestion run",
            )


def render_source_card(source: dict[str, Any]):
    """Render individual source status card with mobile responsiveness."""
    stats = source.get("stats", {})
    health_status = get_health_status(source)
    is_mobile = st.session_state.get("is_mobile", False)

    with st.container():
        st.markdown('<div class="source-card">', unsafe_allow_html=True)

        # Header with source name and health
        if is_mobile:
            # Stack header elements on mobile
            st.markdown(f"### {source.get('name', 'Unknown').title()}")
            render_health_badge(health_status)
        else:
            # Side by side on desktop
            col_header1, col_header2 = st.columns([3, 1])
            with col_header1:
                st.markdown(f"### {source.get('name', 'Unknown').title()}")
            with col_header2:
                render_health_badge(health_status)

        if is_mobile:
            # Stack all info vertically on mobile
            st.markdown(f"**Type:** {source.get('type', 'Unknown')}")
            st.markdown(f"**Base URL:** {truncate_text(source.get('base_url', 'N/A'), 30)}")
            st.markdown(f"**Rate Limit:** {source.get('rate_limit', 'N/A')} req/min")

            st.markdown("**Last Ingestion:**")
            last_successful = stats.get("last_successful_run")
            if last_successful:
                try:
                    if isinstance(last_successful, str):
                        last_time = datetime.fromisoformat(last_successful.replace("Z", "+00:00"))
                    else:
                        last_time = last_successful
                    st.caption(format_timestamp(last_time, "relative"))
                except:
                    st.caption("Unknown")
            else:
                st.caption("No successful runs")

            # Last run status
            last_status = stats.get("last_run_status", "unknown")
            status_emoji = {"completed": "✅", "failed": "❌", "running": "🔄"}.get(last_status, "❓")
            st.caption(f"Status: {status_emoji} {last_status.title()}")

            # Quick stats
            items_24h = stats.get("items_last_24h", 0)
            success_rate = stats.get("success_rate", 0)

            col_metric1, col_metric2 = st.columns(2)
            with col_metric1:
                st.metric("Items (24h)", f"{items_24h:,}")
            with col_metric2:
                st.metric("Success Rate", f"{success_rate:.1f}%")
        else:
            # Main info columns for desktop
            col1, col2, col3 = st.columns([2, 1, 1])

            with col1:
                st.markdown(f"**Type:** {source.get('type', 'Unknown')}")
                st.markdown(f"**Base URL:** {truncate_text(source.get('base_url', 'N/A'), 40)}")
                st.markdown(f"**Rate Limit:** {source.get('rate_limit', 'N/A')} req/min")

            with col2:
                # Last ingestion info
                st.markdown("**Last Ingestion:**")
                last_successful = stats.get("last_successful_run")
                if last_successful:
                    try:
                        if isinstance(last_successful, str):
                            last_time = datetime.fromisoformat(last_successful.replace("Z", "+00:00"))
                        else:
                            last_time = last_successful
                        st.caption(format_timestamp(last_time, "relative"))
                    except:
                        st.caption("Unknown")
                else:
                    st.caption("No successful runs")

                # Last run status
                last_status = stats.get("last_run_status", "unknown")
                status_emoji = {"completed": "✅", "failed": "❌", "running": "🔄"}.get(last_status, "❓")
                st.caption(f"Status: {status_emoji} {last_status.title()}")

            with col3:
                # Quick stats
                items_24h = stats.get("items_last_24h", 0)
                st.metric("Items (24h)", f"{items_24h:,}")

                success_rate = stats.get("success_rate", 0)
                st.metric("Success Rate", f"{success_rate:.1f}%")

        # Expandable details
        with st.expander("View Details", expanded=False):
            detail_col1, detail_col2 = st.columns(2)

            with detail_col1:
                st.markdown("**Statistics (Last 7 days):**")
                st.text(f"Total Runs: {stats.get('total_runs', 0)}")
                st.text(f"Successful: {stats.get('successful_runs', 0)}")
                st.text(f"Failed: {stats.get('failed_runs', 0)}")
                st.text(f"Total Items: {stats.get('total_items_processed', 0):,}")

                median_duration = stats.get("median_duration_seconds")
                if median_duration:
                    st.text(f"Median Duration: {median_duration:.1f}s")

            with detail_col2:
                st.markdown("**Recent Runs:**")
                recent_runs = source.get("recent_runs", [])
                if recent_runs:
                    for run in recent_runs[:3]:  # Show last 3 runs
                        status = run.get("status", "unknown")
                        items = run.get("items_processed", 0)
                        started_at = run.get("started_at")

                        if started_at:
                            try:
                                if isinstance(started_at, str):
                                    start_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                                else:
                                    start_time = started_at
                                time_str = start_time.strftime("%m/%d %H:%M")
                            except:
                                time_str = "Unknown"
                        else:
                            time_str = "Unknown"

                        status_emoji = {"completed": "✅", "failed": "❌", "running": "🔄"}.get(status, "❓")
                        st.caption(f"{status_emoji} {time_str} - {items} items")
                else:
                    st.caption("No recent runs")


def render_sources_grid(
    sources_data: dict[str, Any],
    status_filter: str | None = None,
    search_filter: str | None = None,
):
    """Render sources in a responsive grid layout with filtering."""
    sources = sources_data.get("sources", [])

    if not sources:
        st.info("No sources found. Make sure the API is running and sources are configured.")
        return

    # Apply filters
    filtered_sources = sources

    if status_filter and status_filter != "All":
        filtered_sources = [s for s in filtered_sources if get_health_status(s) == status_filter.lower()]

    if search_filter:
        filtered_sources = [s for s in filtered_sources if search_filter.lower() in s.get("name", "").lower()]

    if not filtered_sources:
        st.info("No sources match the current filters.")
        return

    is_mobile = st.session_state.get("is_mobile", False)

    if is_mobile:
        # Single column layout on mobile
        for i, source in enumerate(filtered_sources):
            render_source_card(source)
            if i < len(filtered_sources) - 1:  # Don't add separator after last item
                st.markdown("---")
    else:
        # 2-column grid on desktop
        for i in range(0, len(filtered_sources), 2):
            col1, col2 = st.columns(2)

            with col1:
                render_source_card(filtered_sources[i])

            if i + 1 < len(filtered_sources):
                with col2:
                    render_source_card(filtered_sources[i + 1])

            if i + 2 < len(filtered_sources):  # Don't add separator after last row
                st.markdown("---")


def render_source_details_drawer(source_id: int):
    """Render detailed view for a specific source."""
    try:
        api_client = get_api_client()

        with st.spinner("Loading source details..."):
            details = run_async(api_client.get_source_details(source_id, runs_limit=10))

        source = details.get("source", {})
        ingestion_runs = details.get("ingestion_runs", [])
        lag_trend = details.get("lag_trend", [])

        st.subheader(f"Details: {source.get('name', 'Unknown').title()}")

        # Source info
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Configuration:**")
            st.json(
                {
                    "name": source.get("name"),
                    "type": source.get("type"),
                    "base_url": source.get("base_url"),
                    "rate_limit": source.get("rate_limit"),
                    "is_active": source.get("is_active"),
                },
            )

        with col2:
            st.markdown("**Statistics:**")
            stats = source.get("stats", {})
            st.json(
                {
                    "total_runs": stats.get("total_runs"),
                    "success_rate": f"{stats.get('success_rate', 0):.1f}%",
                    "total_items_processed": stats.get("total_items_processed"),
                    "items_last_24h": stats.get("items_last_24h"),
                    "avg_items_per_run": f"{stats.get('avg_items_per_run', 0):.1f}",
                },
            )

        # Lag trend sparkline
        if lag_trend:
            st.markdown("**Ingestion Lag Trend (Last 24h):**")
            # Create simple line chart data
            trend_df = pd.DataFrame(lag_trend)
            if not trend_df.empty:
                st.line_chart(trend_df.set_index("timestamp")["duration_seconds"])
            else:
                st.info("No trend data available")
        else:
            st.info("No lag trend data available for the last 24 hours")

        # Recent ingestion runs table
        st.markdown("**Recent Ingestion Runs:**")
        if ingestion_runs:
            runs_data = []
            for run in ingestion_runs:
                started_at = run.get("started_at")
                completed_at = run.get("completed_at")

                # Format timestamps
                if started_at:
                    try:
                        if isinstance(started_at, str):
                            start_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                        else:
                            start_time = started_at
                        start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        start_str = "Unknown"
                else:
                    start_str = "Unknown"

                if completed_at:
                    try:
                        if isinstance(completed_at, str):
                            end_time = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                        else:
                            end_time = completed_at
                        end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        end_str = "Unknown"
                else:
                    end_str = "Running..." if run.get("status") == "running" else "Unknown"

                # Format duration
                duration = run.get("duration_seconds")
                if duration:
                    if duration < 60:
                        duration_str = f"{duration:.1f}s"
                    else:
                        duration_str = f"{duration / 60:.1f}m"
                else:
                    duration_str = "N/A"

                # Status with emoji
                status = run.get("status", "unknown")
                status_emoji = {"completed": "✅", "failed": "❌", "running": "🔄"}.get(status, "❓")
                status_display = f"{status_emoji} {status.title()}"

                runs_data.append(
                    {
                        "Started": start_str,
                        "Completed": end_str,
                        "Duration": duration_str,
                        "Status": status_display,
                        "Items": run.get("items_processed", 0),
                        "New": run.get("items_new", 0),
                        "Updated": run.get("items_updated", 0),
                        "Failed": run.get("items_failed", 0),
                        "Errors": run.get("errors_count", 0),
                    },
                )

            if runs_data:
                df = pd.DataFrame(runs_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No ingestion runs found")
        else:
            st.info("No ingestion runs found")

    except Exception as e:
        st.error(f"Failed to load source details: {str(e)}")


def render_sources_page():
    """Main function to render the sources page."""
    # Page header
    render_page_header(
        title="Data Sources",
        description="Monitor and manage data source connections, ingestion status, and performance metrics",
        show_refresh=True,
    )

    state = get_dashboard_state()

    # Filters
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        status_options = ["All", "Healthy", "Degraded", "Failed"]
        status_filter = st.selectbox("Filter by Status", options=status_options, index=0, key="sources_status_filter")

    with col2:
        search_filter = st.text_input(
            "Search Sources",
            placeholder="Search by source name...",
            key="sources_search_filter",
        )

    with col3:
        if st.button("🔄 Refresh", key="refresh_sources"):
            state.clear_cache("sources_data")
            st.rerun()

    try:
        # Load sources data
        api_client = get_api_client()

        # Check cache first
        cache_key = "sources_data"
        cached_data = state.get_cached_data(cache_key)

        if cached_data is None:
            with st.spinner("Loading sources..."):
                # Apply filters at API level
                api_status_filter = status_filter.lower() if status_filter != "All" else None
                sources_data = run_async(
                    api_client.get_sources(status=api_status_filter, search=search_filter if search_filter else None),
                )
                state.cache_data(cache_key, sources_data, ttl_minutes=5)
        else:
            sources_data = cached_data

        # Sources overview KPIs
        render_sources_overview(sources_data)

        st.markdown("---")

        # Health summary
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Sources", sources_data.get("total", 0))
        with col2:
            st.metric("Healthy", sources_data.get("healthy", 0), delta_color="normal")
        with col3:
            st.metric("Degraded", sources_data.get("degraded", 0), delta_color="off")
        with col4:
            st.metric("Failed", sources_data.get("failed", 0), delta_color="inverse")

        st.markdown("---")

        # Main content
        st.markdown("### Source Status")

        # Check if user wants to see details for a specific source
        if "selected_source_id" in st.session_state and st.session_state.selected_source_id:
            col_back, col_main = st.columns([1, 4])
            with col_back:
                if st.button("← Back to Sources"):
                    st.session_state.selected_source_id = None
                    st.rerun()

            with col_main:
                render_source_details_drawer(st.session_state.selected_source_id)
        else:
            # Show sources grid
            render_sources_grid(sources_data, status_filter, search_filter)

            # Add source selection buttons (for demo purposes)
            if sources_data.get("sources"):
                st.markdown("---")
                st.markdown("**View Details:**")
                cols = st.columns(len(sources_data["sources"]))
                for i, source in enumerate(sources_data["sources"]):
                    with cols[i]:
                        if st.button(f"Details: {source['name'].title()}", key=f"details_{source['id']}"):
                            st.session_state.selected_source_id = source["id"]
                            st.rerun()

    except Exception as e:
        st.error(f"Failed to load sources: {str(e)}")
        # Show error details in expander
        with st.expander("Error Details"):
            st.code(str(e))


# Initialize session state
if "selected_source_id" not in st.session_state:
    st.session_state.selected_source_id = None

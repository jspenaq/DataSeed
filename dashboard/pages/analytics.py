"""
Analytics Page - DataSeed Dashboard

Real analytics and insights page showing trends, statistics, and data analysis across all sources.
Uses actual API data with interactive filtering, real-time charts, and CSV export functionality.
"""

from typing import Any

import pandas as pd
import streamlit as st

from dashboard.api import get_api_client, run_async
from dashboard.components.filters import render_analytics_filters, render_chart_controls
from dashboard.components.tables import render_data_table_with_export, render_summary_stats
from dashboard.state import get_dashboard_state
from dashboard.ui import render_auto_refresh_page_wrapper, render_kpi_card, render_page_header

# Import charts with fallback for missing plotly
try:
    from dashboard.components.charts import (
        render_items_over_time_chart,
        render_pie_chart,
        render_score_distribution_chart,
        render_top_sources_chart,
    )

    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False


def load_analytics_data(filters: dict[str, Any]) -> dict[str, Any]:
    """Load analytics data from API based on filters."""
    api_client = get_api_client()

    try:
        # Get basic stats
        stats = run_async(
            api_client.get_stats(
                window=filters["time_window"],
                source_name=filters["sources"][0] if len(filters["sources"]) == 1 else None,
            ),
        )

        # Get available sources
        sources_response = run_async(api_client.get_sources())
        available_sources = [s["name"] for s in sources_response.get("sources", [])]

        # Get items for detailed analysis
        items = run_async(
            api_client.get_items_for_analytics(
                window=filters["time_window"],
                sources=filters["sources"] if filters["sources"] else None,
                search_query=filters["search_query"] if filters["search_query"] else None,
                limit=1000,
            ),
        )

        # Get time series data
        time_series = run_async(
            api_client.get_time_series_data(
                window=filters["time_window"],
                sources=filters["sources"] if filters["sources"] else None,
            ),
        )

        # Get trending items
        trending = run_async(
            api_client.get_trending_items(
                window=filters["time_window"],
                source=filters["sources"][0] if len(filters["sources"]) == 1 else None,
                limit=20,
            ),
        )

        return {
            "stats": stats,
            "available_sources": available_sources,
            "items": items,
            "time_series": time_series,
            "trending": trending,
        }

    except Exception as e:
        st.error(f"Failed to load analytics data: {str(e)}")
        return {"stats": {}, "available_sources": [], "items": [], "time_series": [], "trending": []}


def render_analytics_overview(stats: dict[str, Any]) -> None:
    """Render overview analytics KPIs with mobile responsiveness."""
    is_mobile = st.session_state.get("is_mobile", False)

    # Prepare data
    new_items = stats.get("new_last_window", 0)
    top_sources = stats.get("top_sources", [])
    top_source = top_sources[0]["source_name"] if top_sources else "N/A"
    avg_score = stats.get("avg_score")

    if is_mobile:
        # Stack KPI cards vertically on mobile
        render_kpi_card(
            title="Total Items",
            value=f"{stats.get('total_items', 0):,}",
            help_text="Total content items across all sources",
        )

        render_kpi_card(title="New Items", value=f"{new_items:,}", help_text="New items in the selected time window")

        render_kpi_card(title="Top Source", value=top_source, help_text="Most active source by volume")

        if avg_score is not None:
            render_kpi_card(title="Avg Score", value=f"{avg_score:.1f}", help_text="Average engagement score per item")
        else:
            render_kpi_card(title="Avg Score", value="N/A", help_text="Average engagement score per item")
    else:
        # Use columns on desktop
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            render_kpi_card(
                title="Total Items",
                value=f"{stats.get('total_items', 0):,}",
                help_text="Total content items across all sources",
            )

        with col2:
            render_kpi_card(
                title="New Items",
                value=f"{new_items:,}",
                help_text="New items in the selected time window",
            )

        with col3:
            render_kpi_card(title="Top Source", value=top_source, help_text="Most active source by volume")

        with col4:
            if avg_score is not None:
                render_kpi_card(
                    title="Avg Score",
                    value=f"{avg_score:.1f}",
                    help_text="Average engagement score per item",
                )
            else:
                render_kpi_card(title="Avg Score", value="N/A", help_text="Average engagement score per item")


def render_charts_section(data: dict[str, Any], chart_controls: dict[str, Any]) -> None:
    """Render the charts section with real data and mobile responsiveness."""
    st.subheader("📊 Data Visualizations")

    if not CHARTS_AVAILABLE:
        st.warning("Charts require plotly package. Install with: pip install plotly")
        return

    is_mobile = st.session_state.get("is_mobile", False)
    chart_height = chart_controls["height"] if not is_mobile else 300  # Smaller height on mobile

    # Items over time chart
    if data["time_series"]:
        render_items_over_time_chart(data["time_series"], title="Items Ingested Over Time", height=chart_height)
    else:
        st.info("No time series data available")

    if is_mobile:
        # Stack charts vertically on mobile
        # Top sources chart
        if data["stats"].get("top_sources"):
            render_top_sources_chart(
                data["stats"]["top_sources"],
                title="Top Sources by Volume",
                height=chart_height // 2,
            )
        else:
            st.info("No source data available")

        # Score distribution chart
        if data["items"]:
            # Extract scores for histogram
            scores = [item.get("score") for item in data["items"] if item.get("score") is not None]
            if scores:
                score_data = [{"score": score} for score in scores]
                render_score_distribution_chart(
                    score_data,
                    title="Score Distribution",
                    height=chart_height // 2,
                    bins=chart_controls["bins"],
                )
            else:
                st.info("No score data available")
        else:
            st.info("No items data available")
    else:
        # Side by side on desktop
        col1, col2 = st.columns(2)

        with col1:
            # Top sources chart
            if data["stats"].get("top_sources"):
                render_top_sources_chart(
                    data["stats"]["top_sources"],
                    title="Top Sources by Volume",
                    height=chart_controls["height"] // 2,
                )
            else:
                st.info("No source data available")

        with col2:
            # Score distribution chart
            if data["items"]:
                # Extract scores for histogram
                scores = [item.get("score") for item in data["items"] if item.get("score") is not None]
                if scores:
                    score_data = [{"score": score} for score in scores]
                    render_score_distribution_chart(
                        score_data,
                        title="Score Distribution",
                        height=chart_controls["height"] // 2,
                        bins=chart_controls["bins"],
                    )
                else:
                    st.info("No score data available")
            else:
                st.info("No items data available")


def render_trending_section(trending_items: list[dict[str, Any]]) -> None:
    """Render trending items section."""
    st.subheader("🔥 Trending Items")

    if not trending_items:
        st.info("No trending items found for the selected filters")
        return

    # Format trending data for display
    trending_data = []
    for item in trending_items:
        trending_data.append(
            {
                "Title": item.get("title", "")[:80] + "..."
                if len(item.get("title", "")) > 80
                else item.get("title", ""),
                "Score": item.get("score", 0),
                "Source": item.get("source_id", "Unknown"),  # This would need source name lookup
                "Published": item.get("published_at", ""),
                "URL": item.get("url", ""),
            },
        )

    # Display as table
    df = pd.DataFrame(trending_data)
    st.dataframe(df, use_container_width=True)


def render_data_table_section(items: list[dict[str, Any]], filters: dict[str, Any]) -> None:
    """Render the data table section with export functionality."""
    st.subheader("📋 Raw Data")

    if not items:
        st.info("No data available for the selected filters")
        return

    # Format data for table display
    table_data = []
    for item in items:
        table_data.append(
            {
                "ID": item.get("id"),
                "Title": item.get("title", ""),
                "Score": item.get("score", 0),
                "Source ID": item.get("source_id"),
                "Published At": item.get("published_at", ""),
                "Created At": item.get("created_at", ""),
                "URL": item.get("url", ""),
            },
        )

    # Show summary stats
    render_summary_stats(table_data)

    st.markdown("---")

    # Render table with export
    render_data_table_with_export(
        data=table_data,
        title=f"Content Items ({len(table_data)} rows)",
        max_rows=1000,
        enable_export=True,
        filename_prefix="dataseed_analytics",
    )


def render_analytics_content():
    """Render the main analytics page content (without auto-refresh wrapper)."""
    # Get available sources for filters
    try:
        api_client = get_api_client()
        sources_response = run_async(api_client.get_sources())
        available_sources = [s["name"] for s in sources_response.get("sources", [])]
    except Exception as e:
        st.error(f"Failed to load sources: {str(e)}")
        available_sources = []

    # Sidebar filters
    with st.sidebar:
        filters = render_analytics_filters(available_sources=available_sources, key_prefix="analytics")

        st.markdown("---")

        chart_controls = render_chart_controls(key_prefix="analytics_chart")

    # Load data based on filters
    with st.spinner("Loading analytics data..."):
        data = load_analytics_data(filters)

    # Analytics overview KPIs
    render_analytics_overview(data["stats"])

    st.markdown("---")

    # Main content tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Charts", "🔥 Trending", "📋 Data Table", "📈 Summary"])

    with tab1:
        render_charts_section(data, chart_controls)

    with tab2:
        render_trending_section(data["trending"])

    with tab3:
        render_data_table_section(data["items"], filters)

    with tab4:
        st.subheader("📈 Analytics Summary")

        if data["stats"]:
            is_mobile = st.session_state.get("is_mobile", False)

            if is_mobile:
                # Stack summary sections vertically on mobile
                st.markdown("**Data Overview**")
                st.write(f"• Total items: {data['stats'].get('total_items', 0):,}")
                st.write(f"• New items (window): {data['stats'].get('new_last_window', 0):,}")
                st.write(f"• Max score: {data['stats'].get('max_score', 'N/A')}")
                st.write(f"• Average score: {data['stats'].get('avg_score', 'N/A')}")

                st.markdown("**Top Sources**")
                for source in data["stats"].get("top_sources", [])[:5]:
                    st.write(f"• {source['source_name']}: {source['item_count']:,} items")
            else:
                # Side by side on desktop
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**Data Overview**")
                    st.write(f"• Total items: {data['stats'].get('total_items', 0):,}")
                    st.write(f"• New items (window): {data['stats'].get('new_last_window', 0):,}")
                    st.write(f"• Max score: {data['stats'].get('max_score', 'N/A')}")
                    st.write(f"• Average score: {data['stats'].get('avg_score', 'N/A')}")

                with col2:
                    st.markdown("**Top Sources**")
                    for source in data["stats"].get("top_sources", [])[:5]:
                        st.write(f"• {source['source_name']}: {source['item_count']:,} items")

        # Filter summary
        st.markdown("**Applied Filters**")
        st.write(f"• Time window: {filters['time_window']}")
        st.write(f"• Sources: {', '.join(filters['sources']) if filters['sources'] else 'All'}")
        st.write(f"• Search query: {filters['search_query'] if filters['search_query'] else 'None'}")


def render_analytics_page():
    """Main function to render the analytics page with auto-refresh functionality."""
    state = get_dashboard_state()
    api_client = get_api_client()

    # Page header
    render_page_header(
        title="Analytics & Insights",
        description="Comprehensive analytics, trends, and insights across all data sources",
        show_refresh=False,  # Auto-refresh wrapper handles refresh
    )

    # Use the auto-refresh wrapper
    render_auto_refresh_page_wrapper(
        page_content_func=render_analytics_content,
        page_title="Analytics",
        state=state,
        api_client=api_client,
        key_prefix="analytics",
    )


# Main entry point
if __name__ == "__main__":
    render_analytics_page()

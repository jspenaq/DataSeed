"""
Chart components for DataSeed Dashboard using Plotly.

This module provides reusable chart components for visualizing data in the dashboard,
including line charts, bar charts, pie charts, and histograms.
"""

from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


def render_items_over_time_chart(data: list[dict[str, Any]], title: str = "Items Over Time", height: int = 400) -> None:
    """
    Render a line chart showing items ingested over time.

    Args:
        data: List of dictionaries with 'timestamp' and 'count' keys
        title: Chart title
        height: Chart height in pixels
    """
    if not data:
        st.info("No data available for time series chart")
        return

    df = pd.DataFrame(data)

    # Ensure timestamp is datetime
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])

    fig = px.line(
        df,
        x="timestamp",
        y="count",
        title=title,
        labels={"timestamp": "Time", "count": "Number of Items"},
        line_shape="spline",
    )

    fig.update_layout(
        height=height,
        showlegend=False,
        xaxis_title="Time",
        yaxis_title="Items Count",
        hovermode="x unified",
    )

    fig.update_traces(line=dict(width=3, color="#1f77b4"), hovertemplate="<b>%{y}</b> items<br>%{x}<extra></extra>")

    st.plotly_chart(fig, use_container_width=True)


def render_top_sources_chart(
    data: list[dict[str, Any]],
    title: str = "Top Sources by Volume",
    height: int = 400,
) -> None:
    """
    Render a bar chart showing top sources by item count.

    Args:
        data: List of dictionaries with 'source_name' and 'item_count' keys
        title: Chart title
        height: Chart height in pixels
    """
    if not data:
        st.info("No data available for sources chart")
        return

    df = pd.DataFrame(data)

    fig = px.bar(
        df,
        x="source_name",
        y="item_count",
        title=title,
        labels={"source_name": "Source", "item_count": "Number of Items"},
        color="item_count",
        color_continuous_scale="viridis",
    )

    fig.update_layout(
        height=height,
        showlegend=False,
        xaxis_title="Data Source",
        yaxis_title="Items Count",
        coloraxis_showscale=False,
    )

    fig.update_traces(hovertemplate="<b>%{x}</b><br>%{y} items<extra></extra>")

    st.plotly_chart(fig, use_container_width=True)


def render_score_distribution_chart(
    data: list[dict[str, Any]],
    title: str = "Score Distribution",
    height: int = 400,
    bins: int = 20,
) -> None:
    """
    Render a histogram showing the distribution of item scores.

    Args:
        data: List of dictionaries with 'score' key
        title: Chart title
        height: Chart height in pixels
        bins: Number of histogram bins
    """
    if not data:
        st.info("No data available for score distribution chart")
        return

    df = pd.DataFrame(data)

    # Filter out null scores
    df = df[df["score"].notna()]

    if df.empty:
        st.info("No score data available")
        return

    fig = px.histogram(
        df,
        x="score",
        nbins=bins,
        title=title,
        labels={"score": "Score", "count": "Number of Items"},
        color_discrete_sequence=["#2E86AB"],
    )

    fig.update_layout(height=height, showlegend=False, xaxis_title="Score", yaxis_title="Number of Items", bargap=0.1)

    fig.update_traces(hovertemplate="Score: %{x}<br>Count: %{y}<extra></extra>")

    st.plotly_chart(fig, use_container_width=True)


def render_pie_chart(
    data: list[dict[str, Any]],
    values_col: str,
    names_col: str,
    title: str = "Distribution",
    height: int = 400,
) -> None:
    """
    Render a pie chart for categorical data distribution.

    Args:
        data: List of dictionaries containing the data
        values_col: Column name for values
        names_col: Column name for labels
        title: Chart title
        height: Chart height in pixels
    """
    if not data:
        st.info("No data available for pie chart")
        return

    df = pd.DataFrame(data)

    fig = px.pie(
        df,
        values=values_col,
        names=names_col,
        title=title,
        color_discrete_sequence=px.colors.qualitative.Set3,
    )

    fig.update_layout(height=height, showlegend=True)

    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>%{value} items<br>%{percent}<extra></extra>",
    )

    st.plotly_chart(fig, use_container_width=True)


def render_multi_line_chart(
    data: list[dict[str, Any]],
    x_col: str,
    y_cols: list[str],
    title: str = "Multi-Series Chart",
    height: int = 400,
) -> None:
    """
    Render a multi-line chart for comparing multiple series.

    Args:
        data: List of dictionaries containing the data
        x_col: Column name for x-axis
        y_cols: List of column names for y-axis series
        title: Chart title
        height: Chart height in pixels
    """
    if not data:
        st.info("No data available for multi-line chart")
        return

    df = pd.DataFrame(data)

    fig = go.Figure()

    colors = px.colors.qualitative.Set1

    for i, col in enumerate(y_cols):
        if col in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df[x_col],
                    y=df[col],
                    mode="lines+markers",
                    name=col.replace("_", " ").title(),
                    line=dict(color=colors[i % len(colors)], width=3),
                    marker=dict(size=6),
                ),
            )

    fig.update_layout(
        title=title,
        height=height,
        xaxis_title=x_col.replace("_", " ").title(),
        yaxis_title="Count",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    st.plotly_chart(fig, use_container_width=True)


def render_heatmap(
    data: list[dict[str, Any]],
    x_col: str,
    y_col: str,
    z_col: str,
    title: str = "Activity Heatmap",
    height: int = 400,
) -> None:
    """
    Render a heatmap for showing activity patterns.

    Args:
        data: List of dictionaries containing the data
        x_col: Column name for x-axis
        y_col: Column name for y-axis
        z_col: Column name for values (color intensity)
        title: Chart title
        height: Chart height in pixels
    """
    if not data:
        st.info("No data available for heatmap")
        return

    df = pd.DataFrame(data)

    # Pivot the data for heatmap
    pivot_df = df.pivot(index=y_col, columns=x_col, values=z_col)

    fig = px.imshow(pivot_df, title=title, color_continuous_scale="viridis", aspect="auto")

    fig.update_layout(
        height=height,
        xaxis_title=x_col.replace("_", " ").title(),
        yaxis_title=y_col.replace("_", " ").title(),
    )

    st.plotly_chart(fig, use_container_width=True)


def render_gauge_chart(
    value: float,
    title: str = "Metric",
    min_val: float = 0,
    max_val: float = 100,
    height: int = 300,
) -> None:
    """
    Render a gauge chart for showing a single metric.

    Args:
        value: Current value
        title: Chart title
        min_val: Minimum value for the gauge
        max_val: Maximum value for the gauge
        height: Chart height in pixels
    """
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=value,
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": title},
            gauge={
                "axis": {"range": [None, max_val]},
                "bar": {"color": "darkblue"},
                "steps": [
                    {"range": [0, max_val * 0.5], "color": "lightgray"},
                    {"range": [max_val * 0.5, max_val * 0.8], "color": "gray"},
                ],
                "threshold": {"line": {"color": "red", "width": 4}, "thickness": 0.75, "value": max_val * 0.9},
            },
        ),
    )

    fig.update_layout(height=height)
    st.plotly_chart(fig, use_container_width=True)


def render_box_plot(
    data: list[dict[str, Any]],
    y_col: str,
    x_col: str | None = None,
    title: str = "Distribution Analysis",
    height: int = 400,
) -> None:
    """
    Render a box plot for showing data distribution.

    Args:
        data: List of dictionaries containing the data
        y_col: Column name for y-axis values
        x_col: Optional column name for grouping
        title: Chart title
        height: Chart height in pixels
    """
    if not data:
        st.info("No data available for box plot")
        return

    df = pd.DataFrame(data)

    if x_col and x_col in df.columns:
        fig = px.box(df, x=x_col, y=y_col, title=title)
    else:
        fig = px.box(df, y=y_col, title=title)

    fig.update_layout(height=height)
    st.plotly_chart(fig, use_container_width=True)

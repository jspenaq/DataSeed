"""
Table and export components for DataSeed Dashboard.

This module provides reusable table components and data export functionality
for the dashboard, including CSV export, pagination, and data formatting.
"""

import io
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from dashboard.telemetry import track_export_action


def render_data_table_with_export(
    data: list[dict[str, Any]],
    title: str = "Data Table",
    columns: list[str] | None = None,
    max_rows: int = 1000,
    enable_export: bool = True,
    filename_prefix: str = "dataseed_export",
) -> None:
    """
    Render a data table with export functionality.

    Args:
        data: List of dictionaries containing table data
        title: Table title
        columns: Optional list of columns to display
        max_rows: Maximum number of rows to display
        enable_export: Whether to show export buttons
        filename_prefix: Prefix for exported filenames
    """
    if not data:
        st.info("No data available")
        return

    # Convert to DataFrame
    df = pd.DataFrame(data)

    # Filter columns if specified
    if columns:
        available_columns = [col for col in columns if col in df.columns]
        if available_columns:
            df = df[available_columns]

    # Limit rows
    if len(df) > max_rows:
        st.warning(f"Showing first {max_rows} rows of {len(df)} total rows")
        df_display = df.head(max_rows)
    else:
        df_display = df

    # Display table
    st.subheader(title)
    st.dataframe(df_display, use_container_width=True)

    # Export buttons
    if enable_export:
        render_export_buttons(df, filename_prefix)


def render_export_buttons(df: pd.DataFrame, filename_prefix: str = "dataseed_export") -> None:
    """
    Render export buttons for DataFrame.

    Args:
        df: DataFrame to export
        filename_prefix: Prefix for exported filenames
    """
    if df.empty:
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    col1, col2, col3 = st.columns(3)

    with col1:
        # CSV Export
        csv_data = convert_to_csv(df)
        csv_filename = f"{filename_prefix}_{timestamp}.csv"
        if st.download_button(
            label="📄 Export CSV",
            data=csv_data,
            file_name=csv_filename,
            mime="text/csv",
            help="Download data as CSV file",
        ):
            track_export_action("csv", filename_prefix, len(df), csv_filename)

    with col2:
        # JSON Export
        json_data = convert_to_json(df)
        json_filename = f"{filename_prefix}_{timestamp}.json"
        if st.download_button(
            label="📋 Export JSON",
            data=json_data,
            file_name=json_filename,
            mime="application/json",
            help="Download data as JSON file",
        ):
            track_export_action("json", filename_prefix, len(df), json_filename)

    with col3:
        # Excel Export (if openpyxl is available)
        try:
            excel_data = convert_to_excel(df)
            excel_filename = f"{filename_prefix}_{timestamp}.xlsx"
            if st.download_button(
                label="📊 Export Excel",
                data=excel_data,
                file_name=excel_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Download data as Excel file",
            ):
                track_export_action("excel", filename_prefix, len(df), excel_filename)
        except ImportError:
            st.button("📊 Export Excel", disabled=True, help="Excel export requires openpyxl package")


def convert_to_csv(df: pd.DataFrame) -> str:
    """Convert DataFrame to CSV string."""
    return df.to_csv(index=False)


def convert_to_json(df: pd.DataFrame) -> str:
    """Convert DataFrame to JSON string."""
    # Convert datetime columns to ISO format strings
    df_copy = df.copy()
    for col in df_copy.columns:
        if df_copy[col].dtype == "datetime64[ns]":
            df_copy[col] = df_copy[col].dt.strftime("%Y-%m-%d %H:%M:%S")

    return df_copy.to_json(orient="records", indent=2)


def convert_to_excel(df: pd.DataFrame) -> bytes:
    """Convert DataFrame to Excel bytes."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Data")
    return output.getvalue()


def render_paginated_table(data: list[dict[str, Any]], page_size: int = 20, key: str = "paginated_table") -> None:
    """
    Render a paginated table.

    Args:
        data: List of dictionaries containing table data
        page_size: Number of rows per page
        key: Unique key for pagination state
    """
    if not data:
        st.info("No data available")
        return

    df = pd.DataFrame(data)
    total_rows = len(df)
    total_pages = (total_rows - 1) // page_size + 1

    # Page selector
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        current_page = st.selectbox(
            "Page",
            options=list(range(1, total_pages + 1)),
            index=0,
            key=f"{key}_page_selector",
            format_func=lambda x: f"Page {x} of {total_pages}",
        )

    # Calculate slice indices
    start_idx = (current_page - 1) * page_size
    end_idx = min(start_idx + page_size, total_rows)

    # Display current page data
    page_df = df.iloc[start_idx:end_idx]
    st.dataframe(page_df, use_container_width=True)

    # Show row info
    st.caption(f"Showing rows {start_idx + 1}-{end_idx} of {total_rows}")


def render_searchable_table(
    data: list[dict[str, Any]],
    searchable_columns: list[str],
    key: str = "searchable_table",
) -> None:
    """
    Render a table with search functionality.

    Args:
        data: List of dictionaries containing table data
        searchable_columns: List of columns to search in
        key: Unique key for search state
    """
    if not data:
        st.info("No data available")
        return

    df = pd.DataFrame(data)

    # Search input
    search_query = st.text_input("Search table", placeholder="Enter search terms...", key=f"{key}_search")

    # Filter data based on search
    if search_query:
        mask = pd.Series([False] * len(df))
        for col in searchable_columns:
            if col in df.columns:
                mask |= df[col].astype(str).str.contains(search_query, case=False, na=False)

        filtered_df = df[mask]

        if filtered_df.empty:
            st.info(f"No results found for '{search_query}'")
            return
        st.info(f"Found {len(filtered_df)} results for '{search_query}'")
    else:
        filtered_df = df

    # Display filtered table
    st.dataframe(filtered_df, use_container_width=True)


def format_table_data(
    data: list[dict[str, Any]],
    format_config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Format table data for display.

    Args:
        data: Raw data to format
        format_config: Configuration for formatting specific columns

    Returns:
        Formatted data
    """
    if not data or not format_config:
        return data

    formatted_data = []

    for row in data:
        formatted_row = row.copy()

        for column, config in format_config.items():
            if column in formatted_row:
                value = formatted_row[column]

                if config.get("type") == "datetime" and value:
                    # Format datetime
                    if isinstance(value, str):
                        try:
                            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                            formatted_row[column] = dt.strftime(config.get("format", "%Y-%m-%d %H:%M"))
                        except:
                            pass

                elif config.get("type") == "number" and value is not None:
                    # Format numbers
                    if config.get("format") == "comma":
                        formatted_row[column] = f"{value:,}"
                    elif config.get("format") == "percentage":
                        formatted_row[column] = f"{value:.1%}"

                elif config.get("type") == "truncate" and value:
                    # Truncate text
                    max_length = config.get("max_length", 50)
                    if len(str(value)) > max_length:
                        formatted_row[column] = str(value)[:max_length] + "..."

        formatted_data.append(formatted_row)

    return formatted_data


def render_summary_stats(data: list[dict[str, Any]]) -> None:
    """
    Render summary statistics for the data.

    Args:
        data: Data to analyze
    """
    if not data:
        return

    df = pd.DataFrame(data)

    st.subheader("📊 Summary Statistics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Rows", len(df))

    with col2:
        st.metric("Columns", len(df.columns))

    with col3:
        # Find numeric columns
        numeric_cols = df.select_dtypes(include=["number"]).columns
        if len(numeric_cols) > 0:
            st.metric("Numeric Columns", len(numeric_cols))
        else:
            st.metric("Numeric Columns", 0)

    with col4:
        # Find datetime columns
        datetime_cols = df.select_dtypes(include=["datetime64"]).columns
        if len(datetime_cols) > 0:
            st.metric("Date Columns", len(datetime_cols))
        else:
            st.metric("Date Columns", 0)

    # Show basic statistics for numeric columns
    if len(numeric_cols) > 0:
        st.subheader("Numeric Column Statistics")
        st.dataframe(df[numeric_cols].describe(), use_container_width=True)

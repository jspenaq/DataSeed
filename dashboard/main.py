"""
DataSeed Dashboard - Main Entry Point

Multi-page Streamlit application for exploring and analyzing data from the DataSeed pipeline.
Provides overview, source management, and analytics capabilities.
"""

import os

import streamlit as st

from dashboard.api import get_api_client
from dashboard.state import get_dashboard_state
from dashboard.telemetry import track_page_view

state = get_dashboard_state()  # <-- Ensure this is called before any state.ui access


def load_css():
    """Load custom CSS styles for mobile responsiveness."""
    css_path = os.path.join(os.path.dirname(__file__), "style.css")
    if os.path.exists(css_path):
        with open(css_path) as f:
            css_content = f.read()
        st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    else:
        st.warning("Custom CSS file not found. Some styling may be missing.")


def configure_page():
    """Configure Streamlit page settings."""
    # Detect mobile viewport
    is_mobile = st.session_state.get("is_mobile", False)
    initial_sidebar_state = "collapsed" if is_mobile else "expanded"

    st.set_page_config(
        page_title="DataSeed Dashboard",
        page_icon="🌱",
        layout="wide",
        initial_sidebar_state=initial_sidebar_state,
        menu_items={
            "Get Help": "https://github.com/your-org/dataseed",
            "Report a bug": "https://github.com/your-org/dataseed/issues",
            "About": """
            # DataSeed Dashboard
            
            A developer-friendly data pipeline dashboard for exploring content from multiple sources.
            
            **Version**: 0.1.0
            **Sources**: HackerNews, Reddit, GitHub, ProductHunt
            """,
        },
    )

    # Load custom CSS
    load_css()

    # Add mobile detection script
    st.markdown(
        """
    <script>
    function detectMobile() {
        return window.innerWidth <= 768;
    }
    
    function updateMobileState() {
        const isMobile = detectMobile();
        if (window.parent && window.parent.postMessage) {
            window.parent.postMessage({
                type: 'streamlit:setComponentValue',
                key: 'is_mobile',
                value: isMobile
            }, '*');
        }
    }
    
    // Check on load and resize
    window.addEventListener('load', updateMobileState);
    window.addEventListener('resize', updateMobileState);
    </script>
    """,
        unsafe_allow_html=True,
    )


def render_sidebar_navigation():
    """Render sidebar navigation menu with mobile-friendly design."""
    state = get_dashboard_state()
    is_mobile = st.session_state.get("is_mobile", False)

    # Mobile-friendly header
    if is_mobile:
        st.sidebar.markdown(
            """
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem;">
            <h2 style="margin: 0; font-size: 1.5rem;">🌱 DataSeed</h2>
        </div>
        """,
            unsafe_allow_html=True,
        )
    else:
        st.sidebar.title("🌱 DataSeed")

    st.sidebar.markdown("---")

    # Navigation menu
    pages = {
        "Overview": {"icon": "📊", "description": "Recent content and search"},
        "Sources": {"icon": "🔗", "description": "Data source management"},
        "Analytics": {"icon": "📈", "description": "Trends and statistics"},
    }

    # Mobile-optimized navigation
    if is_mobile:
        # Use selectbox for mobile to save space
        selected_page = st.sidebar.selectbox(
            "Navigate to:",
            options=list(pages.keys()),
            format_func=lambda x: f"{pages[x]['icon']} {x}",
            key="page_selector_mobile",
            help="Select a page to navigate",
        )
    else:
        # Use radio buttons for desktop
        selected_page = st.sidebar.radio(
            "Navigation",
            options=list(pages.keys()),
            format_func=lambda x: f"{pages[x]['icon']} {x}",
            key="page_selector",
        )

    # Update state if page changed
    if selected_page != state.ui.selected_page:
        state.update_ui(selected_page=selected_page)

    # Show page description (condensed on mobile)
    if is_mobile:
        st.sidebar.caption(f"*{pages[selected_page]['description']}*")
    else:
        st.sidebar.markdown(f"*{pages[selected_page]['description']}*")

    st.sidebar.markdown("---")

    return selected_page


def render_api_status():
    """Render API connection status in sidebar."""
    try:
        api_client = get_api_client()
        # This will be implemented when we add health checks
        st.sidebar.success("🟢 API Connected")
    except Exception as e:
        st.sidebar.error("🔴 API Disconnected")
        st.sidebar.caption(f"Error: {str(e)[:50]}...")


def load_page_content(page_name: str):
    """Load and render the selected page content."""
    try:
        # Track page view
        track_page_view(page_name)

        if page_name == "Overview":
            from dashboard.pages.overview import render_overview_page

            render_overview_page()
        elif page_name == "Sources":
            from dashboard.pages.sources import render_sources_page

            render_sources_page()
        elif page_name == "Analytics":
            from dashboard.pages.analytics import render_analytics_page

            render_analytics_page()
        else:
            st.error(f"Unknown page: {page_name}")

    except ImportError as e:
        st.error(f"Failed to load page '{page_name}': {str(e)}")
        st.info("This page is still under development.")

    except Exception as e:
        st.error(f"Error rendering page '{page_name}': {str(e)}")
        st.exception(e)


def render_footer():
    """Render dashboard footer with mobile responsiveness."""
    st.markdown("---")
    is_mobile = st.session_state.get("is_mobile", False)

    if is_mobile:
        # Stack footer items vertically on mobile
        st.markdown(
            """
        <div class="dashboard-footer text-center">
            <div class="mb-2">DataSeed Dashboard v0.1.0</div>
            <div class="mb-2">🔄 Auto-refresh: Disabled</div>
            <div>⏰ Last updated: Just now</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    else:
        # Use columns on desktop
        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            st.caption("DataSeed Dashboard v0.1.0 - Real-time data pipeline insights")

        with col2:
            st.caption("🔄 Auto-refresh: Disabled")  # Will be dynamic later

        with col3:
            st.caption("⏰ Last updated: Just now")  # Will be dynamic later


def handle_errors():
    """Handle and display any accumulated errors."""
    state = get_dashboard_state()
    errors = state.get_errors()

    if errors:
        st.sidebar.markdown("### ⚠️ Errors")
        for error in errors[-3:]:  # Show last 3 errors
            st.sidebar.error(error["message"])

        if st.sidebar.button("Clear Errors"):
            state.clear_errors()
            st.rerun()


def main():
    """Main application entry point."""
    # Configure page
    configure_page()

    # Initialize state
    state = get_dashboard_state()

    # Render sidebar navigation
    selected_page = render_sidebar_navigation()

    # Render API status
    render_api_status()

    # Handle any errors
    handle_errors()

    # Load and render page content
    load_page_content(selected_page)

    # Render footer
    render_footer()

    # Auto-refresh logic (placeholder for now)
    if state.should_refresh():
        state.mark_refreshed()
        st.rerun()


if __name__ == "__main__":
    main()

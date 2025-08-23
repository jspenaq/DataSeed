# DataSeed Dashboard Guide

This comprehensive guide covers all features and functionality of the DataSeed Dashboard, a Streamlit-based web interface for exploring and analyzing data from your DataSeed pipeline.

## Table of Contents

- [Getting Started](#getting-started)
- [Dashboard Overview](#dashboard-overview)
- [Pages and Features](#pages-and-features)
  - [Overview Page](#overview-page)
  - [Sources Page](#sources-page)
  - [Analytics Page](#analytics-page)
- [Auto-Refresh Feature](#auto-refresh-feature)
- [Data Export](#data-export)
- [Mobile Experience](#mobile-experience)
- [Telemetry and Monitoring](#telemetry-and-monitoring)
- [Troubleshooting](#troubleshooting)

## Getting Started

### Prerequisites

- DataSeed API running on `http://localhost:8000` (or configured URL)
- Python 3.12+ with Streamlit installed
- Web browser (Chrome, Firefox, Safari, Edge)

### Running the Dashboard

**Option 1: Using Docker Compose (Recommended)**
```bash
docker-compose up dashboard
```

**Option 2: Direct Streamlit Execution**
```bash
# Install dependencies
pip install -r requirements.txt

# Run the dashboard
streamlit run dashboard/main.py
```

**Option 3: Development Mode**
```bash
# With auto-reload for development
streamlit run dashboard/main.py --server.runOnSave true
```

The dashboard will be available at `http://localhost:8501`.

### Environment Configuration

Create a `.env` file in the project root with the following variables:

```env
# API Configuration
API_BASE_URL=http://localhost:8000

# Dashboard Customization
DASHBOARD_TITLE=DataSeed Dashboard
DASHBOARD_DESCRIPTION=Real-time data pipeline insights

# Telemetry Settings
TELEMETRY_ENABLED=true
TELEMETRY_LOG_FILE=logs/dashboard_telemetry.log

# Performance Settings
STREAMLIT_SERVER_MAX_UPLOAD_SIZE=200
STREAMLIT_SERVER_MAX_MESSAGE_SIZE=200
```

## Dashboard Overview

The DataSeed Dashboard provides a comprehensive interface for monitoring and analyzing your data pipeline. It consists of three main pages accessible via the sidebar navigation:

### Navigation

- **📊 Overview**: Real-time system status and latest content
- **🔗 Sources**: Data source management and monitoring
- **📈 Analytics**: Advanced analytics and trend analysis

### Key Features

- **Real-time Updates**: Auto-refresh functionality with configurable intervals
- **Mobile Responsive**: Optimized for desktop, tablet, and mobile devices
- **Data Export**: CSV, JSON, and Excel export capabilities
- **Advanced Filtering**: Search, source filtering, and time-based queries
- **Health Monitoring**: System status and performance indicators
- **Rate Limiting Awareness**: Intelligent handling of API rate limits

## Pages and Features

### Overview Page

The Overview page provides a high-level view of your data pipeline status and recent activity.

#### Key Performance Indicators (KPIs)

The top section displays four key metrics:

1. **Total Items**: Total number of content items across all sources
2. **Success Rate**: Ingestion success rate in the last 24 hours
3. **Avg Ingestion Lag**: Average time between publication and ingestion
4. **Total Errors**: Number of ingestion errors in the last 24 hours

#### System Health

Real-time health status for core system components:

- **API**: DataSeed API connectivity and response status
- **Database**: PostgreSQL connection and query performance
- **Redis**: Redis connectivity for caching and task queues

Health indicators:
- 🟢 **Healthy**: Component operating normally
- 🟡 **Degraded**: Component experiencing issues but functional
- 🔴 **Unhealthy**: Component not responding or failing

#### Trending Now

Displays the top 10 trending items from the last 24 hours, ranked by engagement score. Each item shows:

- **Rank**: Position in trending list
- **Title**: Content title (clickable link to original source)
- **Source**: Origin platform (HackerNews, Reddit, GitHub, ProductHunt)
- **Score**: Engagement score (upvotes, stars, likes)
- **Time**: Relative time since publication

#### Latest Items Table

Interactive table showing the most recent content items with:

**Filtering Options:**
- **Source Filter**: Filter by specific data source or view all
- **Search**: Full-text search across titles and content
- **Refresh Button**: Manual data refresh

**Table Columns:**
- **Title**: Content title (truncated for readability)
- **Source**: Data source name
- **Score**: Engagement metrics
- **Published**: Publication timestamp

**Export Options:**
- **📄 Export CSV**: Download filtered results as CSV file
- **📋 Export JSON**: Download filtered results as JSON file

### Sources Page

The Sources page provides detailed monitoring and management of all configured data sources.

#### Sources Overview KPIs

Summary metrics across all sources:

1. **Active Sources**: Number of configured and active data sources
2. **Total Ingestions**: Total ingestion runs across all sources (last 7 days)
3. **Success Rate**: Overall ingestion success rate (last 7 days)
4. **Avg Items/Run**: Average items processed per ingestion run

#### Health Summary

Quick overview of source health status:

- **Total Sources**: Total number of configured sources
- **Healthy**: Sources operating normally
- **Degraded**: Sources with performance issues
- **Failed**: Sources experiencing failures

#### Source Cards

Each data source is displayed in a detailed card showing:

**Header Information:**
- **Source Name**: Display name (HackerNews, Reddit, etc.)
- **Health Badge**: Current health status with color coding

**Configuration Details:**
- **Type**: Source type (API, scraping, etc.)
- **Base URL**: API endpoint or source URL
- **Rate Limit**: Configured rate limit (requests per minute)

**Performance Metrics:**
- **Last Ingestion**: Time since last successful run
- **Status**: Current run status (completed, failed, running)
- **Items (24h)**: Items processed in the last 24 hours
- **Success Rate**: Historical success rate percentage

**Detailed Statistics (Expandable):**
- **Total Runs**: Number of ingestion attempts (last 7 days)
- **Successful/Failed**: Breakdown of run outcomes
- **Total Items**: Cumulative items processed
- **Median Duration**: Average processing time per run
- **Recent Runs**: List of recent ingestion attempts with timestamps and results

#### Source Details View

Click "Details" for any source to view comprehensive information:

**Configuration Panel:**
- Complete source configuration in JSON format
- API endpoints and authentication settings
- Rate limiting and retry configurations

**Performance Statistics:**
- Detailed metrics and success rates
- Processing times and throughput analysis
- Error rates and failure patterns

**Ingestion Lag Trend:**
- Time-series chart showing ingestion lag over the last 24 hours
- Helps identify performance degradation patterns

**Recent Ingestion Runs Table:**
- Detailed table of recent ingestion attempts
- Start/completion times, duration, and status
- Item counts (processed, new, updated, failed)
- Error counts and failure reasons

### Analytics Page

The Analytics page provides comprehensive data analysis and visualization capabilities.

#### Analytics Filters (Sidebar)

**Time Window Selection:**
- Last 1 hour
- Last 6 hours
- Last 24 hours (default)
- Last 7 days
- Last 30 days

**Source Selection:**
- All sources (default)
- Individual source selection
- Multiple source selection

**Search Query:**
- Full-text search across content
- Filters all analytics based on search terms

**Chart Controls:**
- Chart height adjustment
- Histogram bin count configuration
- Color scheme selection

#### Analytics Overview KPIs

Real-time metrics based on selected filters:

1. **Total Items**: Total items matching current filters
2. **New Items**: Items added in the selected time window
3. **Top Source**: Most active source by volume
4. **Avg Score**: Average engagement score across items

#### Visualization Tabs

**📊 Charts Tab**

*Items Over Time Chart:*
- Time-series line chart showing ingestion volume
- Configurable time granularity (hourly, daily)
- Interactive hover tooltips with exact counts

*Top Sources Chart:*
- Horizontal bar chart showing source activity
- Ranked by total item count
- Color-coded by source type

*Score Distribution Chart:*
- Histogram showing engagement score distribution
- Configurable bin count for granularity
- Helps identify content performance patterns

**🔥 Trending Tab**

- List of trending items based on current filters
- Ranked by engagement score or "hot" algorithm
- Includes title, score, source, and publication time
- Clickable links to original content

**📋 Data Table Tab**

- Complete raw data table with all available fields
- Sortable columns and advanced filtering
- Pagination for large datasets
- Export functionality for filtered results

**📈 Summary Tab**

- Statistical summary of current dataset
- Data overview with key metrics
- Top sources breakdown with item counts
- Applied filters summary for reference

#### Advanced Analytics Features

**Time-Series Analysis:**
- Trend identification and pattern recognition
- Peak activity period analysis
- Source activity correlation

**Content Analysis:**
- Score distribution analysis
- Source performance comparison
- Trending topic identification

**Export Capabilities:**
- Filtered data export in multiple formats
- Chart export as images (PNG, SVG)
- Summary report generation

## Auto-Refresh Feature

The auto-refresh feature provides intelligent, automated data updates with rate limiting awareness.

### Configuration Options

**Enable/Disable Toggle:**
- Checkbox to enable or disable auto-refresh
- Automatically disabled during rate limiting

**Refresh Intervals:**
- 15 seconds (for real-time monitoring)
- 30 seconds
- 1 minute
- 5 minutes (default)
- 10 minutes

### Smart Rate Limiting

**Automatic Detection:**
- Monitors API response codes for rate limiting (429)
- Tracks consecutive rate limit events
- Implements exponential backoff strategy

**Visual Indicators:**
- Progress bars showing time until next refresh
- Rate limit countdown timers
- Status messages and warnings

**Pause/Resume Controls:**
- Manual pause and resume functionality
- Automatic pause during rate limiting
- Resume after rate limit period expires

### Status Indicators

**Active State:**
- ✅ Green indicator when auto-refresh is active
- Countdown timer showing time until next refresh
- Progress bar indicating refresh cycle progress

**Rate Limited State:**
- ⚠️ Warning indicator during rate limiting
- Countdown showing wait time remaining
- Progress bar for rate limit recovery

**Paused State:**
- ⏸️ Pause indicator when manually paused
- Resume button to restart auto-refresh

### Manual Controls

**Refresh Now Button:**
- Immediate data refresh regardless of schedule
- Disabled during rate limiting
- Resets auto-refresh timer

**Pause/Resume Button:**
- Toggle auto-refresh without disabling
- Maintains interval settings
- Useful for detailed data analysis

## Data Export

Comprehensive data export functionality across all dashboard pages.

### Export Formats

**CSV Export:**
- Comma-separated values format
- Compatible with Excel, Google Sheets
- Preserves data types and formatting
- Includes column headers

**JSON Export:**
- JavaScript Object Notation format
- Preserves complete data structure
- Suitable for programmatic processing
- Human-readable formatting with indentation

**Excel Export:**
- Native Excel format (.xlsx)
- Formatted spreadsheet with proper column types
- Requires openpyxl package
- Professional presentation ready

### Export Features

**Filtered Exports:**
- Exports respect current page filters
- Search queries applied to export data
- Source filters included in export
- Time window filters preserved

**Automatic Naming:**
- Timestamp-based filenames
- Descriptive prefixes (dataseed_items_, dataseed_analytics_)
- Format-specific extensions
- Prevents filename conflicts

**Large Dataset Handling:**
- Pagination-aware exports
- Memory-efficient processing
- Progress indicators for large exports
- Error handling for failed exports

### Export Telemetry

All export actions are tracked for analytics:
- Export format preferences
- Dataset sizes and types
- User export patterns
- Performance metrics

## Mobile Experience

The dashboard is fully optimized for mobile devices with responsive design principles.

### Mobile-Specific Features

**Adaptive Navigation:**
- Collapsible sidebar for space efficiency
- Touch-friendly navigation controls
- Selectbox navigation on small screens
- Swipe gestures for page navigation

**Responsive Layouts:**
- Vertical stacking of components on mobile
- Optimized card layouts for touch interaction
- Readable typography with appropriate sizing
- Efficient use of screen real estate

**Touch Optimization:**
- Large, touch-friendly buttons and controls
- Appropriate spacing between interactive elements
- Swipe-friendly table scrolling
- Pinch-to-zoom support for charts

**Performance Optimization:**
- Reduced chart complexity on mobile
- Optimized image loading
- Efficient data pagination
- Fast initial load times

### Mobile-Specific UI Elements

**KPI Cards:**
- Stacked vertically on mobile
- Larger text for readability
- Simplified layouts
- Touch-friendly expansion

**Data Tables:**
- Horizontal scrolling for wide tables
- Sticky headers for navigation
- Simplified column layouts
- Touch-friendly sorting

**Charts and Visualizations:**
- Reduced height for mobile screens
- Touch-friendly zoom and pan
- Simplified legends and labels
- Optimized color schemes

## Telemetry and Monitoring

The dashboard includes comprehensive telemetry for monitoring user behavior and system performance.

### Tracked Events

**Page Views:**
- Navigation between dashboard pages
- Time spent on each page
- Mobile vs desktop usage patterns
- Session duration tracking

**User Actions:**
- Auto-refresh toggle activations
- Manual refresh button clicks
- Filter changes and searches
- Export button interactions

**System Events:**
- API call durations and success rates
- Rate limiting events and recovery
- Error occurrences and types
- Performance bottlenecks

**Export Activity:**
- Export format preferences
- Dataset sizes and types
- Export success/failure rates
- User export patterns

### Telemetry Data Structure

Each event includes:
- **Timestamp**: ISO 8601 formatted timestamp
- **Session ID**: Unique session identifier
- **Event Type**: Category (page_view, user_action, system_event, etc.)
- **Event Name**: Specific event identifier
- **Properties**: Additional event-specific data
- **Duration**: Performance timing (where applicable)

### Privacy and Data Handling

**Data Collection:**
- No personally identifiable information collected
- Session-based tracking only
- Local logging (no external transmission)
- Configurable via environment variables

**Data Storage:**
- Console logging for development
- Optional file logging for analysis
- Configurable log rotation
- No persistent user tracking

## Troubleshooting

### Common Issues and Solutions

#### Dashboard Won't Load

**Symptoms:**
- Blank page or loading spinner
- Connection errors in browser console

**Solutions:**
1. Verify API is running at configured URL
2. Check network connectivity
3. Verify environment variables are set correctly
4. Check browser console for JavaScript errors

#### API Connection Errors

**Symptoms:**
- "API Disconnected" status in sidebar
- Error messages about failed requests

**Solutions:**
1. Verify API_BASE_URL environment variable
2. Check API health endpoint: `curl http://localhost:8000/health`
3. Verify API is accepting connections
4. Check firewall and network settings

#### Rate Limiting Issues

**Symptoms:**
- Frequent rate limit warnings
- Auto-refresh automatically pausing
- 429 error messages

**Solutions:**
1. Increase auto-refresh interval
2. Reduce concurrent dashboard users
3. Check API rate limiting configuration
4. Monitor API usage patterns

#### Export Functionality Not Working

**Symptoms:**
- Export buttons disabled or not responding
- Download files are empty or corrupted

**Solutions:**
1. Verify data is loaded in the current view
2. Check browser download settings
3. Try different export formats
4. Clear browser cache and cookies

#### Mobile Display Issues

**Symptoms:**
- Layout problems on mobile devices
- Touch interactions not working
- Text too small to read

**Solutions:**
1. Refresh the page to reload mobile detection
2. Try different mobile browsers
3. Check device orientation (portrait/landscape)
4. Clear browser cache

#### Performance Issues

**Symptoms:**
- Slow page loading
- Unresponsive interface
- High memory usage

**Solutions:**
1. Reduce auto-refresh frequency
2. Use smaller time windows for analytics
3. Clear browser cache
4. Restart the dashboard application

### Debug Mode

Enable debug mode for additional troubleshooting information:

```bash
# Run with debug logging
STREAMLIT_LOGGER_LEVEL=debug streamlit run dashboard/main.py

# Enable telemetry file logging
TELEMETRY_ENABLED=true TELEMETRY_LOG_FILE=debug_telemetry.log streamlit run dashboard/main.py
```

### Getting Help

If you encounter issues not covered in this guide:

1. Check the telemetry logs for error details
2. Review browser console for JavaScript errors
3. Verify API connectivity and health
4. Check GitHub issues for similar problems
5. Create a new issue with detailed error information

### Performance Optimization

**For Large Datasets:**
- Use cursor-based pagination
- Implement data sampling for analytics
- Optimize database queries
- Consider data archiving strategies

**For High Traffic:**
- Implement caching strategies
- Use load balancing
- Monitor resource usage
- Scale infrastructure as needed

---

This guide covers the complete functionality of the DataSeed Dashboard. For additional technical details, see the source code documentation and API reference.